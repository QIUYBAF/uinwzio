from __future__ import annotations

import json
from pathlib import Path

from .util import ensure_binary, run


def probe(path: Path) -> dict:
    ffprobe = ensure_binary("ffprobe")
    cp = run([
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,duration,start_time",
        "-of", "json", str(path)
    ])
    return json.loads(cp.stdout)


def primary_video_info(path: Path) -> dict | None:
    data = probe(path)
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            return s
    return None


def primary_audio_info(path: Path) -> dict | None:
    data = probe(path)
    for s in data.get("streams", []):
        if s.get("codec_type") == "audio":
            return s
    return None


def _rate(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    if "/" in text:
        a, b = text.split("/", 1)
        try:
            den = float(b)
            return float(a) / den if den else None
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


def probe_media(path: Path) -> dict:
    """Return normalized probe data while preserving raw stream fields."""
    data = probe(Path(path))
    streams = []
    for row in data.get("streams", []):
        item = dict(row)
        if item.get("codec_type") == "video":
            item["fps"] = _rate(item.get("r_frame_rate"))
        for key in ("duration", "start_time"):
            if item.get(key) is not None:
                try:
                    item[key] = float(item[key])
                except (TypeError, ValueError):
                    pass
        streams.append(item)
    duration = (data.get("format") or {}).get("duration")
    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    return {"duration": duration, "streams": streams, "raw": data}
