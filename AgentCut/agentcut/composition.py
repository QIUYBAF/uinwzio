from __future__ import annotations

from copy import deepcopy

from .errors import AgentCutError
from .visual import choose_caption_zone

COMPOSITION_MODES = {"cover", "contain", "native_window", "ambient"}
BACKGROUND_STYLES = {"black", "blur", "dim_blur"}
CAPTION_ZONES = {
    "top_left", "top", "top_right", "left", "center", "right",
    "bottom_left", "bottom", "bottom_right",
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def _dims(asset: dict) -> tuple[int | None, int | None]:
    meta = asset.get("metadata") or {}
    try:
        if asset.get("type") == "image":
            return int(meta.get("width")), int(meta.get("height"))
        streams = meta.get("streams") or []
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        if video:
            return int(video.get("width")), int(video.get("height"))
        if meta.get("width") and meta.get("height"):
            return int(meta["width"]), int(meta["height"])
    except (TypeError, ValueError):
        pass
    return None, None


def _visual(asset: dict, supplied: dict | None = None) -> dict:
    if supplied:
        return supplied
    return ((asset.get("metadata") or {}).get("visual") or {})


def _focus(asset: dict, visual: dict | None = None) -> tuple[float, float]:
    tags = asset.get("tags") or {}
    vis = _visual(asset, visual)
    # Explicit user/agent tags override inferred saliency. This keeps artistic intent above
    # automated analysis and makes the system easy to correct when saliency is wrong.
    try:
        fx = tags.get("focus_x", vis.get("focus_x", 0.5))
        fy = tags.get("focus_y", vis.get("focus_y", 0.5))
        return _clamp(float(fx), 0.0, 1.0), _clamp(float(fy), 0.0, 1.0)
    except (TypeError, ValueError):
        return 0.5, 0.5


def caption_zone_for_focus(focus_x: float, focus_y: float, *, text_length: int = 0) -> str:
    # Compatibility fallback when no saliency map is available.
    if text_length >= 28:
        return "top" if focus_y > 0.58 else "bottom"
    if focus_x < 0.40:
        return "top_right" if focus_y > 0.55 else "bottom_right"
    if focus_x > 0.60:
        return "top_left" if focus_y > 0.55 else "bottom_left"
    return "top" if focus_y > 0.60 else "bottom"


def _subject_crop_risk(visual: dict, source_ar: float, target_ar: float) -> bool:
    bbox = visual.get("subject_bbox") or []
    confidence = float(visual.get("confidence", 0.0) or 0.0)
    if len(bbox) != 4 or confidence < 0.18:
        return False
    try:
        x0, y0, x1, y1 = [_clamp(float(v), 0.0, 1.0) for v in bbox]
    except (TypeError, ValueError):
        return False
    bw, bh = max(0.0, x1 - x0), max(0.0, y1 - y0)
    if source_ar > target_ar:
        visible = target_ar / source_ar
        return visible < 0.92 and bw > visible * 0.93
    visible = source_ar / target_ar
    return visible < 0.92 and bh > visible * 0.93


def plan_composition(
    asset: dict,
    target_width: int,
    target_height: int,
    *,
    text_hint: str = "",
    visual: dict | None = None,
) -> dict:
    sw, sh = _dims(asset)
    vis = _visual(asset, visual)
    fx, fy = _focus(asset, vis)
    target_ar = float(target_width) / float(target_height)
    visual_caption = choose_caption_zone({**vis, "focus_x": fx, "focus_y": fy}, text_length=len(text_hint)) if vis else None
    caption_zone = visual_caption or caption_zone_for_focus(fx, fy, text_length=len(text_hint))

    base = {
        "focus_x": round(fx, 4),
        "focus_y": round(fy, 4),
        "caption_zone": caption_zone,
    }
    if vis:
        if vis.get("focus_path"):
            base["focus_path"] = deepcopy(vis["focus_path"])
        if vis.get("subject_bbox"):
            base["subject_bbox"] = deepcopy(vis["subject_bbox"])
        if vis.get("zone_scores"):
            base["safe_zones"] = [name for name, _ in sorted(vis["zone_scores"].items(), key=lambda kv: float(kv[1]))[:4]]
        base["visual_confidence"] = round(float(vis.get("confidence", 0.0) or 0.0), 4)
        base["analysis_source"] = str(vis.get("method", "visual"))

    if not sw or not sh:
        return {
            "mode": "cover", "background": "black", "frame_scale": 1.0,
            **base,
            "reason": "source_geometry_unknown",
        }

    source_ar = float(sw) / float(sh)
    aspect_mismatch = max(source_ar / target_ar, target_ar / source_ar)
    resolution_ratio = min(float(sw) / target_width, float(sh) / target_height)
    crop_risk = _subject_crop_risk(vis, source_ar, target_ar)

    if resolution_ratio < 0.72:
        mode = "ambient"
        background = "dim_blur"
        frame_scale = _clamp(0.70 + 0.16 * resolution_ratio, 0.66, 0.82)
        reason = "low_resolution_preserve_detail"
    elif crop_risk and aspect_mismatch > 1.06:
        # If saliency indicates meaningful content spans the area a cover crop would remove,
        # preserve it rather than forcing a technically full-bleed but artistically damaged frame.
        mode = "native_window"
        background = "black"
        frame_scale = 0.97
        reason = "subject_crop_risk"
    elif aspect_mismatch > 1.18:
        mode = "native_window"
        background = "black"
        frame_scale = 0.96
        reason = "preserve_native_aspect_ratio"
    else:
        mode = "cover"
        background = "black"
        frame_scale = 1.0
        reason = "focus_aware_cover" if vis or (asset.get("tags") or {}).get("focus_x") is not None else "source_matches_canvas"

    return {
        "mode": mode,
        "background": background,
        "frame_scale": round(frame_scale, 4),
        **base,
        "source_width": sw,
        "source_height": sh,
        "source_aspect": round(source_ar, 6),
        "target_aspect": round(target_ar, 6),
        "reason": reason,
    }


def _validate_focus_path(value) -> list[dict]:
    if value in (None, []):
        return []
    if not isinstance(value, list) or len(value) > 12:
        raise AgentCutError("INVALID_COMPOSITION", "focus_path must be a list with at most 12 points")
    out = []
    previous_t = -1.0
    for row in value:
        if not isinstance(row, dict):
            raise AgentCutError("INVALID_COMPOSITION", "focus_path points must be objects")
        t = _clamp(float(row.get("t", 0.0)), 0.0, 1.0)
        x = _clamp(float(row.get("x", 0.5)), 0.0, 1.0)
        y = _clamp(float(row.get("y", 0.5)), 0.0, 1.0)
        if t < previous_t:
            raise AgentCutError("INVALID_COMPOSITION", "focus_path must be sorted by t")
        previous_t = t
        out.append({"t": t, "x": x, "y": y})
    return out


def validate_composition(spec: dict | None) -> dict:
    spec = deepcopy(spec or {})
    mode = str(spec.get("mode", "cover"))
    if mode not in COMPOSITION_MODES:
        raise AgentCutError("INVALID_COMPOSITION", "Unsupported composition mode", mode=mode, allowed=sorted(COMPOSITION_MODES))
    background = str(spec.get("background", "black"))
    if background not in BACKGROUND_STYLES:
        raise AgentCutError("INVALID_COMPOSITION", "Unsupported composition background", background=background, allowed=sorted(BACKGROUND_STYLES))
    frame_scale = float(spec.get("frame_scale", 1.0))
    if not 0.35 <= frame_scale <= 1.0:
        raise AgentCutError("INVALID_COMPOSITION", "frame_scale must be in [0.35, 1.0]", frame_scale=frame_scale)
    crop_zoom = float(spec.get("crop_zoom", 1.0))
    if not 1.0 <= crop_zoom <= 3.0:
        raise AgentCutError("INVALID_COMPOSITION", "crop_zoom must be in [1.0, 3.0]", crop_zoom=crop_zoom)
    fx = _clamp(float(spec.get("focus_x", 0.5)), 0.0, 1.0)
    fy = _clamp(float(spec.get("focus_y", 0.5)), 0.0, 1.0)
    zone = str(spec.get("caption_zone", "bottom"))
    if zone not in CAPTION_ZONES:
        raise AgentCutError("INVALID_COMPOSITION", "Unsupported caption zone", caption_zone=zone, allowed=sorted(CAPTION_ZONES))
    focus_path = _validate_focus_path(spec.get("focus_path"))

    bbox = spec.get("subject_bbox")
    if bbox is not None:
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise AgentCutError("INVALID_COMPOSITION", "subject_bbox must be [x0,y0,x1,y1]")
        bbox = [_clamp(float(v), 0.0, 1.0) for v in bbox]
        if bbox[2] < bbox[0] or bbox[3] < bbox[1]:
            raise AgentCutError("INVALID_COMPOSITION", "subject_bbox bounds are inverted", subject_bbox=bbox)

    safe_zones = spec.get("safe_zones")
    if safe_zones is not None:
        if not isinstance(safe_zones, list) or any(str(z) not in CAPTION_ZONES for z in safe_zones):
            raise AgentCutError("INVALID_COMPOSITION", "safe_zones contains an unsupported zone")
        safe_zones = [str(z) for z in safe_zones[:9]]

    out = {
        **spec,
        "mode": mode,
        "background": background,
        "frame_scale": frame_scale,
        "crop_zoom": crop_zoom,
        "focus_x": fx,
        "focus_y": fy,
        "caption_zone": zone,
        "focus_path": focus_path,
    }
    if bbox is not None:
        out["subject_bbox"] = bbox
    if safe_zones is not None:
        out["safe_zones"] = safe_zones
    if "visual_confidence" in spec:
        out["visual_confidence"] = _clamp(float(spec["visual_confidence"]), 0.0, 1.0)
    if "analysis_source" in spec:
        out["analysis_source"] = str(spec["analysis_source"])
    return out
