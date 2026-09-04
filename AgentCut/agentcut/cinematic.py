from __future__ import annotations

from copy import deepcopy

from .errors import AgentCutError

FRAME_EASINGS = {"linear", "smooth", "snap"}
FRAME_PRESETS = {
    "scope_lock": [
        {"t": 0.0, "aspect": 16 / 9},
        {"t": 0.32, "aspect": 16 / 9},
        {"t": 0.58, "aspect": 2.39},
        {"t": 1.0, "aspect": 2.39},
    ],
    "scope_reveal": [
        {"t": 0.0, "aspect": 2.39},
        {"t": 0.42, "aspect": 2.39},
        {"t": 0.72, "aspect": 16 / 9},
        {"t": 1.0, "aspect": 16 / 9},
    ],
    "impact_pulse": [
        {"t": 0.0, "aspect": 16 / 9},
        {"t": 0.16, "aspect": 2.39},
        {"t": 0.52, "aspect": 2.39},
        {"t": 0.74, "aspect": 2.0},
        {"t": 1.0, "aspect": 16 / 9},
    ],
    "scope_hold": [
        {"t": 0.0, "aspect": 2.39},
        {"t": 1.0, "aspect": 2.39},
    ],
}

FRAGMENT_STYLES = {"impact_cluster", "detail_burst", "memory_shards"}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def validate_frame_path(path, *, canvas_aspect: float | None = None) -> list[dict]:
    if path in (None, []):
        return []
    if not isinstance(path, list) or len(path) > 16:
        raise AgentCutError("INVALID_CINEMATIC_FRAME", "frame_path must be a list with at most 16 points")
    out = []
    previous_t = -1.0
    min_aspect = float(canvas_aspect) if canvas_aspect else 1.0
    for row in path:
        if not isinstance(row, dict):
            raise AgentCutError("INVALID_CINEMATIC_FRAME", "frame_path points must be objects")
        t = _clamp(float(row.get("t", 0.0)), 0.0, 1.0)
        aspect = float(row.get("aspect", min_aspect))
        if t < previous_t:
            raise AgentCutError("INVALID_CINEMATIC_FRAME", "frame_path must be sorted by t")
        if not min_aspect - 1e-6 <= aspect <= 3.2:
            raise AgentCutError(
                "INVALID_CINEMATIC_FRAME",
                "cinematic aspect must be at least the canvas aspect and <= 3.2",
                aspect=aspect,
                minimum=min_aspect,
            )
        previous_t = t
        out.append({"t": round(t, 6), "aspect": round(aspect, 6)})
    if len(out) == 1:
        out.append({"t": 1.0, "aspect": out[0]["aspect"]})
    return out


def validate_cinematic(spec: dict | None, *, canvas_aspect: float | None = None) -> dict:
    spec = deepcopy(spec or {})
    easing = str(spec.get("frame_easing", "smooth"))
    if easing not in FRAME_EASINGS:
        raise AgentCutError("INVALID_CINEMATIC_FRAME", "Unsupported frame easing", easing=easing, allowed=sorted(FRAME_EASINGS))
    frame_path = validate_frame_path(spec.get("frame_path"), canvas_aspect=canvas_aspect)
    treatment = spec.get("treatment")
    if treatment is not None:
        treatment = str(treatment)
    out = {**spec, "frame_path": frame_path, "frame_easing": easing}
    if treatment:
        out["treatment"] = treatment
    if "fragment_group" in out:
        out["fragment_group"] = str(out["fragment_group"])
    if "fragment_index" in out:
        out["fragment_index"] = int(out["fragment_index"])
    if "fragment_count" in out:
        out["fragment_count"] = int(out["fragment_count"])
    return out


def preset_frame_path(preset: str, *, canvas_aspect: float = 16 / 9) -> list[dict]:
    try:
        rows = deepcopy(FRAME_PRESETS[preset])
    except KeyError as exc:
        raise AgentCutError("CINEMATIC_PRESET_NOT_FOUND", "Unknown cinematic frame preset", preset=preset, allowed=sorted(FRAME_PRESETS)) from exc
    # Presets are authored for 16:9. Never request an aspect narrower than the real canvas.
    for row in rows:
        row["aspect"] = max(float(canvas_aspect), float(row["aspect"]))
    return validate_frame_path(rows, canvas_aspect=canvas_aspect)


def fragment_recipe(style: str, *, count: int = 5, intensity: float = 0.75) -> list[dict]:
    """Return deterministic micro-cut semantics, independent of concrete scene state.

    `crop_zoom` is an immediate reframe, not an animated camera move. `focus_dx/dy` are
    intentionally small so the recipe produces details around the known focal point rather
    than randomly abandoning the subject.
    """
    if style not in FRAGMENT_STYLES:
        raise AgentCutError("CINEMATIC_RECIPE_NOT_FOUND", "Unknown fragmentation style", style=style, allowed=sorted(FRAGMENT_STYLES))
    count = int(count)
    if not 3 <= count <= 8:
        raise AgentCutError("INVALID_FRAGMENT_COUNT", "fragment count must be in [3, 8]", count=count)
    intensity = _clamp(float(intensity), 0.0, 1.0)

    if style == "impact_cluster":
        base = [
            (0.32, 1.00, 0.00, 0.00, 16 / 9, 0.00),
            (0.11, 1.35, -0.06, -0.03, 2.39, 0.36),
            (0.10, 1.72, 0.07, 0.02, 2.39, 0.58),
            (0.11, 1.46, 0.00, 0.07, 2.39, 0.44),
            (0.36, 1.08, 0.00, 0.00, 16 / 9, 0.72),
        ]
    elif style == "detail_burst":
        base = [
            (0.38, 1.00, 0.00, 0.00, 16 / 9, 0.00),
            (0.14, 1.28, -0.08, 0.00, 2.00, 0.38),
            (0.12, 1.58, 0.08, -0.04, 2.39, 0.52),
            (0.12, 1.72, 0.00, 0.07, 2.39, 0.63),
            (0.24, 1.16, 0.00, 0.00, 2.00, 0.76),
        ]
    else:  # memory_shards
        base = [
            (0.22, 1.06, 0.00, 0.00, 2.39, 0.00),
            (0.12, 1.42, 0.08, -0.05, 2.39, 0.62),
            (0.14, 1.20, -0.08, 0.03, 2.00, 0.26),
            (0.10, 1.68, 0.02, 0.08, 2.39, 0.78),
            (0.16, 1.35, -0.04, -0.04, 2.39, 0.48),
            (0.26, 1.00, 0.00, 0.00, 16 / 9, 0.86),
        ]

    if count != len(base):
        # Deterministically resample the authored pattern. Nearest-neighbour here is deliberate:
        # fragment grammar should stay punchy instead of blending into generic ramps.
        picked = []
        for i in range(count):
            j = round(i * (len(base) - 1) / max(1, count - 1))
            picked.append(base[j])
        base = picked

    total = sum(row[0] for row in base)
    rows = []
    for ratio, zoom, dx, dy, aspect, source_pos in base:
        rows.append({
            "duration_ratio": ratio / total,
            "crop_zoom": round(1.0 + (zoom - 1.0) * intensity, 4),
            "focus_dx": round(dx * intensity, 4),
            "focus_dy": round(dy * intensity, 4),
            "aspect": round((16 / 9) + (aspect - 16 / 9) * intensity, 6),
            "source_pos": float(source_pos),
        })
    return rows
