from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import subprocess
from pathlib import Path

from . import __version__
from .director import choose_backend


def _first_line(cmd: list[str], timeout: int = 8) -> str | None:
    try:
        cp = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=timeout)
        value = (cp.stdout or cp.stderr or "").strip()
        return value.splitlines()[0] if value else None
    except Exception:
        return None


def _output(cmd: list[str], timeout: int = 12) -> str:
    try:
        cp = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=timeout)
        return (cp.stdout or "") + (cp.stderr or "")
    except Exception:
        return ""


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _install_hint() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "Install FFmpeg and add ffmpeg/ffprobe to PATH (for example: winget install Gyan.FFmpeg)."
    if system == "darwin":
        return "Install FFmpeg (for example: brew install ffmpeg)."
    return "Install FFmpeg with your system package manager (for example: sudo apt install ffmpeg)."


def run_doctor(project_root=None, *, fix: bool = False) -> dict:
    """Inspect a fresh checkout without crashing when optional tools are absent."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    filters_text = _output([ffmpeg, "-hide_banner", "-filters"]) if ffmpeg else ""
    encoders_text = _output([ffmpeg, "-hide_banner", "-encoders"]) if ffmpeg else ""

    required_filters = ["xfade", "concat", "ass", "blend", "amix", "alimiter", "perspective", "colorkey", "overlay"]
    optional_filters = ["minterpolate", "scale"]
    filters = {name: name in filters_text for name in required_filters + optional_filters}
    encoders = {
        "libx264": "libx264" in encoders_text,
        "libx265": "libx265" in encoders_text,
        "libaom-av1": "libaom-av1" in encoders_text,
        "libvpx-vp9": "libvpx-vp9" in encoders_text,
        "prores_ks": "prores_ks" in encoders_text,
        "h264_nvenc": "h264_nvenc" in encoders_text,
        "hevc_nvenc": "hevc_nvenc" in encoders_text,
        "av1_nvenc": "av1_nvenc" in encoders_text,
        "aac": " aac" in encoders_text or "AAC" in encoders_text,
        "libopus": "libopus" in encoders_text,
        "qtrle": "qtrle" in encoders_text,
    }

    numpy_version = _package_version("numpy")
    pillow_version = _package_version("Pillow")
    editing_ready = bool(numpy_version and pillow_version)
    rendering_ready = bool(
        ffmpeg
        and ffprobe
        and all(filters[name] for name in required_filters)
        and encoders["libx264"]
        and encoders["aac"]
    )
    status = "pass" if editing_ready and rendering_ready else "degraded" if editing_ready else "fail"

    try:
        from .export import nvenc_runtime_available
        nvenc_runtime = {name: nvenc_runtime_available(name) for name in ("h264", "hevc", "av1")} if ffmpeg else {name: False for name in ("h264", "hevc", "av1")}
    except Exception:
        nvenc_runtime = {name: False for name in ("h264", "hevc", "av1")}
    try:
        from .enhance import enhancement_status
        ai = enhancement_status()
    except Exception as exc:
        ai = {"available": False, "error": str(exc)}
    try:
        from .subtitles import asr_status
        asr = asr_status()
    except Exception as exc:
        asr = {"available": False, "error": str(exc)}

    changes = []
    runtime_home = Path(os.getenv("AGENTCUT_HOME", str(Path.home() / ".agentcut"))).expanduser()
    if fix:
        for name in ("backends", "cache", "logs"):
            target = runtime_home / name
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                changes.append({"created": str(target)})

    suggestions = []
    if not editing_ready:
        suggestions.append("Install Python dependencies: python -m pip install -e AgentCut")
    if not (ffmpeg and ffprobe):
        suggestions.append(_install_hint())
    elif not rendering_ready:
        suggestions.append("Use an FFmpeg build containing the required filters plus libx264 and AAC encoders.")
    suggestions.append("Remotion is optional; install it inside a project only when React/UI rendering is required.")

    fc_match = shutil.which("fc-match")
    node = shutil.which("node")
    npm = shutil.which("npm")
    return {
        "status": status,
        "version": __version__,
        "editing_ready": editing_ready,
        "rendering_ready": rendering_ready,
        "backend": choose_backend(project_root=project_root),
        "environment": {
            "platform": platform.platform(),
            "numpy": numpy_version,
            "Pillow": pillow_version,
            "node": node,
            "node_version": _first_line([node, "--version"]) if node else None,
            "npm": npm,
        },
        "ffmpeg": {"path": ffmpeg, "version": _first_line([ffmpeg, "-version"]) if ffmpeg else None},
        "ffprobe": {"path": ffprobe, "version": _first_line([ffprobe, "-version"]) if ffprobe else None},
        "filters": filters,
        "encoders": encoders,
        "gpu_runtime": {"nvenc": nvenc_runtime},
        "optional": {"ai_enhancement": ai, "subtitle_asr": asr},
        "render_ceiling": {"official_max": "3840x2160@60fps", "uhd_4k60_ready": rendering_ready and editing_ready},
        "font_probe": {"fc_match": fc_match, "noto_sans_cjk_sc": _first_line([fc_match, "Noto Sans CJK SC"]) if fc_match else None},
        "fix": {"requested": fix, "runtime_home": str(runtime_home), "changes": changes},
        "suggestions": suggestions,
    }
