from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from agentcut import __version__
from agentcut.editor import Editor
from agentcut.enhance import enhancement_status, install_backend
from agentcut.errors import AgentCutError
from agentcut.export import ExportSpec
from agentcut.render import Renderer


def make_image(path: Path, size=(320, 180)):
    im = Image.new("RGB", size, "#151821")
    d = ImageDraw.Draw(im)
    d.rectangle((30, 30, 120, 150), fill="#e07a5f")
    d.ellipse((200, 50, 285, 135), fill="#81b29a")
    im.save(path)


def probe_video(path: Path) -> dict:
    cp = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,codec_name,nb_frames",
        "-of", "json", str(path),
    ], text=True, capture_output=True, check=True)
    return json.loads(cp.stdout)["streams"][0]


def test_export_spec_accepts_custom_geometry_fps_and_formats():
    spec = ExportSpec.normalized(width=2560, height=1080, fps=48, container="mov", codec="prores", encoder="cpu")
    assert (spec.width, spec.height, spec.fps, spec.container, spec.codec) == (2560, 1080, 48, "mov", "prores")
    with pytest.raises(AgentCutError):
        ExportSpec.normalized(width=1920, height=1080, fps=30, container="webm", codec="prores")


def test_custom_renderer_can_explicitly_exceed_project_canvas(tmp_path):
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=12)
    p = Renderer(e.root, e.get_project())._profile("final", {"width": 640, "height": 360, "fps": 24, "allow_canvas_upscale": True})
    assert (p["width"], p["height"], p["fps"]) == (640, 360, 24)


def test_export_plan_is_machine_readable_and_ai_optional(tmp_path):
    e = Editor.create(tmp_path / "p", width=1920, height=1080, fps=30)
    plan = e.plan_export(width=3840, height=2160, fps=60, container="mp4", codec="hevc", encoder="auto", upscale="auto", interpolate="auto")
    assert plan["spec"]["width"] == 3840 and plan["spec"]["fps"] == 60
    assert plan["enhancement"]["upscale"]["enabled"] is True
    assert plan["enhancement"]["interpolation"]["enabled"] is True
    assert plan["encoder"]["backend"] in {"cpu", "gpu"}


def test_third_party_ai_install_requires_explicit_acceptance():
    with pytest.raises(AgentCutError) as exc:
        install_backend("realesrgan", accept_third_party=False)
    assert exc.value.code == "THIRD_PARTY_ACCEPTANCE_REQUIRED"


def test_actual_custom_48fps_export(tmp_path):
    src = tmp_path / "a.png"; make_image(src)
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=12)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 0.35, scene_id="s1")
    result = e.export_video(width=480, height=270, fps=48, container="mp4", codec="h264", encoder="cpu", upscale="off", interpolate="off", output=tmp_path / "custom.mp4")
    out = Path(result["output"])
    assert out.exists() and out.stat().st_size > 0
    v = probe_video(out)
    assert (v["width"], v["height"]) == (480, 270)
    assert v["avg_frame_rate"] == "48/1"
    assert Path(str(out) + ".agentcut-export.json").exists()


def test_actual_fallback_enhancement_chain(tmp_path):
    src = tmp_path / "a.png"; make_image(src, (160, 90))
    e = Editor.create(tmp_path / "p", width=160, height=90, fps=12)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 0.5, scene_id="s1")
    result = e.export_video(width=320, height=180, fps=24, container="mp4", codec="h264", encoder="cpu", upscale="auto", interpolate="auto", output=tmp_path / "enhanced.mp4")
    out = Path(result["output"])
    v = probe_video(out)
    assert (v["width"], v["height"]) == (320, 180)
    assert v["avg_frame_rate"] == "24/1"
    stages = {x["stage"]: x for x in result["stages"]}
    assert stages["frame_interpolation"]["backend"] in {"ffmpeg_minterpolate", "rife-ncnn-vulkan"}
    assert stages["super_resolution"]["backend"] in {"ffmpeg_lanczos", "realesrgan-ncnn-vulkan"}


def test_actual_webm_vp9_export(tmp_path):
    src = tmp_path / "a.png"; make_image(src)
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=12)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 0.25, scene_id="s1")
    result = e.export_video(width=320, height=180, fps=12, container="webm", codec="vp9", encoder="cpu", upscale="off", interpolate="off", output=tmp_path / "clip.webm")
    v = probe_video(Path(result["output"]))
    assert v["codec_name"] == "vp9"


def test_enhancement_status_has_ai_and_fallbacks():
    status = enhancement_status()
    assert "realesrgan" in status and "rife" in status
    assert status["fallbacks"]["upscale"] == "ffmpeg_lanczos"
    assert status["fallbacks"]["interpolation"] == "ffmpeg_minterpolate"


def test_v3_http_api_exposes_export_and_enhancement(tmp_path):
    from fastapi.testclient import TestClient
    from agentcut.api import create_app
    Editor.create(tmp_path / "p", width=320, height=180, fps=24)
    client = TestClient(create_app(tmp_path / "p"))
    assert client.get("/health").json()["version"] == __version__
    assert client.get("/enhancement/status").status_code == 200
    r = client.post("/export/plan", json={"width": 640, "height": 360, "fps": 48, "container": "mp4", "codec": "h264", "upscale": "auto", "interpolate": "auto"})
    assert r.status_code == 200
    body = r.json()
    assert body["spec"]["width"] == 640 and body["spec"]["fps"] == 48


def make_tiny_video(path: Path, fps=12, duration=0.25, size="160x90"):
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={fps}",
        "-t", str(duration), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ], check=True)


def failing_backend(monkeypatch, variable):
    """Exercise a real failed child process without requiring POSIX /bin/false."""
    monkeypatch.setenv(variable, sys.executable)
    original_run = subprocess.run
    def run_failure(command, *args, **kwargs):
        if command and str(command[0]) == sys.executable:
            command = [sys.executable, "-c", "raise SystemExit(1)"]
        return original_run(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, "run", run_failure)


def test_auto_upscale_falls_back_if_detected_ai_runtime_fails(tmp_path, monkeypatch):
    from agentcut.enhance import upscale_video
    src = tmp_path / "src.mp4"; make_tiny_video(src)
    failing_backend(monkeypatch, "AGENTCUT_REALESRGAN")
    out = tmp_path / "up.mp4"
    result = upscale_video(src, out, width=320, height=180, backend="auto", model="anime")
    assert result["backend"] == "ffmpeg_lanczos"
    assert result["ai"] is False
    assert result["fallback_from"] == "realesrgan-ncnn-vulkan"
    assert out.exists()


def test_auto_interpolation_falls_back_if_detected_ai_runtime_fails(tmp_path, monkeypatch):
    from agentcut.enhance import interpolate_video
    src = tmp_path / "src.mp4"; make_tiny_video(src)
    failing_backend(monkeypatch, "AGENTCUT_RIFE")
    out = tmp_path / "fi.mp4"
    result = interpolate_video(src, out, target_fps=24, backend="auto", hard_cut_times=[])
    assert result["backend"] == "ffmpeg_minterpolate"
    assert result["ai"] is False
    assert result["fallback_from"] == "rife-ncnn-vulkan"
    assert out.exists()


def test_lightweight_checkout_does_not_bundle_realesrgan():
    from agentcut.enhance import enhancement_status
    status = enhancement_status()["realesrgan"]
    assert status["bundled"] is False
    assert status["bundled_models"] == []


def test_lightweight_checkout_has_no_heavy_vendor_payload():
    vendor = Path(__file__).parents[1] / "agentcut" / "vendor"
    files = list(vendor.rglob("*")) if vendor.exists() else []
    assert not [path for path in files if path.is_file() and path.suffix.lower() in {".bin", ".exe", ".dll", ".so"}]


def test_uninstalled_realesrgan_auto_uses_ffmpeg_fallback(tmp_path, monkeypatch):
    import agentcut.enhance as enhance
    from agentcut.enhance import upscale_video
    src = tmp_path / "src.mp4"; make_tiny_video(src)
    monkeypatch.delenv("AGENTCUT_REALESRGAN", raising=False)
    original = enhance._find_backend
    monkeypatch.setattr(enhance, "_find_backend", lambda name: None if name == "realesrgan" else original(name))
    out = tmp_path / "up.mp4"
    result = upscale_video(src, out, width=320, height=180, backend="auto", model="anime")
    assert out.exists()
    assert result["backend"] == "ffmpeg_lanczos"
    assert result["ai"] is False
