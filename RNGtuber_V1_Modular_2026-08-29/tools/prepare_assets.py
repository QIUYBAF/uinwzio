from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "source_input"
RUNTIME = ROOT / "assets" / "characters" / "zhou_wanqing" / "runtime"


def connected_background(candidate: np.ndarray) -> np.ndarray:
    """Return border-connected background pixels, with a dependency-free fallback."""
    seed = np.zeros_like(candidate, dtype=bool)
    seed[0, :] = candidate[0, :]
    seed[-1, :] = candidate[-1, :]
    seed[:, 0] = candidate[:, 0]
    seed[:, -1] = candidate[:, -1]
    try:
        from scipy.ndimage import binary_propagation

        return binary_propagation(seed, mask=candidate)
    except Exception:
        height, width = candidate.shape
        result = seed.copy()
        queue = deque(map(tuple, np.argwhere(seed)))
        while queue:
            y, x = queue.popleft()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and candidate[ny, nx] and not result[ny, nx]:
                    result[ny, nx] = True
                    queue.append((ny, nx))
        return result


def transparent_base(source: Path, destination: Path, silhouette_reference: Path | None = None) -> None:
    rgb = np.asarray(Image.open(source).convert("RGB"), dtype=np.uint8)
    if silhouette_reference is not None and silhouette_reference.exists():
        # The formal V4 master already has an approved transparent silhouette
        # and clean edge colours.  Keep that master outside the face, then
        # feather in the supplied faceless Base only over the facial region.
        # This removes every white-matte hair hole while still guaranteeing
        # that eyes/brows/mouth are absent from Base and the original nose stays.
        reference_image = Image.open(silhouette_reference).convert("RGBA")
        reference = np.asarray(reference_image, dtype=np.uint8)
        if reference.shape[:2] != rgb.shape[:2]:
            raise ValueError(f"silhouette size mismatch: {silhouette_reference}")
        alpha = reference[..., 3].copy()
        alpha[alpha < 8] = 0
        face_mask = Image.new("L", reference_image.size, 0)
        ImageDraw.Draw(face_mask).ellipse((390, 72, 630, 282), fill=255)
        face_mask = face_mask.filter(ImageFilter.GaussianBlur(5.0))
        blend = np.asarray(face_mask, dtype=np.float32)[..., None] / 255.0
        corrected = (
            reference[..., :3].astype(np.float32) * (1.0 - blend)
            + rgb.astype(np.float32) * blend
        ).astype(np.uint8)
        Image.fromarray(np.dstack((corrected, alpha)), "RGBA").save(destination, optimize=True)
        return
    high = rgb.min(axis=2) >= 238
    neutral = (rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)) <= 26
    background = connected_background(high & neutral)
    background_image = Image.fromarray((background.astype(np.uint8) * 255), "L")
    near_background = np.asarray(background_image.filter(ImageFilter.MaxFilter(7))) > 0
    alpha = np.full(background.shape, 255, dtype=np.uint8)
    alpha[background] = 0
    fringe = near_background & ~background
    # Retain dark hair/clothing edges, but make near-white JPEG antialias pixels
    # partially transparent to avoid a white halo in transparent windows.
    whiteness_distance = 255 - rgb.min(axis=2).astype(np.int16)
    alpha[fringe] = np.clip(whiteness_distance[fringe], 0, 255).astype(np.uint8)
    # Undo JPEG's white matte on the narrow boundary ring.  This is the
    # standard color-to-alpha inverse for a white background and prevents a
    # bright fringe on dark/transparent streaming backgrounds.
    corrected = rgb.astype(np.float32)
    a = alpha.astype(np.float32) / 255.0
    partial = fringe & (alpha > 0) & (alpha < 255)
    for channel in range(3):
        values = corrected[..., channel]
        values[partial] = (values[partial] - (1.0 - a[partial]) * 255.0) / np.maximum(a[partial], 1e-4)
    corrected = np.clip(corrected, 0, 255).astype(np.uint8)
    rgba = np.dstack((corrected, alpha))
    Image.fromarray(rgba, "RGBA").save(destination, optimize=True)


def clean_sprite(source: Path) -> Image.Image:
    image = Image.open(source).convert("RGBA")
    rgba = np.asarray(image).copy()
    rgba[..., 3][rgba[..., 3] < 12] = 0
    return Image.fromarray(rgba, "RGBA")


def mask_half(image: Image.Image, left: bool) -> Image.Image:
    rgba = np.asarray(image).copy()
    midpoint = rgba.shape[1] // 2
    if left:
        rgba[:, midpoint:, 3] = 0
    else:
        rgba[:, :midpoint, 3] = 0
    return Image.fromarray(rgba, "RGBA")


def iris_sprite(source: Image.Image, center: tuple[int, int], radius: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", source.size, 0)
    draw = ImageDraw.Draw(mask)
    cx, cy = center
    rx, ry = radius
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    rgba = np.asarray(source).copy()
    rgba[..., 3] = np.minimum(rgba[..., 3], np.asarray(mask, dtype=np.uint8))
    rgba[..., 3][rgba[..., 3] < 12] = 0
    return Image.fromarray(rgba, "RGBA")


def bbox_for(path: Path) -> list[int] | None:
    image = Image.open(path).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    return list(bbox) if bbox else None


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    reference = RUNTIME.parent / "reference"
    transparent_base(
        SOURCE / "casual_base_source.jpeg",
        RUNTIME / "casual_base.png",
        reference / "casual_master.png",
    )
    transparent_base(
        SOURCE / "cos_base_source.jpeg",
        RUNTIME / "cos_base.png",
        reference / "cos_master.png",
    )

    direct = {
        "mouth_closed.png": "mouth_closed.png",
        "mouth_open.png": "mouth_open.png"
    }
    for source_name, runtime_name in direct.items():
        clean_sprite(SOURCE / source_name).save(RUNTIME / runtime_name, optimize=True)

    whites = clean_sprite(SOURCE / "eye_whites.png")
    mask_half(whites, True).save(RUNTIME / "eye_white_left.png", optimize=True)
    mask_half(whites, False).save(RUNTIME / "eye_white_right.png", optimize=True)

    for source_name, runtime_stem in (
        ("eyebrows.png", "eyebrow"),
        ("eyelid_closed.png", "eyelid_closed"),
        ("eyeliner_open.png", "eyeliner_open"),
        ("eye_glow.png", "eye_glow"),
    ):
        source = clean_sprite(SOURCE / source_name)
        mask_half(source, True).save(RUNTIME / f"{runtime_stem}_left.png", optimize=True)
        mask_half(source, False).save(RUNTIME / f"{runtime_stem}_right.png", optimize=True)

    irises = clean_sprite(SOURCE / "irises_source.png")
    # Elliptical masks isolate iris/pupil from the AI source's attached sclera.
    iris_sprite(irises, (461, 315), (18, 22)).save(RUNTIME / "iris_left.png", optimize=True)
    iris_sprite(irises, (571, 309), (18, 22)).save(RUNTIME / "iris_right.png", optimize=True)

    report: dict[str, object] = {"canvas": [1024, 1536], "files": {}, "issues": []}
    for path in sorted(RUNTIME.glob("*.png")):
        image = Image.open(path)
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        report["files"][path.name] = {
            "mode": image.mode,
            "size": list(image.size),
            "alpha_extrema": list(alpha.getextrema()),
            "alpha_bbox": list(bbox) if bbox else None,
            "bytes": path.stat().st_size,
        }
        if image.mode != "RGBA" or image.size != (1024, 1536) or bbox is None:
            report["issues"].append(path.name)
    report["ok"] = not report["issues"]
    (RUNTIME.parent / "ASSET_QA.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
