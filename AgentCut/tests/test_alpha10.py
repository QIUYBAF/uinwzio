from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from agentcut.editor import Editor
from agentcut.render import Renderer, PROFILES


def make_image(path: Path, size=(960, 540)):
    im = Image.new("RGB", size, "#20242a")
    d = ImageDraw.Draw(im)
    d.rectangle((80, 80, 360, 460), fill="#ef8354")
    d.rectangle((620, 140, 900, 400), fill="#4f5d75")
    im.save(path)


def test_agent_preflight_repairs_common_llm_aliases(tmp_path):
    src = tmp_path / "a.png"; make_image(src)
    e = Editor.create(tmp_path / "p")
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 2.0, scene_id="s1")
    before = e.state_digest()["project_hash"]
    ops = [{"action": "transition", "args": {"scene": "s1", "type": "fade", "duration": 0.25}}]
    check = e.preflight_operations(ops, expected_project_hash=before)
    assert check["ok"] is True
    assert check["operations"] == [{"action": "set_transition", "args": {"scene_id": "s1", "transition": "fade", "duration": 0.25}}]
    assert len(check["repairs"]) >= 3
    assert e.state_digest()["project_hash"] == before  # dry-run must not mutate


def test_agent_apply_commits_normalized_transaction(tmp_path):
    src = tmp_path / "a.png"; make_image(src)
    e = Editor.create(tmp_path / "p")
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 2.0, scene_id="s1")
    h = e.state_digest()["project_hash"]
    result = e.apply_agent_operations([
        {"action": "camera", "args": {"sceneId": "s1", "type": "slow_push", "amount": 0.02}},
        {"action": "filter", "args": {"scene": "s1", "filter": "cool"}},
    ], expected_project_hash=h)
    assert result["ok"] is True and result["applied"] == 2
    scene = e.get_scene("s1")
    assert scene["camera"]["type"] == "slow_push"
    assert "cool" in scene["filters"]


def test_agent_preflight_library_typo_returns_suggestions(tmp_path):
    src = tmp_path / "a.png"; make_image(src)
    e = Editor.create(tmp_path / "p")
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 1.0, scene_id="s1")
    check = e.preflight_operations([{"action": "filter", "args": {"scene": "s1", "filter": "cinematic_cool"}}])
    assert check["ok"] is False
    assert check["error"]["error"] == "LIBRARY_ITEM_NOT_FOUND"
    assert check["warnings"]
    suggestions = check["warnings"][0]["suggestions"]
    assert "cinematic_contrast" in suggestions or "cool" in suggestions


def test_operation_schema_is_machine_readable(tmp_path):
    e = Editor.create(tmp_path / "p")
    schema = e.operation_schema()
    assert "set_transition" in schema
    assert "scene_id" in schema["set_transition"]["required"]
    assert "transition" in schema["set_transition"]["required"]
    assert "duration" in schema["set_transition"]["optional"]


def test_4k60_profile_exact_on_4k60_project(tmp_path):
    e = Editor.create(tmp_path / "p", width=3840, height=2160, fps=60)
    p = Renderer(e.root, e.get_project())._profile("uhd_4k60")
    assert (p["width"], p["height"], p["fps"]) == (3840, 2160, 60)
    assert p["camera_supersample"] == 1


def test_4k60_profile_does_not_upscale_smaller_project(tmp_path):
    e = Editor.create(tmp_path / "p", width=1920, height=1080, fps=30)
    p = Renderer(e.root, e.get_project())._profile("uhd_4k60")
    assert (p["width"], p["height"], p["fps"]) == (1920, 1080, 30)


def test_actual_4k60_static_render(tmp_path):
    src = tmp_path / "a.png"; make_image(src, (1280, 720))
    e = Editor.create(tmp_path / "p", width=3840, height=2160, fps=60)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 0.25, scene_id="s1")
    out = e.render_4k60(tmp_path / "4k60.mp4")
    assert out.exists() and out.stat().st_size > 0
    cp = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,nb_frames", "-of", "json", str(out)
    ], text=True, capture_output=True, check=True)
    stream = json.loads(cp.stdout)["streams"][0]
    assert (stream["width"], stream["height"]) == (3840, 2160)
    assert stream["avg_frame_rate"] == "60/1"
    assert int(stream.get("nb_frames") or 0) >= 14


def test_video_mode_semantic_operation_and_alias(tmp_path):
    e = Editor.create(tmp_path / "p")
    check = e.preflight_operations([{"action": "video_mode", "args": {"mode": "4k60"}}])
    assert check["ok"] is True
    result = e.apply_agent_operations([{"action": "video_mode", "args": {"mode": "4k60"}}])
    assert result["ok"] is True
    assert e.get_project()["video"] == {"width": 3840, "height": 2160, "fps": 60}
