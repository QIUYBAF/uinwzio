from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .probe import probe
from .util import ensure_binary, run


def make_contact_sheet(video: Path, output: Path, *, interval: float = 2.0, columns: int = 4, thumb_width: int = 320) -> Path:
    info = probe(video)
    video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    try:
        duration = float((video_stream or {}).get("duration") or info.get("format", {}).get("duration", 0) or 0)
    except (TypeError, ValueError):
        duration = float(info.get("format", {}).get("duration", 0) or 0)
    times = []
    t = 0.0
    while t < duration + 1e-6:
        times.append(min(t, max(0, duration - 0.05)))
        t += interval
    if not times:
        times = [0.0]
    tmp = output.parent / f".{output.stem}_frames"
    tmp.mkdir(parents=True, exist_ok=True)
    ffmpeg = ensure_binary("ffmpeg")
    frames = []
    for i, sec in enumerate(times):
        # PNG avoids FFmpeg MJPEG full-range compliance failures seen on newer builds.
        p = tmp / f"{i:03d}.png"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{sec:.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={thumb_width}:-2", str(p)])
        img = Image.open(p).convert("RGB")
        frames.append((sec, img.copy()))
        img.close()
    thumb_height = max(img.height for _, img in frames)
    label_h = 28
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_h)), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)
    for i, (sec, img) in enumerate(frames):
        x = (i % columns) * thumb_width
        y = (i // columns) * (thumb_height + label_h)
        sheet.paste(img, (x, y))
        draw.text((x + 8, y + thumb_height + 5), f"{sec:.1f}s", fill=(235,235,235))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=90)
    for p in tmp.glob("*.png"):
        p.unlink(missing_ok=True)
    tmp.rmdir()
    return output
