from __future__ import annotations

import shutil
from pathlib import Path


def _local_remotion(project_root=None) -> str | None:
    executable = shutil.which("remotion")
    if executable:
        return executable
    if project_root:
        bin_dir = Path(project_root).resolve() / "node_modules" / ".bin"
        for name in ("remotion", "remotion.cmd"):
            candidate = bin_dir / name
            if candidate.is_file():
                return str(candidate)
    return None


def _pillow_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def choose_backend(*, needs_react_ui=False, project_root=None):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    node = shutil.which("node")
    npm = shutil.which("npm")
    remotion = _local_remotion(project_root)
    pillow = _pillow_available()
    if needs_react_ui and remotion and node:
        selected = "remotion"
        reason = "React/UI presentation requested and a local Remotion executable is available"
    elif ffmpeg and ffprobe:
        selected = "ffmpeg/pillow"
        reason = "deterministic lightweight renderer is healthy"
    elif pillow:
        selected = "pillow-only"
        reason = "editing and image operations are available; install FFmpeg to render video"
    else:
        selected = "unavailable"
        reason = "install Pillow and FFmpeg to enable the lightweight runtime"
    return {
        "selected": selected,
        "ffmpeg_available": bool(ffmpeg and ffprobe),
        "pillow_available": pillow,
        "remotion_available": bool(remotion and node),
        "remotion_executable": remotion,
        "node_available": bool(node and npm),
        "reason": reason,
        "rule": "Prefer the cheapest healthy backend that satisfies the result.",
    }


def plan(goal, *, scenes=None, domains=None, needs_react_ui=False, project_root=None):
    return {
        "schema": "agentcut-director-plan-v1",
        "goal": goal,
        "scope": scenes or ["task-scoped"],
        "domains": domains or ["infer-minimum-required"],
        "backend": choose_backend(needs_react_ui=needs_react_ui, project_root=project_root),
        "loop": ["bootstrap", "scoped-context", "preflight", "apply", "local-preview", "qa", "stop-or-one-local-fix"],
        "guardrails": ["no repository archaeology", "no full render when local preview is sufficient", "no repeated QA without a concrete failure", "preserve canonical project state"],
    }
