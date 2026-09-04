from __future__ import annotations

import math
import re
from copy import deepcopy

from .composition import caption_zone_for_focus
from .errors import AgentCutError
from .subtitles import SUBTITLE_STYLES

DIALOGUE_PACES = {
    "slow": 4.2,
    "normal": 5.6,
    "fast": 7.0,
    "snappy": 8.2,
}

DIALOGUE_STYLES = set(SUBTITLE_STYLES)
PERFORMANCE_STYLES = {"anime_band", "dialogue", "reaction", "calm"}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def normalize_color(value: str | None, default: str = "#FFFFFF") -> str:
    raw = str(value or default).strip()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", raw):
        raise AgentCutError("INVALID_CHARACTER_COLOR", "Character color must be #RRGGBB", color=value)
    return raw.upper()


def text_read_units(text: str) -> float:
    """Approximate readable units across CJK and Latin text without external NLP deps."""
    s = str(text or "").strip()
    if not s:
        return 0.0
    cjk = len(re.findall(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", s))
    latin_words = len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", s))
    punctuation = len(re.findall(r"[,，。.!！？?…:：;；、]", s))
    other = max(0, len(re.sub(r"\s", "", s)) - cjk - sum(len(x) for x in re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", s)) - punctuation)
    return cjk + latin_words * 1.7 + punctuation * 0.22 + other * 0.55


def estimate_dialogue_duration(text: str, *, pace: str = "normal", minimum: float = 0.78, maximum: float = 7.5) -> float:
    key = str(pace).strip().lower()
    if key not in DIALOGUE_PACES:
        raise AgentCutError("INVALID_DIALOGUE_PACE", "Unknown dialogue pace", pace=pace, allowed=sorted(DIALOGUE_PACES))
    units = text_read_units(text)
    # Short lines still need perceptual dwell time; punctuation naturally adds a little weight.
    duration = 0.34 + units / DIALOGUE_PACES[key]
    return round(_clamp(duration, minimum, maximum), 3)


def resolve_character(cast: dict, *, character_id: str | None = None, speaker: str | None = None) -> tuple[str | None, dict | None]:
    if character_id:
        row = cast.get(str(character_id))
        if row is None:
            raise AgentCutError("CHARACTER_NOT_FOUND", "Unknown character", character_id=character_id, available=sorted(cast))
        return str(character_id), row
    if not speaker:
        return None, None
    needle = str(speaker).strip().casefold()
    matches = []
    for cid, row in cast.items():
        names = [cid, row.get("display_name", cid), *(row.get("aliases") or [])]
        if any(str(x).strip().casefold() == needle for x in names if x is not None):
            matches.append((cid, row))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AgentCutError("AMBIGUOUS_CHARACTER", "Speaker name matches multiple cast entries", speaker=speaker, matches=[x[0] for x in matches])
    return None, None


def normalize_dialogue_line(line, *, cast: dict, pace: str, default_style: str = "band") -> dict:
    if isinstance(line, str):
        raw = line.strip()
        # Accept low-structure script lines such as "虹夏：开始吧" when the prefix is a known cast label.
        m = re.match(r"^([^：:]{1,24})[：:]\s*(.+)$", raw)
        if m:
            maybe_speaker, body = m.group(1).strip(), m.group(2).strip()
            try:
                cid, char = resolve_character(cast, speaker=maybe_speaker)
            except AgentCutError:
                cid, char = None, None
            line = {"speaker": maybe_speaker, "text": body} if cid else {"text": raw}
        else:
            line = {"text": raw}
    if not isinstance(line, dict):
        raise AgentCutError("INVALID_DIALOGUE_LINE", "Dialogue lines must be strings or objects", value_type=type(line).__name__)
    text = str(line.get("text", line.get("line", line.get("台词", line.get("内容", ""))))).strip()
    if not text:
        raise AgentCutError("INVALID_DIALOGUE_LINE", "Dialogue line text cannot be empty")
    speaker = line.get("speaker", line.get("name", line.get("角色", line.get("说话人"))))
    character_id = line.get("character_id", line.get("character", line.get("member", line.get("角色id"))))
    character_id, character = resolve_character(cast, character_id=character_id, speaker=speaker)
    if line.get("speaker_label") is not None:
        speaker = str(line.get("speaker_label"))
    elif character is not None:
        speaker = character.get("display_name") or character_id
    style = str(line.get("subtitle_style", line.get("style", default_style))).strip().lower()
    emotion = str(line.get("emotion", "neutral")).strip().lower()
    if style not in DIALOGUE_STYLES:
        raise AgentCutError("INVALID_DIALOGUE_STYLE", "Unknown dialogue subtitle style", style=style, allowed=sorted(DIALOGUE_STYLES))
    duration = line.get("duration")
    if duration is None:
        duration = estimate_dialogue_duration(text, pace=pace)
    else:
        try:
            duration = float(duration)
        except (TypeError, ValueError) as exc:
            raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue line duration must be numeric", duration=duration) from exc
        if not math.isfinite(duration) or duration <= 0:
            raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue line duration must be > 0", duration=duration)
    position = line.get("position")
    if position in (None, "auto"):
        if character and character.get("subtitle_position") not in (None, "auto"):
            position = character["subtitle_position"]
        elif character:
            position = caption_zone_for_focus(float(character.get("focus_x", 0.5)), float(character.get("focus_y", 0.5)), text_length=len(text))
        else:
            position = "bottom"
    return {
        "text": text,
        "speaker": speaker,
        "character_id": character_id,
        "character": deepcopy(character),
        "audio_asset_id": line.get("audio_asset_id", line.get("audio")),
        "duration": round(float(duration), 3),
        "position": position,
        "font_size": int(line.get("font_size", 54)),
        "outline": int(line.get("outline", 3)),
        "volume_db": float(line.get("volume_db", 0.0)),
        "subtitle_style": style,
        "emotion": emotion,
        "max_line_chars": int(line.get("max_line_chars", 18)),
        "secondary_text": str(line.get("secondary_text", line.get("translation", line.get("译文", ""))) or "").strip() or None,
        "secondary_language": str(line.get("secondary_language", line.get("translation_language", "en")) or "en"),
        "secondary_font_scale": float(line.get("secondary_font_scale", 0.72)),
    }


def plan_dialogue_sequence(lines, *, cast: dict, start: float = 0.0, gap: float = 0.10, pace: str = "normal", default_style: str = "band") -> dict:
    try:
        cursor = float(start)
        gap = float(gap)
    except (TypeError, ValueError) as exc:
        raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue sequence start/gap must be numeric") from exc
    if cursor < 0 or gap < 0:
        raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue sequence start/gap must be >= 0", start=cursor, gap=gap)
    normalized = []
    for idx, raw in enumerate(lines or []):
        row = normalize_dialogue_line(raw, cast=cast, pace=pace, default_style=default_style)
        row["start"] = round(cursor, 3)
        row["index"] = idx
        normalized.append(row)
        cursor += float(row["duration"]) + gap
    if not normalized:
        raise AgentCutError("EMPTY_DIALOGUE_SEQUENCE", "Dialogue sequence needs at least one line")
    end = normalized[-1]["start"] + normalized[-1]["duration"]
    return {"lines": normalized, "start": float(start), "end": round(end, 3), "duration": round(end - float(start), 3), "gap": gap, "pace": pace}


def _compress_focus_points(points: list[dict], limit: int = 12) -> list[dict]:
    if len(points) <= limit:
        return points
    if limit < 2:
        return points[:limit]
    keep = [points[0]]
    for i in range(1, limit - 1):
        idx = round(i * (len(points) - 1) / (limit - 1))
        keep.append(points[idx])
    keep.append(points[-1])
    out = []
    for row in keep:
        if not out or row != out[-1]:
            out.append(row)
    return out


def dialogue_focus_path(sequence: dict, *, scene_duration: float, default_focus=(0.5, 0.5), anticipation: float = 0.07) -> list[dict]:
    if scene_duration <= 1e-6:
        return []
    points = []
    last_focus = (float(default_focus[0]), float(default_focus[1]))
    for row in sequence.get("lines", []):
        char = row.get("character") or {}
        focus = (float(char.get("focus_x", last_focus[0])), float(char.get("focus_y", last_focus[1])))
        start = float(row["start"])
        dur = float(row["duration"])
        # Hold the previous speaker until just before the next line, then glide to the new one.
        pre = max(0.0, start - min(anticipation, dur * 0.18))
        mid = min(scene_duration, start + min(dur * 0.38, 0.55))
        points.append({"t": _clamp(pre / scene_duration, 0, 1), "x": _clamp(last_focus[0], 0, 1), "y": _clamp(last_focus[1], 0, 1)})
        points.append({"t": _clamp(mid / scene_duration, 0, 1), "x": _clamp(focus[0], 0, 1), "y": _clamp(focus[1], 0, 1)})
        last_focus = focus
    if points:
        points[0]["t"] = 0.0
        if points[-1]["t"] < 1.0:
            points.append({"t": 1.0, "x": points[-1]["x"], "y": points[-1]["y"]})
    points.sort(key=lambda x: x["t"])
    return _compress_focus_points(points, 12)


def performance_focus_path(cast: dict, member_ids: list[str] | None, *, energy: float, points: int = 7) -> list[dict]:
    energy = _clamp(energy, 0.0, 1.0)
    ids = [str(x) for x in (member_ids or []) if str(x) in cast]
    if not ids:
        ids = list(cast.keys())
    if not ids:
        return []
    points = max(3, min(12, int(points)))
    # Deterministic alternating sweep: avoids random camera behavior across rerenders.
    order = []
    seq = ids + list(reversed(ids[1:-1] if len(ids) > 2 else ids))
    if not seq:
        seq = ids
    for i in range(points):
        cid = seq[i % len(seq)]
        row = cast[cid]
        order.append({"t": round(i / (points - 1), 4), "x": float(row.get("focus_x", 0.5)), "y": float(row.get("focus_y", 0.5)), "character_id": cid})
    return order
