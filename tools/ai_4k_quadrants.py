#!/usr/bin/env python3
"""AI 4K quadrant helper.

Utility for ChatGPT Work / Codex image workflows:
1. Split a 16:9 source image exactly into four equal quadrants.
2. Reconstruct/up-detail each quadrant with an image model while preserving composition.
3. Stitch the four reconstructed quadrants back into one high-information image.
4. Optionally run a light final AI upscale to UHD 4K (3840x2160).

Example pipeline for a 1536x864 source:
1536x864 -> 4 x 768x432 -> AI reconstruction to 4 x 1536x864
-> stitch to 3072x1728 -> optional 1.25x AI upscale -> 3840x2160.

This script performs only deterministic split/stitch I/O. It does not call an AI model.
Requires Pillow: pip install pillow
"""

from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image

QUADRANTS = ("TL", "TR", "BL", "BR")


def _save(img: Image.Image, path: Path, quality: int = 95) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        img.convert("RGB").save(path, quality=quality, subsampling=0)
    else:
        img.save(path)


def split_image(source: Path, output_dir: Path, fmt: str, quality: int) -> None:
    with Image.open(source) as src:
        img = src.convert("RGB") if fmt in {"jpg", "jpeg"} else src.copy()
        w, h = img.size
        if w % 2 or h % 2:
            raise ValueError(f"Image dimensions must be even for an exact 2x2 split; got {w}x{h}.")
        mx, my = w // 2, h // 2
        boxes = {
            "TL": (0, 0, mx, my),
            "TR": (mx, 0, w, my),
            "BL": (0, my, mx, h),
            "BR": (mx, my, w, h),
        }
        ext = "jpg" if fmt == "jpeg" else fmt
        for label in QUADRANTS:
            out = output_dir / f"{label}.{ext}"
            _save(img.crop(boxes[label]), out, quality)
            print(f"{label}: {out} ({mx}x{my})")


def stitch_images(tl: Path, tr: Path, bl: Path, br: Path, output: Path, quality: int) -> None:
    paths = dict(zip(QUADRANTS, (tl, tr, bl, br)))
    opened = {k: Image.open(v).convert("RGB") for k, v in paths.items()}
    try:
        sizes = {im.size for im in opened.values()}
        if len(sizes) != 1:
            raise ValueError(f"All four quadrants must have identical dimensions; got {sorted(sizes)}")
        w, h = next(iter(sizes))
        canvas = Image.new("RGB", (w * 2, h * 2))
        canvas.paste(opened["TL"], (0, 0))
        canvas.paste(opened["TR"], (w, 0))
        canvas.paste(opened["BL"], (0, h))
        canvas.paste(opened["BR"], (w, h))
        _save(canvas, output, quality)
        print(f"stitched: {output} ({w * 2}x{h * 2})")
    finally:
        for im in opened.values():
            im.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Split/stitch helper for AI-assisted 4K image reconstruction.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_split = sub.add_parser("split", help="Split one image into exact TL/TR/BL/BR quadrants.")
    p_split.add_argument("source", type=Path)
    p_split.add_argument("-o", "--output-dir", type=Path, default=Path("quadrants"))
    p_split.add_argument("--format", choices=("jpg", "jpeg", "png"), default="jpg")
    p_split.add_argument("--quality", type=int, default=95)

    p_stitch = sub.add_parser("stitch", help="Hard-stitch four equal quadrants with no blending or resampling.")
    p_stitch.add_argument("--tl", type=Path, required=True, help="top-left")
    p_stitch.add_argument("--tr", type=Path, required=True, help="top-right")
    p_stitch.add_argument("--bl", type=Path, required=True, help="bottom-left")
    p_stitch.add_argument("--br", type=Path, required=True, help="bottom-right")
    p_stitch.add_argument("-o", "--output", type=Path, default=Path("stitched.jpg"))
    p_stitch.add_argument("--quality", type=int, default=95)

    args = parser.parse_args()
    if not 1 <= args.quality <= 100:
        parser.error("--quality must be between 1 and 100")

    if args.command == "split":
        split_image(args.source, args.output_dir, args.format, args.quality)
    else:
        stitch_images(args.tl, args.tr, args.bl, args.br, args.output, args.quality)


if __name__ == "__main__":
    main()
