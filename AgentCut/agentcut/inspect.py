from __future__ import annotations

from pathlib import Path

from .contact_sheet import make_contact_sheet
from .errors import AgentCutError
from .util import ensure_binary, run


def extract_frame(video: Path, output: Path, *, time: float) -> Path:
    if time < 0:
        raise AgentCutError("INVALID_TIME", "Frame time must be >= 0", time=time)
    if not video.exists():
        raise AgentCutError("FILE_NOT_FOUND", "Video for inspection does not exist", path=str(video))
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ensure_binary("ffmpeg")
    run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{time:.6f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(output)
    ])
    return output


def inspect_contact_sheet(video: Path, output: Path, *, interval: float = 2.0) -> Path:
    if interval <= 0:
        raise AgentCutError("INVALID_INTERVAL", "Contact sheet interval must be > 0", interval=interval)
    if not video.exists():
        raise AgentCutError("FILE_NOT_FOUND", "Video for inspection does not exist", path=str(video))
    return make_contact_sheet(video, output, interval=interval)
