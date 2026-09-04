from __future__ import annotations

import math
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from .errors import AgentCutError
from .util import ensure_binary, run

# Zones are deliberately conservative: title/caption placement should avoid the exact
# center whenever a comparably empty edge/corner exists.
_ZONE_RECTS = {
    "top_left": (0.04, 0.05, 0.38, 0.34),
    "top": (0.28, 0.05, 0.72, 0.30),
    "top_right": (0.62, 0.05, 0.96, 0.34),
    "left": (0.04, 0.30, 0.34, 0.70),
    "center": (0.32, 0.28, 0.68, 0.72),
    "right": (0.66, 0.30, 0.96, 0.70),
    "bottom_left": (0.04, 0.66, 0.38, 0.94),
    "bottom": (0.28, 0.70, 0.72, 0.95),
    "bottom_right": (0.62, 0.66, 0.96, 0.94),
}


def _norm01(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    lo = float(np.percentile(a, 2.0))
    hi = float(np.percentile(a, 98.0))
    if not math.isfinite(lo) or not math.isfinite(hi) or hi - lo < 1e-6:
        return np.zeros_like(a, dtype=np.float32)
    return np.clip((a - lo) / (hi - lo), 0.0, 1.0)


def _weighted_quantile_axis(weights: np.ndarray, q: float) -> int:
    c = np.cumsum(np.maximum(weights.astype(np.float64), 0.0))
    total = float(c[-1]) if len(c) else 0.0
    if total <= 1e-12:
        return max(0, min(len(weights) - 1, int(round(q * max(0, len(weights) - 1)))))
    return int(np.searchsorted(c, total * q, side="left"))


def _zone_score(saliency: np.ndarray, rect: tuple[float, float, float, float]) -> float:
    h, w = saliency.shape
    x0, y0, x1, y1 = rect
    xa = max(0, min(w - 1, int(round(x0 * w))))
    xb = max(xa + 1, min(w, int(round(x1 * w))))
    ya = max(0, min(h - 1, int(round(y0 * h))))
    yb = max(ya + 1, min(h, int(round(y1 * h))))
    patch = saliency[ya:yb, xa:xb]
    if patch.size == 0:
        return 1.0
    # A few highly salient pixels (eyes, face edges, text) matter more than plain mean.
    return float(0.72 * patch.mean() + 0.28 * np.percentile(patch, 85.0))


def choose_caption_zone(visual: dict | None, *, text_length: int = 0) -> str:
    visual = visual or {}
    scores = visual.get("zone_scores") or {}
    if not scores:
        fx = float(visual.get("focus_x", 0.5))
        fy = float(visual.get("focus_y", 0.5))
        if text_length >= 28:
            return "top" if fy > 0.58 else "bottom"
        if fx < 0.42:
            return "top_right" if fy > 0.56 else "bottom_right"
        if fx > 0.58:
            return "top_left" if fy > 0.56 else "bottom_left"
        return "top" if fy > 0.60 else "bottom"

    if text_length >= 28:
        candidates = ["top", "bottom"]
    else:
        candidates = ["top_left", "top_right", "bottom_left", "bottom_right", "top", "bottom", "left", "right"]

    fx = float(visual.get("focus_x", 0.5))
    fy = float(visual.get("focus_y", 0.5))
    centers = {
        name: ((r[0] + r[2]) * 0.5, (r[1] + r[3]) * 0.5)
        for name, r in _ZONE_RECTS.items()
    }
    # Prefer visually quiet regions and, on ties, regions farther from the focus centroid.
    ranked = []
    for name in candidates:
        quiet = float(scores.get(name, 1.0))
        cx, cy = centers[name]
        distance = math.hypot(cx - fx, cy - fy) / math.sqrt(2.0)
        cost = quiet + 0.12 * (1.0 - distance)
        # Slightly discourage middle-edge slots unless they are materially safer.
        if name in {"left", "right"}:
            cost += 0.035
        ranked.append((cost, name))
    ranked.sort()
    return ranked[0][1]


def analyze_image(image: Image.Image) -> dict:
    im = image.convert("RGB")
    ow, oh = im.size
    work = im.copy()
    work.thumbnail((320, 320), Image.Resampling.LANCZOS)
    arr = np.asarray(work, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]

    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    sat = arr.max(axis=2) - arr.min(axis=2)
    blur_img = Image.fromarray(np.uint8(np.clip(lum * 255.0, 0, 255)), mode="L").filter(
        ImageFilter.GaussianBlur(radius=max(1.5, min(w, h) / 48.0))
    )
    blur = np.asarray(blur_img, dtype=np.float32) / 255.0
    contrast = np.abs(lum - blur)

    gx = np.zeros_like(lum)
    gy = np.zeros_like(lum)
    gx[:, 1:] = np.abs(lum[:, 1:] - lum[:, :-1])
    gy[1:, :] = np.abs(lum[1:, :] - lum[:-1, :])
    edge = np.hypot(gx, gy)

    edge_n = _norm01(edge)
    contrast_n = _norm01(contrast)
    sat_n = _norm01(sat)
    sal = 0.52 * edge_n + 0.32 * contrast_n + 0.16 * sat_n

    # A weak center prior stabilizes noisy backgrounds without forcing genuinely off-center
    # subjects back to the middle.
    yy, xx = np.mgrid[0:h, 0:w]
    xn = (xx + 0.5) / max(1.0, float(w))
    yn = (yy + 0.5) / max(1.0, float(h))
    center_prior = np.exp(-(((xn - 0.5) / 0.46) ** 2 + ((yn - 0.5) / 0.46) ** 2))
    sal = np.clip(sal * (0.84 + 0.16 * center_prior), 0.0, None)

    strength = float(np.percentile(sal, 90.0) - np.percentile(sal, 35.0))
    if not math.isfinite(strength) or float(sal.max()) < 1e-5:
        focus_x = focus_y = 0.5
        bbox = [0.20, 0.20, 0.80, 0.80]
        confidence = 0.0
    else:
        floor = float(np.percentile(sal, 56.0))
        weights = np.maximum(sal - floor, 0.0) ** 1.35
        total = float(weights.sum())
        if total <= 1e-9:
            weights = sal + 1e-9
            total = float(weights.sum())
        focus_x = float((weights * xn).sum() / total)
        focus_y = float((weights * yn).sum() / total)

        wx = weights.sum(axis=0)
        wy = weights.sum(axis=1)
        x0 = _weighted_quantile_axis(wx, 0.08) / max(1.0, float(w))
        x1 = (_weighted_quantile_axis(wx, 0.92) + 1) / max(1.0, float(w))
        y0 = _weighted_quantile_axis(wy, 0.08) / max(1.0, float(h))
        y1 = (_weighted_quantile_axis(wy, 0.92) + 1) / max(1.0, float(h))
        bbox = [float(np.clip(x0, 0, 1)), float(np.clip(y0, 0, 1)), float(np.clip(x1, 0, 1)), float(np.clip(y1, 0, 1))]
        # Confidence measures useful saliency separation, not semantic certainty.
        confidence = float(np.clip(strength / 0.34, 0.0, 1.0))

    sal_n = _norm01(sal)
    zone_scores = {name: round(_zone_score(sal_n, rect), 5) for name, rect in _ZONE_RECTS.items()}
    out = {
        "focus_x": round(float(np.clip(focus_x, 0, 1)), 5),
        "focus_y": round(float(np.clip(focus_y, 0, 1)), 5),
        "subject_bbox": [round(v, 5) for v in bbox],
        "confidence": round(confidence, 5),
        "zone_scores": zone_scores,
        "source_width": int(ow),
        "source_height": int(oh),
        "method": "deterministic_saliency_v1",
    }
    out["caption_zone"] = choose_caption_zone(out)
    return out


def analyze_image_path(path: str | Path) -> dict:
    path = Path(path)
    try:
        with Image.open(path) as im:
            return analyze_image(im)
    except Exception as exc:
        raise AgentCutError("VISUAL_ANALYSIS_FAILED", "Could not analyze image", path=str(path), error=str(exc)) from exc


def _extract_video_frame(path: Path, output: Path, time_seconds: float) -> None:
    ffmpeg = ensure_binary("ffmpeg")
    run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{max(0.0, float(time_seconds)):.6f}", "-i", str(path),
        "-frames:v", "1", str(output),
    ])


def analyze_video_path(
    path: str | Path,
    *,
    source_in: float = 0.0,
    source_span: float | None = None,
    duration: float | None = None,
    sample_count: int = 3,
) -> dict:
    path = Path(path)
    sample_count = max(1, min(7, int(sample_count)))
    source_in = max(0.0, float(source_in))
    if source_span is None:
        source_span = max(0.0, float(duration or 0.0) - source_in)
    source_span = max(0.0, float(source_span))

    if source_span <= 0.05:
        fractions = [0.0]
    elif sample_count == 1:
        fractions = [0.5]
    else:
        fractions = np.linspace(0.10, 0.90, sample_count).tolist()

    samples = []
    with tempfile.TemporaryDirectory(prefix="agentcut_visual_") as td:
        td = Path(td)
        for i, frac in enumerate(fractions):
            when = source_in + source_span * float(frac)
            frame = td / f"frame_{i:02d}.png"
            _extract_video_frame(path, frame, when)
            row = analyze_image_path(frame)
            row["source_time"] = round(when, 5)
            row["t"] = round(float(frac), 5)
            samples.append(row)

    if not samples:
        raise AgentCutError("VISUAL_ANALYSIS_FAILED", "No video frames were available for analysis", path=str(path))

    # Confidence-weighted centroid; never let one weak/flat frame dominate.
    ws = np.array([0.20 + float(s.get("confidence", 0.0)) for s in samples], dtype=np.float64)
    xs = np.array([float(s["focus_x"]) for s in samples], dtype=np.float64)
    ys = np.array([float(s["focus_y"]) for s in samples], dtype=np.float64)
    fx = float(np.average(xs, weights=ws))
    fy = float(np.average(ys, weights=ws))
    movement = float(math.hypot(float(np.std(xs)), float(np.std(ys))))

    # Aggregate safe-caption occupancy so titles do not jump between frames.
    zone_scores = {}
    for name in _ZONE_RECTS:
        vals = [float((s.get("zone_scores") or {}).get(name, 1.0)) for s in samples]
        zone_scores[name] = round(float(np.mean(vals)), 5)

    bboxes = np.array([s["subject_bbox"] for s in samples], dtype=np.float64)
    bbox = [
        float(np.min(bboxes[:, 0])), float(np.min(bboxes[:, 1])),
        float(np.max(bboxes[:, 2])), float(np.max(bboxes[:, 3])),
    ]
    confidence = float(np.mean([float(s.get("confidence", 0.0)) for s in samples]))
    result = {
        "focus_x": round(fx, 5),
        "focus_y": round(fy, 5),
        "subject_bbox": [round(float(np.clip(v, 0, 1)), 5) for v in bbox],
        "confidence": round(confidence, 5),
        "movement": round(movement, 5),
        "zone_scores": zone_scores,
        "samples": samples,
        "method": "deterministic_saliency_v1",
    }
    result["caption_zone"] = choose_caption_zone(result)
    # Tracking only activates above a conservative threshold. Large discontinuous jumps are
    # more likely to be an internal edit / saliency handoff than a camera move; turning those
    # into a synthetic pan would look worse than a stable crop.
    steps = [math.hypot(float(xs[i]) - float(xs[i-1]), float(ys[i]) - float(ys[i-1])) for i in range(1, len(xs))]
    max_step = max(steps, default=0.0)
    result["max_focus_step"] = round(float(max_step), 5)
    if movement >= 0.045 and len(samples) >= 2 and max_step <= 0.36:
        result["focus_path"] = [
            {"t": round(float(s["t"]), 5), "x": float(s["focus_x"]), "y": float(s["focus_y"])}
            for s in samples
        ]
        result["tracking_reason"] = "continuous_subject_motion"
    else:
        result["focus_path"] = []
        result["tracking_reason"] = "stable_focus" if movement < 0.045 else "discontinuous_focus_guard"
    return result


def suggest_visual_anchors(path: str | Path, *, count: int | None = None) -> dict:
    """Suggest left-to-right visual subject anchors without assigning identities.

    This is deliberately a low-level visual helper, not a face/person classifier. It finds
    separated saliency columns and returns confidence so AgentCut can refuse weak automatic
    staging rather than silently attaching the wrong character name to a location.
    """
    path = Path(path)
    try:
        with Image.open(path) as image:
            im = image.convert("RGB")
            work = im.copy(); work.thumbnail((384, 320), Image.Resampling.LANCZOS)
    except Exception as exc:
        raise AgentCutError("VISUAL_ANALYSIS_FAILED", "Could not open image for staging analysis", path=str(path), error=str(exc)) from exc
    arr = np.asarray(work, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    lum = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
    sat = arr.max(axis=2) - arr.min(axis=2)
    blur_img = Image.fromarray(np.uint8(np.clip(lum * 255.0, 0, 255)), mode="L").filter(ImageFilter.GaussianBlur(radius=max(1.5, min(w, h) / 48.0)))
    blur = np.asarray(blur_img, dtype=np.float32) / 255.0
    contrast = np.abs(lum - blur)
    gx = np.zeros_like(lum); gy = np.zeros_like(lum)
    gx[:, 1:] = np.abs(lum[:, 1:] - lum[:, :-1]); gy[1:, :] = np.abs(lum[1:, :] - lum[:-1, :])
    edge = np.hypot(gx, gy)
    sal = 0.56 * _norm01(edge) + 0.30 * _norm01(contrast) + 0.14 * _norm01(sat)
    # De-emphasize extreme top/bottom UI-like edges; dynamic-manga characters usually occupy the middle band.
    yy = (np.arange(h, dtype=np.float32) + .5) / max(1.0, float(h))
    vertical_prior = np.exp(-((yy - .52) / .40) ** 4)[:, None]
    sal = np.clip(sal * (0.62 + 0.38 * vertical_prior), 0.0, None)
    profile = sal.sum(axis=0)
    kernel = max(5, int(round(w * 0.055)))
    if kernel % 2 == 0: kernel += 1
    smooth = np.convolve(profile, np.ones(kernel, dtype=np.float32) / kernel, mode="same")
    smooth = _norm01(smooth)

    requested = None if count is None else max(1, min(8, int(count)))
    candidate_idx = [i for i in range(1, w - 1) if smooth[i] >= smooth[i-1] and smooth[i] >= smooth[i+1]]
    candidate_idx.sort(key=lambda i: float(smooth[i]), reverse=True)
    target = requested or min(4, max(1, sum(float(smooth[i]) >= 0.48 for i in candidate_idx)))
    min_sep = max(8, int(w / max(4.2, target * 1.55)))
    peaks = []
    for idx in candidate_idx:
        if float(smooth[idx]) < (0.30 if requested else 0.42):
            continue
        if all(abs(idx - other) >= min_sep for other in peaks):
            peaks.append(idx)
        if len(peaks) >= target:
            break
    if requested and len(peaks) < requested:
        # Deterministic fallback: fill missing slots from strongest non-overlapping columns.
        for idx in np.argsort(smooth)[::-1].tolist():
            if all(abs(int(idx) - other) >= max(5, int(min_sep * .65)) for other in peaks):
                peaks.append(int(idx))
            if len(peaks) >= requested:
                break
    peaks = sorted(peaks[:target])
    if not peaks:
        base = analyze_image(work)
        return {"anchors": [{"x": base["focus_x"], "y": base["focus_y"], "score": base["confidence"]}], "confidence": float(base["confidence"]) * .45, "method": "saliency_anchor_v1", "requested_count": requested}

    boundaries = [0]
    for a, b in zip(peaks[:-1], peaks[1:]): boundaries.append(int(round((a + b) * .5)))
    boundaries.append(w)
    anchors = []
    peak_scores = []
    for j, peak in enumerate(peaks):
        xa, xb = boundaries[j], boundaries[j+1]
        region = sal[:, xa:xb]
        floor = float(np.percentile(region, 60.0)) if region.size else 0.0
        weights = np.maximum(region - floor, 0.0) ** 1.25
        total = float(weights.sum())
        if total <= 1e-8:
            x = (peak + .5) / w; y = .52
        else:
            ry, rx = np.mgrid[0:h, xa:xb]
            x = float((weights * ((rx + .5) / w)).sum() / total)
            y = float((weights * ((ry + .5) / h)).sum() / total)
        # For character staging the useful camera target is usually face/upper torso, not the
        # saliency centroid of the entire silhouette. Blend upward conservatively rather than
        # hard-clamping, so crouched/low subjects can still remain low in frame.
        y = 0.67 * float(y) + 0.33 * 0.46
        score = float(smooth[peak]); peak_scores.append(score)
        anchors.append({"x": round(float(np.clip(x,0,1)), 5), "y": round(float(np.clip(y,0,1)), 5), "score": round(score, 4)})
    separation = min([anchors[i+1]["x"] - anchors[i]["x"] for i in range(len(anchors)-1)] or [0.5])
    confidence = float(np.clip((np.mean(peak_scores) * .72) + min(1.0, separation * max(2, len(anchors))) * .28, 0, 1))
    return {"anchors": anchors, "confidence": round(confidence, 4), "method": "saliency_anchor_v1", "requested_count": requested, "detected_count": len(anchors), "focus_bias": "upper_body_conservative"}
