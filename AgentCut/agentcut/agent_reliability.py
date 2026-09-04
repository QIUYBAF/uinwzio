from __future__ import annotations

import difflib
import inspect
import re
from copy import deepcopy
from typing import Any

from .errors import AgentCutError
from .libraries import list_items
from .timeline import build_timeline
from .util import hash_obj

# Deterministic aliases only. They repair syntax/naming drift, never artistic choices.
ACTION_ALIASES = {
    "scene_add": "add_scene", "create_scene": "add_scene", "new_scene": "add_scene", "remove_scene": "delete_scene",
    "video_mode": "set_video_mode", "output_mode": "set_video_mode", "resolution_preset": "set_video_mode",
    "camera": "set_camera", "composition": "set_composition", "auto_composition": "apply_auto_composition",
    "reframe": "apply_visual_composition", "auto_reframe": "apply_visual_composition",
    "effect": "add_effect", "filter": "add_filter", "apply_filter": "add_filter",
    "transition": "set_transition", "set_transition_out": "set_transition",
    "motion_preset": "apply_motion_preset", "transition_preset": "apply_transition_preset",
    "effect_preset": "apply_effect_preset", "caption": "add_caption", "dialogue": "add_dialogue_segment",
    "audio": "add_audio_track", "scene_audio": "add_scene_audio", "cinematic": "apply_cinematic_treatment",
    "make_cinematic": "apply_cinematic_treatment", "fragment": "fragment_scene", "cinematic_frame": "set_cinematic_frame",
    "character": "define_character", "cast_member": "define_character", "member": "define_character",
    "stage": "stage_character", "stage_character": "stage_character", "place_character": "stage_character", "角色站位": "stage_character",
    "dialogue_scene": "compose_dialogue_scene", "conversation_scene": "compose_dialogue_scene",
    "dialogue_coverage": "direct_dialogue_coverage", "coverage": "direct_dialogue_coverage", "shot_coverage": "direct_dialogue_coverage",
    "attention": "direct_attention_insert", "attention_insert": "direct_attention_insert", "action_insert": "direct_attention_insert", "object_insert": "direct_attention_insert",
    "anime_dialogue": "compose_dialogue_scene", "band_dialogue": "compose_dialogue_scene",
    "performance": "direct_performance_scene", "performance_scene": "direct_performance_scene",
    "reaction": "direct_reaction_scene", "reaction_shot": "direct_reaction_scene",
    "band_scene": "direct_performance_scene", "anime_band": "direct_performance_scene",
    "band_sequence": "direct_band_sequence", "music_montage": "direct_band_sequence", "performance_sequence": "direct_band_sequence",
    "recipe": "apply_scene_recipe", "scene_recipe": "apply_scene_recipe",
    "对话场景": "compose_dialogue_scene", "对白分镜": "direct_dialogue_coverage", "分镜覆盖": "direct_dialogue_coverage", "动作特写": "direct_attention_insert", "物件特写": "direct_attention_insert", "乐队演奏": "direct_performance_scene",
    "反应特写": "direct_reaction_scene", "场景配方": "apply_scene_recipe", "角色": "define_character",
    "auto_caption": "auto_subtitles", "auto_subtitle": "auto_subtitles", "transcribe": "auto_subtitles",
    "speech_to_text": "auto_subtitles", "字幕识别": "auto_subtitles", "自动字幕": "auto_subtitles",
    "subtitle_import": "import_subtitle_file", "import_srt": "import_subtitle_file",
    "subtitle_optimize": "optimize_subtitle_layout", "fit_subtitles": "optimize_subtitle_layout",
    "gen3_config": "configure_gen3", "jane3_config": "configure_gen3", "third_gen_config": "configure_gen3",
    "gen3_scene": "set_gen3_scene", "jane3_scene": "set_gen3_scene", "third_gen_scene": "set_gen3_scene", "第三代场景": "set_gen3_scene",
    "gen3_card": "set_gen3_card", "jane3_card": "set_gen3_card", "info_card": "set_gen3_card", "介绍卡片": "set_gen3_card",
    "actor_card": "register_gen3_actor_card", "register_actor": "register_gen3_actor_card", "角色卡": "register_gen3_actor_card",
    "place_actor": "place_gen3_actor", "gen3_actor": "place_gen3_actor", "纸片人": "place_gen3_actor",
    "compile_gen3": "compile_gen3", "compile_jane3": "compile_gen3",
    "auto_stage": "stage_scene_by_order", "stage_by_order": "stage_scene_by_order",
}

COMMON_ARG_ALIASES = {
    "scene": "scene_id", "sceneId": "scene_id", "sceneID": "scene_id",
    "asset": "asset_id", "assetId": "asset_id", "assetID": "asset_id",
    "preset": "preset_id", "presetId": "preset_id",
    "layer": "layer_id", "track": "track_id", "caption": "caption_id", "dialogue": "dialogue_id",
    "sourceIn": "source_in", "playbackRate": "playback_rate", "volumeDb": "volume_db",
    "fadeIn": "fade_in", "fadeOut": "fade_out", "fontSize": "font_size",
    "character": "character_id", "characterId": "character_id", "member": "character_id",
    "场景": "scene_id", "角色": "character_id",
}

ACTION_ARG_ALIASES = {
    "set_transition": {"type": "transition", "transition_type": "transition"},
    "set_camera": {"type": "motion", "camera": "motion", "camera_motion": "motion"},
    "add_effect": {"type": "effect"},
    "add_filter": {"filter": "filter_id", "id": "filter_id"},
    "apply_motion_preset": {"motion": "preset_id"},
    "apply_transition_preset": {"transition": "preset_id", "type": "preset_id"},
    "apply_effect_preset": {"effect": "preset_id", "type": "preset_id"},
    "add_scene": {"id": "scene_id"},
    "set_video_mode": {"mode": "preset", "profile": "preset", "resolution": "preset"},
    "compose_dialogue_scene": {"dialogue": "lines", "script": "lines", "台词": "lines", "对白": "lines", "style": "subtitle_style", "motion": "motion_strength"},
    "direct_performance_scene": {"members": "member_ids", "characters": "member_ids", "成员": "member_ids", "intensity": "energy", "music": "rhythm_asset_id", "bgm": "rhythm_asset_id", "音乐": "rhythm_asset_id"},
    "direct_reaction_scene": {"character": "character_id", "speaker": "character_id", "member": "character_id", "角色": "character_id", "energy": "intensity"},
    "direct_dialogue_coverage": {"energy": "intensity", "strength": "intensity", "gap": "reset_gap", "shots": "max_shots"},
    "direct_attention_insert": {"x":"focus_x", "y":"focus_y", "time":"start", "length":"duration", "energy":"intensity", "focusX":"focus_x", "focusY":"focus_y"},
    "direct_band_sequence": {"scenes": "scene_ids", "audio": "rhythm_asset_id", "music": "rhythm_asset_id", "bgm": "rhythm_asset_id", "members": "member_ids", "intensity": "energy"},
    "apply_scene_recipe": {"data": "payload", "options": "payload", "type": "recipe"},
    "define_character": {"name": "display_name", "x": "focus_x", "y": "focus_y", "position": "subtitle_position"},
    "stage_character": {"character": "character_id", "member": "character_id", "x": "focus_x", "y": "focus_y", "角色": "character_id"},
    "auto_subtitles": {"asset": "asset_id", "audio": "asset_id", "video": "asset_id", "lang": "language", "dual": "bilingual", "translate": "translate_to", "style": "subtitle_style"},
    "import_subtitle_file": {"file": "path", "style": "subtitle_style"},
    "stage_scene_by_order": {"characters": "character_ids", "members": "character_ids", "角色": "character_ids"},
    "optimize_subtitle_layout": {"captions": "caption_ids", "dialogue": "include_dialogue"},
    "set_gen3_scene": {"scene": "scene_id", "type": "kind", "work": "work_title"},
    "set_gen3_card": {"scene": "scene_id", "text": "body", "description": "body", "label": "category"},
    "register_gen3_actor_card": {"file": "path", "id": "asset_id", "key": "key_color", "shadow": "make_shadow"},
    "place_gen3_actor": {"scene": "scene_id", "asset": "asset_id", "y": "floor_y", "shadow": "shadow_asset_id"},
}

LIBRARY_ARGS = {
    ("add_filter", "filter_id"): "filters",
    ("apply_motion_preset", "preset_id"): "motions",
    ("apply_transition_preset", "preset_id"): "transitions",
    ("apply_effect_preset", "preset_id"): "effects",
    ("set_transition", "transition"): "transitions",
}

ACTION_DOMAINS = {
    "add_scene": "timeline", "delete_scene": "timeline", "set_scene_asset": "timeline", "move_scene": "timeline",
    "set_duration": "timeline", "set_source": "timeline", "set_video_mode": "project",
    "set_camera": "visual", "set_composition": "visual", "apply_auto_composition": "visual",
    "apply_visual_composition": "visual", "auto_compose_scenes": "visual", "analyze_visual": "visual",
    "set_cinematic_frame": "cinematic", "clear_cinematic_frame": "cinematic", "fragment_scene": "cinematic",
    "apply_cinematic_treatment": "cinematic", "add_effect": "visual", "apply_effect_preset": "visual",
    "remove_effect": "visual", "clear_effects": "visual", "add_filter": "visual", "clear_filters": "visual",
    "apply_motion_preset": "visual", "set_transition": "transition", "apply_transition_preset": "transition",
    "set_transition_event": "transition", "clear_transition_sfx": "transition",
    "add_layer": "graphics", "update_layer": "graphics", "remove_layer": "graphics", "apply_layer_motion": "graphics",
    "add_scene_audio": "audio", "remove_scene_audio": "audio", "update_scene_audio": "audio",
    "add_audio_track": "audio", "remove_audio_track": "audio", "update_audio_track": "audio",
    "add_caption": "text", "update_caption": "text", "remove_caption": "text",
    "import_subtitle_file": "text", "auto_subtitles": "text", "optimize_subtitle_layout": "text",
    "add_dialogue_segment": "text", "update_dialogue_segment": "text", "remove_dialogue_segment": "text",
    "define_character": "performance", "update_character": "performance", "remove_character": "performance", "stage_character": "performance", "clear_scene_staging": "performance",
    "compose_dialogue_scene": "performance", "direct_dialogue_coverage": "performance", "direct_attention_insert": "performance", "direct_performance_scene": "performance", "direct_reaction_scene": "performance", "direct_band_sequence": "performance", "apply_scene_recipe": "performance",
    "tag_asset": "asset", "set_fact": "project", "remove_fact": "project", "restore_scene": "history",
    "configure_gen3": "gen3", "set_gen3_scene": "gen3", "set_gen3_card": "gen3", "register_gen3_actor_card": "gen3", "place_gen3_actor": "gen3", "compile_gen3": "gen3",
}

SHAPE_ACTION_KEYS = ("action", "operation", "op", "tool")
SHAPE_ARGS_KEYS = ("args", "arguments", "params", "parameters")


def _snake(value: str) -> str:
    value = str(value).strip().replace("-", "_").replace(" ", "_")
    value = re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()
    return re.sub(r"_+", "_", value).strip("_")


def _best_unique_typo(candidate: str, choices: set[str] | list[str], *, cutoff: float = 0.86, gap: float = 0.08) -> str | None:
    ranked = sorted(((difflib.SequenceMatcher(None, candidate, x).ratio(), x) for x in choices), reverse=True)
    if not ranked or ranked[0][0] < cutoff:
        return None
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < gap:
        return None
    return ranked[0][1]


def normalize_action(action: str, allowed: set[str]) -> tuple[str, list[dict]]:
    original = str(action or "")
    candidate = _snake(original)
    repairs: list[dict] = []
    if candidate in ACTION_ALIASES:
        mapped = ACTION_ALIASES[candidate]
        if mapped in allowed:
            repairs.append({"kind": "action_alias", "from": original, "to": mapped})
            return mapped, repairs
    if candidate in allowed:
        if candidate != original:
            repairs.append({"kind": "action_normalized", "from": original, "to": candidate})
        return candidate, repairs
    typo = _best_unique_typo(candidate, allowed)
    if typo:
        repairs.append({"kind": "action_typo", "from": original, "to": typo})
        return typo, repairs
    close = difflib.get_close_matches(candidate, sorted(allowed), n=3, cutoff=0.68)
    raise AgentCutError(
        "UNSUPPORTED_OPERATION", "Unsupported operation",
        action=original, normalized=candidate, suggestions=close, allowed=sorted(allowed),
    )


def _annotation_name(annotation: Any) -> str | None:
    if annotation is inspect._empty:
        return None
    if isinstance(annotation, str):
        return annotation
    name = getattr(annotation, "__name__", None)
    return name or str(annotation).replace("typing.", "")


def operation_schema(editor, *, domains: list[str] | None = None, actions: list[str] | None = None) -> dict:
    wanted_domains = {_snake(x) for x in (domains or [])}
    wanted_actions = {_snake(x) for x in (actions or [])}
    reverse_aliases: dict[str, list[str]] = {}
    for alias, canonical in ACTION_ALIASES.items():
        reverse_aliases.setdefault(canonical, []).append(alias)

    out = {}
    for action, fn in editor._operation_map().items():
        domain = ACTION_DOMAINS.get(action, "other")
        if wanted_domains and domain not in wanted_domains:
            continue
        if wanted_actions and action not in wanted_actions:
            continue
        sig = inspect.signature(fn)
        required, optional, params = [], {}, {}
        for name, param in sig.parameters.items():
            if name == "self" or param.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}:
                continue
            if param.default is inspect._empty:
                required.append(name)
            else:
                optional[name] = param.default
            params[name] = {
                "type": _annotation_name(param.annotation),
                "required": param.default is inspect._empty,
            }
            if param.default is not inspect._empty:
                params[name]["default"] = param.default
        aliases = {**COMMON_ARG_ALIASES, **ACTION_ARG_ALIASES.get(action, {})}
        accepted = set(params)
        arg_aliases = {k: v for k, v in aliases.items() if v in accepted and k != v}
        out[action] = {
            "domain": domain,
            "required": required,
            "optional": optional,
            "parameters": params,
            "action_aliases": sorted(reverse_aliases.get(action, [])),
            "argument_aliases": arg_aliases,
        }
    return out


def _coerce_operations_input(operations) -> tuple[list[dict], list[dict]]:
    repairs: list[dict] = []
    if isinstance(operations, list):
        return operations, repairs
    if isinstance(operations, dict):
        if isinstance(operations.get("operations"), list):
            repairs.append({"kind": "root_wrapper", "from": "object.operations", "to": "operations[]"})
            return operations["operations"], repairs
        if any(k in operations for k in SHAPE_ACTION_KEYS):
            repairs.append({"kind": "singleton_operation", "from": "object", "to": "operations[]"})
            return [operations], repairs
    raise AgentCutError("INVALID_OPERATIONS", "Operations must be an array, a single operation object, or {operations:[...]}", value_type=type(operations).__name__)


def _coerce_operation_shape(raw: dict, index: int) -> tuple[str, dict, list[dict], str | None]:
    repairs: list[dict] = []
    action_key = next((k for k in SHAPE_ACTION_KEYS if k in raw), None)
    if not action_key:
        raise AgentCutError("INVALID_OPERATION", "Operation is missing action/operation/op/tool", operation_index=index)
    action = raw.get(action_key)
    if action_key != "action":
        repairs.append({"kind": "shape_alias", "from": action_key, "to": "action"})

    args_key = next((k for k in SHAPE_ARGS_KEYS if k in raw), None)
    if args_key:
        args = raw.get(args_key)
        if not isinstance(args, dict):
            raise AgentCutError("INVALID_OPERATION_ARGS", "Operation args must be an object", operation_index=index, value_type=type(args).__name__)
        args = dict(args)
        if args_key != "args":
            repairs.append({"kind": "shape_alias", "from": args_key, "to": "args"})
    else:
        args = {}

    reserved = set(SHAPE_ACTION_KEYS) | set(SHAPE_ARGS_KEYS) | {"ref", "id", "note"}
    flattened = {k: v for k, v in raw.items() if k not in reserved}
    if flattened:
        for key, value in flattened.items():
            if key in args and args[key] != value:
                raise AgentCutError("AMBIGUOUS_OPERATION_ARG", "Flattened and nested arguments conflict", operation_index=index, field=key)
            args[key] = value
        repairs.append({"kind": "flattened_args", "fields": sorted(flattened)})
    return str(action or ""), args, repairs, str(raw.get("ref") or raw.get("id") or "") or None


def _normalize_args(action: str, args: dict, schema: dict) -> tuple[dict, list[dict], list[dict]]:
    if not isinstance(args, dict):
        raise AgentCutError("INVALID_OPERATION_ARGS", "Operation args must be an object", action=action, value_type=type(args).__name__)
    accepted = set(schema[action]["required"]) | set(schema[action]["optional"])
    aliases = {**COMMON_ARG_ALIASES, **ACTION_ARG_ALIASES.get(action, {})}
    normalized: dict = {}
    repairs: list[dict] = []
    warnings: list[dict] = []
    for key, value in args.items():
        target = key if key in accepted else aliases.get(key, aliases.get(_snake(key), _snake(key)))
        if target not in accepted:
            typo = _best_unique_typo(str(target), accepted, cutoff=0.88, gap=0.1)
            if typo:
                repairs.append({"kind": "arg_typo", "action": action, "from": key, "to": typo})
                target = typo
            else:
                close = difflib.get_close_matches(str(target), sorted(accepted), n=2, cutoff=0.7)
                raise AgentCutError(
                    "UNKNOWN_OPERATION_ARG", "Unknown argument for operation",
                    action=action, argument=key, normalized=target, suggestions=close, accepted=sorted(accepted),
                )
        if target in normalized and normalized[target] != value:
            raise AgentCutError("AMBIGUOUS_OPERATION_ARG", "Two arguments map to the same canonical field", action=action, field=target)
        normalized[target] = value
        if target != key and not any(r.get("from") == key and r.get("to") == target for r in repairs):
            repairs.append({"kind": "arg_alias", "action": action, "from": key, "to": target})

    missing = [name for name in schema[action]["required"] if name not in normalized]
    if missing:
        raise AgentCutError("MISSING_OPERATION_ARG", "Required operation arguments are missing", action=action, missing=missing, accepted=sorted(accepted))
    return normalized, repairs, warnings


def _library_suggestions(action: str, args: dict) -> list[dict]:
    out = []
    for (a, arg), kind in LIBRARY_ARGS.items():
        if action != a or arg not in args:
            continue
        value = str(args[arg])
        ids = [row["id"] for row in list_items(kind)]
        if value == "cut" and kind == "transitions":
            continue
        if value not in ids:
            close = difflib.get_close_matches(value, ids, n=4, cutoff=0.45)
            out.append({"kind": "library_item", "action": action, "argument": arg, "value": value, "library": kind, "suggestions": close})
    return out


def entity_index(editor) -> dict:
    p = editor.project
    layers = []
    scene_tracks = []
    for s in p.get("scenes", []):
        layers.extend({"id": x.get("id"), "scene_id": s["id"]} for x in s.get("layers", []) if x.get("id"))
        scene_tracks.extend({"id": x.get("id"), "scene_id": s["id"]} for x in s.get("audio", []) if x.get("id"))
    return {
        "scenes": [s["id"] for s in p.get("scenes", [])],
        "assets": sorted(p.get("assets", {}).keys()),
        "captions": [x.get("id") for x in p.get("captions", []) if x.get("id")],
        "dialogue": [x.get("id") for x in p.get("dialogue_segments", []) if x.get("id")],
        "characters": sorted((p.get("cast") or {}).keys()),
        "global_audio_tracks": [x.get("id") for x in p.get("audio_tracks", []) if x.get("id")],
        "layers": layers,
        "scene_audio_tracks": scene_tracks,
    }


def normalize_operations(editor, operations) -> dict:
    raw_operations, root_repairs = _coerce_operations_input(operations)
    schema = operation_schema(editor)
    allowed = set(schema)
    normalized, repairs, warnings, refs = [], list(root_repairs), [], []
    for index, raw in enumerate(raw_operations):
        if not isinstance(raw, dict):
            raise AgentCutError("INVALID_OPERATION", "Operation must be an object", operation_index=index)
        raw_action, raw_args, shape_repairs, ref = _coerce_operation_shape(raw, index)
        action, action_repairs = normalize_action(raw_action, allowed)
        inference_repairs = []
        required = set(schema[action]["required"])
        has_scene_arg = any(k in raw_args for k in {"scene_id", "scene", "sceneId", "sceneID"})
        if "scene_id" in required and not has_scene_arg:
            scene_ids = [x.get("id") for x in editor.project.get("scenes", []) if x.get("id")]
            if len(scene_ids) == 1:
                raw_args = dict(raw_args); raw_args["scene_id"] = scene_ids[0]
                inference_repairs.append({"kind": "single_scene_inference", "field": "scene_id", "value": scene_ids[0]})
        args, arg_repairs, arg_warnings = _normalize_args(action, raw_args, schema)
        lib_notes = _library_suggestions(action, args)
        warnings.extend({**x, "operation_index": index} for x in lib_notes + arg_warnings)
        repairs.extend({**x, "operation_index": index} for x in shape_repairs + action_repairs + inference_repairs + arg_repairs)
        normalized.append({"action": action, "args": args})
        refs.append(ref)
    return {"operations": normalized, "operation_refs": refs, "repairs": repairs, "warnings": warnings, "schema_version": 5}


def _project_digest(project: dict) -> dict:
    timeline = build_timeline(project)
    return {
        "project_hash": hash_obj(project),
        "timeline_duration": timeline.get("duration", 0.0),
        "scene_count": len(project.get("scenes", [])),
        "asset_count": len(project.get("assets", {})),
        "caption_count": len(project.get("captions", [])),
        "dialogue_count": len(project.get("dialogue_segments", [])),
        "video": deepcopy(project.get("video")),
    }


def _changed_scene_ids(before: dict, after: dict) -> tuple[list[str], bool, list[str]]:
    before_s = {s["id"]: s for s in before.get("scenes", [])}
    after_s = {s["id"]: s for s in after.get("scenes", [])}
    ids = sorted({*before_s, *after_s})
    changed = [sid for sid in ids if before_s.get(sid) != after_s.get(sid)]
    before_order = [s["id"] for s in before.get("scenes", [])]
    after_order = [s["id"] for s in after.get("scenes", [])]
    order_changed = before_order != after_order
    duration_changed = [sid for sid in set(before_s) & set(after_s) if before_s[sid].get("duration") != after_s[sid].get("duration")]
    return changed, order_changed, sorted(duration_changed, key=lambda x: after_order.index(x) if x in after_order else 10**9)


def _changed_caption_span(before: dict, after: dict) -> tuple[float, float] | None:
    def keyed(rows):
        out = {}
        for idx, row in enumerate(rows or []):
            out[str(row.get("id") or f"__index_{idx}")] = row
        return out
    left, right = keyed(before.get("captions")), keyed(after.get("captions"))
    changed = []
    for key in set(left) | set(right):
        if left.get(key) != right.get(key):
            changed.extend(row for row in (left.get(key), right.get(key)) if row)
    if not changed:
        return None
    starts = [max(0.0, float(row.get("start", 0.0))) for row in changed]
    ends = [max(float(row.get("start", 0.0)), float(row.get("end", row.get("start", 0.0)))) for row in changed]
    return min(starts), max(ends)


def _caption_render_scope(project: dict, span: tuple[float, float] | None) -> dict:
    if span is None:
        return {"kind": "none", "reason": "caption_change_without_timing"}
    start, end = span
    timeline = build_timeline(project)
    rows = [row for row in timeline.get("scenes", []) if float(row["end"]) > start and float(row["start"]) < end]
    if not rows:
        return {"kind": "span", "start": start, "end": end, "reason": "caption_overlay_only", "mode": "overlay_only"}
    if len(rows) == 1:
        return {"kind": "span", "start": start, "end": end, "start_scene": rows[0]["scene_id"],
                "end_scene": rows[0]["scene_id"], "reason": "caption_overlay_only", "mode": "overlay_only"}
    return {"kind": "span", "start": start, "end": end, "start_scene": rows[0]["scene_id"],
            "end_scene": rows[-1]["scene_id"], "reason": "caption_overlay_only", "mode": "overlay_only"}


def change_impact(before: dict, after: dict, operations: list[dict]) -> dict:
    changed_scenes, structure_changed, duration_changed_scenes = _changed_scene_ids(before, after)
    added_scenes = [s["id"] for s in after.get("scenes", []) if s["id"] not in {x["id"] for x in before.get("scenes", [])}]
    deleted_scenes = [s["id"] for s in before.get("scenes", []) if s["id"] not in {x["id"] for x in after.get("scenes", [])}]
    video_changed = before.get("video") != after.get("video")
    captions_changed = before.get("captions") != after.get("captions")
    global_audio_changed = before.get("audio_tracks") != after.get("audio_tracks")
    facts_changed = before.get("facts") != after.get("facts")

    if before.get("dialogue_segments") != after.get("dialogue_segments"):
        d_before = {x.get("id"): x for x in before.get("dialogue_segments", [])}
        d_after = {x.get("id"): x for x in after.get("dialogue_segments", [])}
        for did in set(d_before) | set(d_after):
            if d_before.get(did) != d_after.get(did):
                for row in (d_before.get(did), d_after.get(did)):
                    if row and row.get("scene_id") and row["scene_id"] not in changed_scenes:
                        changed_scenes.append(row["scene_id"])

    changed_scenes = [sid for sid in [s["id"] for s in after.get("scenes", [])] if sid in set(changed_scenes)] + [sid for sid in changed_scenes if sid not in {s["id"] for s in after.get("scenes", [])}]
    op_domains = sorted({ACTION_DOMAINS.get(x.get("action"), "other") for x in operations})
    full_required = structure_changed or video_changed or bool(deleted_scenes)
    order = [s["id"] for s in after.get("scenes", [])]

    # Dependency-aware DAG: metadata and global audio do not invalidate video pixels;
    # captions invalidate only their overlay span. Scene/local changes retain legacy behavior.
    if full_required:
        render = {"kind": "full", "reason": "timeline_or_global_geometry_change"}
    elif changed_scenes:
        if duration_changed_scenes:
            first = min((order.index(x) for x in duration_changed_scenes if x in order), default=0)
            if len(order) == 1 or first == len(order) - 1:
                render = {"kind": "scene", "scene_id": order[first], "reason": "duration_change_last_scene"}
            else:
                render = {"kind": "span", "start_scene": order[first], "end_scene": order[-1], "reason": "timeline_shift_from_duration"}
        elif len(changed_scenes) == 1:
            sid = changed_scenes[0]
            if "transition" in op_domains and sid in order and order.index(sid) + 1 < len(order):
                render = {"kind": "span", "start_scene": sid, "end_scene": order[order.index(sid) + 1], "reason": "transition_boundary_change"}
            else:
                render = {"kind": "scene", "scene_id": sid, "reason": "single_scene_change"}
        else:
            positions = sorted(order.index(x) for x in changed_scenes if x in order)
            contiguous = positions and positions == list(range(positions[0], positions[-1] + 1))
            render = ({"kind": "span", "start_scene": order[positions[0]], "end_scene": order[positions[-1]],
                       "reason": "contiguous_scene_changes"}
                      if contiguous else {"kind": "full", "reason": "non_contiguous_scene_changes"})
    elif captions_changed:
        render = _caption_render_scope(after, _changed_caption_span(before, after))
        render["video_render_required"] = True
    elif global_audio_changed:
        render = {"kind": "audio_only", "reason": "global_audio_mix_change", "video_render_required": False}
    elif facts_changed:
        render = {"kind": "none", "reason": "metadata_only_change", "video_render_required": False}
    else:
        render = {"kind": "none", "reason": "no_render_affecting_change", "video_render_required": False}

    risks = []
    if "cinematic" in op_domains: risks.append("inspect_motion_continuity")
    if "transition" in op_domains: risks.append("inspect_transition_boundary")
    if "text" in op_domains or captions_changed: risks.append("inspect_text_safe_area")
    if "audio" in op_domains or global_audio_changed: risks.append("check_audio_mix")
    if "performance" in op_domains: risks.extend(["inspect_dialogue_readability", "inspect_speaker_focus", "inspect_motion_rhythm"])
    if duration_changed_scenes: risks.append("check_timeline_alignment_after_duration_change")
    if video_changed: risks.append("verify_output_geometry_and_fps")

    return {
        "changed_scene_ids": changed_scenes, "added_scene_ids": added_scenes, "deleted_scene_ids": deleted_scenes,
        "structure_changed": structure_changed, "duration_changed_scene_ids": duration_changed_scenes,
        "timeline_shifted": bool(duration_changed_scenes), "video_changed": video_changed,
        "captions_changed": captions_changed, "global_audio_changed": global_audio_changed,
        "facts_changed": facts_changed, "domains": op_domains, "render_scope": render, "risk_flags": risks,
    }


def verification_plan(impact: dict) -> dict:
    render = impact.get("render_scope", {"kind": "full"})
    steps = ["re_read_state_digest"]
    if render["kind"] == "scene":
        steps.append(f"render_scene:{render['scene_id']}")
    elif render["kind"] == "span":
        if render.get("start_scene") and render.get("end_scene"):
            steps.append(f"render_span:{render['start_scene']}..{render['end_scene']}")
        else:
            steps.append(f"render_time_span:{render.get('start', 0)}..{render.get('end', 0)}")
    elif render["kind"] == "audio_only":
        steps.append("remix_audio_without_video_rerender")
    elif render["kind"] == "none":
        steps.append("no_render_required")
    else:
        steps.append("render_preview")
    if render["kind"] != "none":
        steps.append("qa_render")
    if impact.get("risk_flags"):
        steps.append("inspect_relevant_frames")
    return {"recommended": steps, "risk_flags": impact.get("risk_flags", [])}


def _error_recovery(editor, error: dict) -> dict | None:
    code = error.get("error")
    ctx = error.get("context") or {}
    entities = entity_index(editor)
    mapping = {
        "SCENE_NOT_FOUND": ("scene", "scenes"),
        "ASSET_NOT_FOUND": ("asset_id", "assets"),
        "CAPTION_NOT_FOUND": ("caption_id", "captions"),
        "DIALOGUE_NOT_FOUND": ("dialogue_id", "dialogue"),
        "CHARACTER_NOT_FOUND": ("character_id", "characters"),
        "AUDIO_TRACK_NOT_FOUND": ("track_id", "global_audio_tracks"),
    }
    if code == "STATE_CONFLICT":
        return {"action": "reread_agent_context", "message": "Project changed; reread state and retry with the new project_hash."}
    if code == "RECIPE_NEEDS_LINES":
        return {"action": "provide_dialogue_lines", "message": "Add payload.lines, e.g. [{speaker:'A', text:'...'}]."}
    if code == "RECIPE_NEEDS_CHARACTER":
        return {"action": "choose_existing_character", "available": entities.get("characters", [])}
    if code not in mapping:
        return None
    field, bucket = mapping[code]
    value = str(ctx.get(field) or ctx.get("character") or ctx.get("scene") or "")
    ids = entities.get(bucket, [])
    if ids and isinstance(ids[0], dict):
        ids = [x.get("id") for x in ids if x.get("id")]
    return {
        "action": "choose_existing_id",
        "entity": bucket,
        "value": value,
        "suggestions": difflib.get_close_matches(value, ids, n=5, cutoff=0.35),
        "available": ids[:30],
    }


def preflight_operations(editor, operations, *, expected_project_hash: str | None = None, include_projected_state: bool = False) -> dict:
    before = deepcopy(editor.project)
    try:
        normalized = normalize_operations(editor, operations)
    except AgentCutError as exc:
        payload = exc.as_dict()
        return {
            "ok": False, "operations": [], "operation_refs": [], "repairs": [], "warnings": [],
            "schema_version": 5, "error": payload, "recovery": _error_recovery(editor, payload),
        }
    try:
        projected = editor.apply_operations(normalized["operations"], expected_project_hash=expected_project_hash, dry_run=True)
        impact = change_impact(before, projected["project"], normalized["operations"])
        out = {
            "ok": True,
            **normalized,
            "before_project_hash": hash_obj(before),
            "project_hash": projected["project_hash"],
            "projected_digest": _project_digest(projected["project"]),
            "impact": impact,
            "verification": verification_plan(impact),
        }
        if include_projected_state:
            out["projected_state"] = projected.get("project")
        return out
    except AgentCutError as exc:
        payload = exc.as_dict()
        payload["context"].setdefault("normalized_operations", deepcopy(normalized["operations"]))
        recovery = _error_recovery(editor, payload)
        return {"ok": False, **normalized, "error": payload, "recovery": recovery}


def _result_summary(value: Any) -> Any:
    if isinstance(value, dict):
        keep = ["id", "scene_id", "asset_id", "preset", "deleted", "removed", "type", "duration"]
        summary = {k: deepcopy(value[k]) for k in keep if k in value}
        return summary or {"keys": sorted(value.keys())[:12]}
    if isinstance(value, list):
        return {"list_length": len(value), "sample": deepcopy(value[:3])}
    return value


def apply_agent_operations(editor, operations, *, expected_project_hash: str | None = None, dry_run: bool = False, include_project: bool = False) -> dict:
    check = preflight_operations(editor, operations, expected_project_hash=expected_project_hash, include_projected_state=include_project)
    if not check["ok"]:
        err = check["error"]
        raise AgentCutError(err["error"], err["message"], **err.get("context", {}), repairs=check.get("repairs", []), warnings=check.get("warnings", []), recovery=check.get("recovery"))
    if dry_run:
        return check
    before_hash = check["before_project_hash"]
    # Lock the commit to the exact state that was preflighted, even when the caller omitted a hash.
    result = editor.apply_operations(check["operations"], expected_project_hash=expected_project_hash or before_hash, dry_run=False)
    after_digest = editor.state_digest()
    tx_id = "tx_" + hash_obj({"before": before_hash, "operations": check["operations"], "after": result["project_hash"]})[:12]
    out = {
        "ok": True,
        "transaction_id": tx_id,
        "normalized_operations": check["operations"],
        "operation_refs": check.get("operation_refs", []),
        "repairs": check["repairs"],
        "warnings": check["warnings"],
        "applied": result["applied"],
        "dry_run": False,
        "before_project_hash": before_hash,
        "project_hash": result["project_hash"],
        "state": after_digest,
        "impact": check["impact"],
        "verification": check["verification"],
        "result_summaries": [_result_summary(x) for x in result.get("results", [])],
    }
    if include_project:
        out["project"] = result.get("project")
        out["results"] = result.get("results")
    try:
        from .runtime import record_agent_receipt
        record_agent_receipt(editor.root, out)
    except Exception:
        # Runtime resume metadata must never make a successful edit fail.
        pass
    return out


def agent_context(editor, *, scene_ids: list[str] | None = None, domains: list[str] | None = None, include_schema: bool = True) -> dict:
    context = editor.context_pack(scene_ids=scene_ids)
    out = {
        "protocol_version": 5,
        "state": editor.state_digest(),
        "entities": entity_index(editor),
        "context": context,
        "recommended_loop": [
            "agent_bootstrap_first_on_restart", "read_task_scoped_agent_context", "submit_preflight",
            "inspect_repairs_and_impact", "apply_with_expected_project_hash", "render_recommended_scope", "qa_and_inspect",
        ],
        "restart_policy": "Use /agent/bootstrap on restart/upgrade. Warm resumes keep project-local checkpoint/last receipt; upgrades return schema_delta so only changed operations need rereading.",
        "recipes": {
            "dialogue_scene": {"action": "recipe", "scene": "scene_01", "recipe": "dialogue", "payload": {"lines": [{"speaker": "A", "text": "..."}]}},
            "band_performance": {"action": "recipe", "scene": "scene_01", "recipe": "band_performance", "payload": {"energy": 0.7}},
            "band_sequence": {"action": "band_sequence", "scenes": ["scene_01", "scene_02"], "music": "bgm", "energy": 0.75},
            "reaction_shot": {"action": "recipe", "scene": "scene_01", "recipe": "reaction", "payload": {"character": "A", "intensity": 0.65}},
            "calm_hold": {"action": "recipe", "scene": "scene_01", "recipe": "calm"},
            "auto_subtitles": {"action": "auto_subtitles", "asset": "voice_or_video", "language": "auto", "bilingual": False},
            "bilingual_subtitles": {"action": "auto_subtitles", "asset": "voice_or_video", "language": "auto", "bilingual": True, "translate_to": "en"},
            "subtitle_fit": {"action": "subtitle_optimize"},
            "visual_staging": {"action": "stage_by_order", "scene": "scene_01", "characters": ["A", "B"]},
        },
        "input_shapes": {
            "canonical": {"action": "set_camera", "args": {"scene_id": "scene_01", "motion": "slow_push"}},
            "also_accepted": [
                {"operation": "camera", "params": {"scene": "scene_01", "type": "slow_push"}},
                {"action": "camera", "scene": "scene_01", "type": "slow_push"},
            ],
        },
    }
    if include_schema:
        out["operations"] = operation_schema(editor, domains=domains)
    return out
