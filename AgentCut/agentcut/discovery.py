from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

from . import __version__
from .director import choose_backend
from .modules import module_status

def _version(cmd):
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=8)
        text = (cp.stdout or cp.stderr or "").strip()
        return text.splitlines()[0] if text else None
    except Exception:
        return None

def discover() -> dict:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    node = shutil.which("node")
    npm = shutil.which("npm")
    backend = choose_backend()
    cloud = os.getenv("AGENTCUT_CLOUD", "").lower() in {"1", "true", "yes"} or bool(
        os.getenv("CODEX_SANDBOX") or os.getenv("CHATGPT_WORK")
    )
    if backend["selected"] == "ffmpeg/pillow":
        status = "ready"
    elif backend["selected"] == "pillow-only":
        status = "ready_degraded"
    elif backend["selected"] == "ffmpeg-only":
        status = "needs_python_dependencies"
    else:
        status = "needs_core_runtime"
    return {
        "name": "AgentCut",
        "version": __version__,
        "release": f"{__version__}-remaster",
        "modules": module_status(),
        "status": status,
        "canonical_state": "project.json",
        "agent_protocol": 5,
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cloud_hint": cloud,
            "ffmpeg": ffmpeg,
            "ffprobe": ffprobe,
            "node": node,
            "node_version": _version([node, "--version"]) if node else None,
            "npm": npm,
        },
        "backend": backend,
        "backend_policy": {
            "default": "auto",
            "remotion_available": backend["remotion_available"],
            "fallback": "ffmpeg/pillow",
            "rule": "Do not block editing because optional Remotion/Chromium is absent.",
        },
        "for_agents": {
            "read_first": "AGENTS.md",
            "machine_manifest": "agentcut.manifest.json",
            "direct_runner": "python AgentCut/run.py",
            "do_not_scan_history": True,
            "do_not_guess_versions": True,
        },
    }
