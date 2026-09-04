from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

from .capabilities import CAPABILITIES
from .errors import AgentCutError
from .util import json_dump, json_load
from .composition import CAPTION_ZONES, validate_composition
from .cinematic import validate_cinematic
from .subtitles import SUBTITLE_STYLES
from .gen3 import normalize_config, validate_scene_gen3

PROJECT_FILE = "project.json"
EASINGS = {"linear", "ease", "ease_in", "ease_out", "ease_in_out", "smooth"}
ANCHORS = {"center", "top", "bottom", "left", "right", "top_left", "top_right", "bottom_left", "bottom_right"}
DIRECTIONS = {"auto", "up", "down", "left", "right", "up_left", "up_right", "down_left", "down_right"}
DEPTHS = {"foreground", "midground", "background"}
AUDIO_KINDS = {"bgm", "ambience", "sfx", "dialogue"}
CAPTION_POSITIONS = set(CAPTION_ZONES)
ASSET_TYPES = {"image", "video", "audio", "subtitle", "font"}


def default_project(width=1920, height=1080, fps=30) -> dict:
    return {
        "schema_version": 1,
        "name": "Untitled AgentCut Project",
        "video": {"width": int(width), "height": int(height), "fps": int(fps)},
        "assets": {},
        "scenes": [],
        "audio_tracks": [],
        "captions": [],
        "dialogue_segments": [],
        "cast": {},
        "facts": {},
        "gen3": normalize_config({}),
        "defaults": {
            "transition": {"type": "cut", "duration": 0.0},
            "camera": {"type": "static", "amount": 0.0, "easing": "linear", "anchor": "center"},
            "composition": {"mode": "cover", "background": "black", "frame_scale": 1.0, "crop_zoom": 1.0, "focus_x": 0.5, "focus_y": 0.5, "caption_zone": "bottom"},
        },
    }


def load_project(root: Path) -> dict:
    return json_load(root / PROJECT_FILE)


def save_project(root: Path, project: dict) -> None:
    validate_project(project)
    json_dump(root / PROJECT_FILE, project)


def _number(value, *, field: str, minimum: float | None = None, exclusive: bool = False) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise AgentCutError("INVALID_PROJECT", f"{field} must be numeric", field=field, value=value) from exc
    if not math.isfinite(value):
        raise AgentCutError("INVALID_PROJECT", f"{field} must be finite", field=field, value=value)
    if minimum is not None and (value <= minimum if exclusive else value < minimum):
        op = ">" if exclusive else ">="
        raise AgentCutError("INVALID_PROJECT", f"{field} must be {op} {minimum}", field=field, value=value)
    return value


def _validate_audio_track(track: dict, assets: dict, *, field: str, scene_duration: float | None = None) -> None:
    aid = track.get("asset_id")
    if aid not in assets:
        raise AgentCutError("INVALID_ASSET", "Audio track references unknown asset", field=field, asset_id=aid)
    if assets[aid].get("type") != "audio":
        raise AgentCutError("INVALID_ASSET_TYPE", "Audio track must reference an audio asset", field=field, asset_id=aid)
    if track.get("kind", "bgm") not in AUDIO_KINDS:
        raise AgentCutError("INVALID_PROJECT", "Unsupported audio kind", field=f"{field}.kind", value=track.get("kind"))
    _number(track.get("volume_db", 0), field=f"{field}.volume_db")
    start = _number(track.get("start", 0), field=f"{field}.start", minimum=0)
    duration = track.get("duration")
    if duration is not None:
        duration = _number(duration, field=f"{field}.duration", minimum=0, exclusive=True)
    _number(track.get("fade_in", 0), field=f"{field}.fade_in", minimum=0)
    _number(track.get("fade_out", 0), field=f"{field}.fade_out", minimum=0)
    if scene_duration is not None:
        if start >= scene_duration:
            raise AgentCutError("INVALID_PROJECT", "Scene audio starts outside its scene", field=field, start=start, scene_duration=scene_duration)
        if duration is not None and start + duration > scene_duration + 1e-9:
            raise AgentCutError("INVALID_PROJECT", "Scene audio extends past scene end", field=field, start=start, duration=duration, scene_duration=scene_duration)


def validate_project(project: dict) -> None:
    if not isinstance(project, dict):
        raise AgentCutError("INVALID_PROJECT", "Project root must be an object")
    schema_version = project.get("schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        raise AgentCutError("INVALID_PROJECT", "schema_version must be an integer >= 1", schema_version=schema_version)

    video = project.get("video", {})
    for key in ("width", "height", "fps"):
        value = video.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise AgentCutError("INVALID_PROJECT", f"video.{key} must be a positive integer", field=f"video.{key}", value=value)
    if int(video["fps"]) > 240:
        raise AgentCutError("INVALID_PROJECT", "video.fps must be <= 240", field="video.fps", value=video["fps"])

    # Gen3/Jane3 is optional for legacy projects but normalized when present.
    if "gen3" in project:
        normalize_config(project.get("gen3") or {})
    if "remotion" in project:
        from .remotion_bridge import validate_remotion_state
        validate_remotion_state(project)

    assets = project.get("assets", {})
    if not isinstance(assets, dict):
        raise AgentCutError("INVALID_PROJECT", "assets must be an object")
    for key, asset in assets.items():
        if not isinstance(asset, dict):
            raise AgentCutError("INVALID_PROJECT", "Asset entry must be an object", asset_id=key)
        if asset.get("id") != key:
            raise AgentCutError("INVALID_PROJECT", "Asset object id must match its dictionary key", asset_key=key, asset_id=asset.get("id"))
        if asset.get("type") not in ASSET_TYPES:
            raise AgentCutError("INVALID_PROJECT", "Unsupported asset type", asset_id=key, type=asset.get("type"))
        if not isinstance(asset.get("path"), str) or not asset.get("path"):
            raise AgentCutError("INVALID_PROJECT", "Asset path must be a non-empty string", asset_id=key)

    facts = project.get("facts", {})
    if not isinstance(facts, dict):
        raise AgentCutError("INVALID_PROJECT", "facts must be an object")
    for key, value in facts.items():
        if not isinstance(key, str) or not key:
            raise AgentCutError("INVALID_PROJECT", "fact keys must be non-empty strings", key=key)
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise AgentCutError("INVALID_PROJECT", "fact values must be scalar", key=key, value_type=type(value).__name__)

    cast = project.get("cast", {})
    if not isinstance(cast, dict):
        raise AgentCutError("INVALID_PROJECT", "cast must be an object")
    for cid, row in cast.items():
        if not isinstance(cid, str) or not cid or not isinstance(row, dict):
            raise AgentCutError("INVALID_PROJECT", "Cast entries must use non-empty string IDs", character_id=cid)
        if row.get("id", cid) != cid:
            raise AgentCutError("INVALID_PROJECT", "Cast object id must match its key", character_id=cid, row_id=row.get("id"))
        fx = _number(row.get("focus_x", .5), field=f"cast.{cid}.focus_x", minimum=0)
        fy = _number(row.get("focus_y", .5), field=f"cast.{cid}.focus_y", minimum=0)
        if fx > 1 or fy > 1:
            raise AgentCutError("INVALID_PROJECT", "Character focus coordinates must be <= 1", character_id=cid, focus_x=fx, focus_y=fy)
        pos = row.get("subtitle_position", "auto")
        if pos != "auto" and pos not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_PROJECT", "Unsupported cast subtitle position", character_id=cid, position=pos)
        color = str(row.get("color", "#FFFFFF"))
        if not __import__('re').fullmatch(r"#[0-9A-Fa-f]{6}", color):
            raise AgentCutError("INVALID_PROJECT", "Character color must be #RRGGBB", character_id=cid, color=color)
        aliases = row.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(x, str) for x in aliases):
            raise AgentCutError("INVALID_PROJECT", "Character aliases must be strings", character_id=cid)

    scenes = project.get("scenes", [])
    if not isinstance(scenes, list):
        raise AgentCutError("INVALID_PROJECT", "scenes must be an array")
    seen = set()
    for i, scene in enumerate(scenes):
        field = f"scenes[{i}]"
        if not isinstance(scene, dict):
            raise AgentCutError("INVALID_PROJECT", "Scene must be an object", field=field)
        sid = scene.get("id")
        if not sid or not isinstance(sid, str) or sid in seen:
            raise AgentCutError("INVALID_PROJECT", "Scene IDs must be unique and non-empty", scene_id=sid)
        seen.add(sid)
        aid = scene.get("asset_id")
        if aid not in assets:
            raise AgentCutError("INVALID_ASSET", "Scene references unknown asset", scene=sid, asset_id=aid)
        if assets[aid].get("type") not in {"image", "video"}:
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene must reference image/video asset", scene=sid, asset_id=aid, type=assets[aid].get("type"))
        duration = _number(scene.get("duration"), field=f"{field}.duration", minimum=0, exclusive=True)
        validate_scene_gen3(scene.get("gen3"), scene_duration=duration)
        source_in = _number(scene.get("source_in", 0), field=f"{field}.source_in", minimum=0)
        rate = _number(scene.get("playback_rate", 1), field=f"{field}.playback_rate", minimum=0, exclusive=True)
        if rate > 8:
            raise AgentCutError("INVALID_PROJECT", "playback_rate must be <= 8", scene=sid, playback_rate=rate)
        if assets[aid].get("type") == "image" and (source_in != 0 or rate != 1):
            raise AgentCutError("INVALID_PROJECT", "Image scenes cannot use source_in/playback_rate", scene=sid)

        camera = scene.get("camera") or {}
        if camera.get("type", "static") not in CAPABILITIES["camera"]:
            raise AgentCutError("INVALID_PROJECT", "Unsupported camera motion", scene=sid, motion=camera.get("type"))
        amount = _number(camera.get("amount", 0), field=f"{field}.camera.amount", minimum=0)
        if amount > 0.5:
            raise AgentCutError("INVALID_PROJECT", "camera.amount must be <= 0.5", scene=sid, amount=amount)
        if camera.get("easing", "linear") not in EASINGS:
            raise AgentCutError("INVALID_PROJECT", "Unsupported camera easing", scene=sid, easing=camera.get("easing"))
        if camera.get("anchor", "center") not in ANCHORS:
            raise AgentCutError("INVALID_PROJECT", "Unsupported camera anchor", scene=sid, anchor=camera.get("anchor"))
        shot_path = camera.get("shot_path") or []
        if not isinstance(shot_path, list) or len(shot_path) > 24:
            raise AgentCutError("INVALID_PROJECT", "camera.shot_path must be a list with at most 24 points", scene=sid)
        last_t = -1.0
        for j, row in enumerate(shot_path):
            if not isinstance(row, dict):
                raise AgentCutError("INVALID_PROJECT", "camera.shot_path points must be objects", scene=sid, index=j)
            t = _number(row.get("t", 0), field=f"{field}.camera.shot_path[{j}].t", minimum=0)
            if t > 1 or t < last_t:
                raise AgentCutError("INVALID_PROJECT", "camera.shot_path t must be sorted within [0,1]", scene=sid, index=j, t=t)
            last_t = t
            for key in ("x", "y"):
                value = _number(row.get(key, .5), field=f"{field}.camera.shot_path[{j}].{key}", minimum=0)
                if value > 1:
                    raise AgentCutError("INVALID_PROJECT", "camera.shot_path coordinates must be <= 1", scene=sid, index=j, key=key, value=value)
            zoom = _number(row.get("zoom", 1.0), field=f"{field}.camera.shot_path[{j}].zoom", minimum=1.0)
            if zoom > 1.6:
                raise AgentCutError("INVALID_PROJECT", "camera.shot_path zoom must be <= 1.6", scene=sid, index=j, zoom=zoom)
            if row.get("cut") not in (None, True, False):
                raise AgentCutError("INVALID_PROJECT", "camera.shot_path cut must be boolean", scene=sid, index=j)

        try:
            validate_composition(scene.get("composition") or {"mode": "cover", "background": "black", "frame_scale": 1.0, "crop_zoom": 1.0, "focus_x": 0.5, "focus_y": 0.5, "caption_zone": "bottom"})
            if scene.get("cinematic") is not None:
                canvas_aspect = float(video["width"]) / float(video["height"])
                validate_cinematic(scene.get("cinematic"), canvas_aspect=canvas_aspect)
        except AgentCutError as exc:
            exc.context.setdefault("scene", sid)
            raise

        layers = scene.get("layers", [])
        if not isinstance(layers, list):
            raise AgentCutError("INVALID_PROJECT", "Scene layers must be an array", scene=sid)
        layer_ids=set()
        for j, layer in enumerate(layers):
            lf=f"{field}.layers[{j}]"
            if not isinstance(layer, dict):
                raise AgentCutError("INVALID_PROJECT", "Layer must be an object", field=lf)
            lid=layer.get("id")
            if not isinstance(lid,str) or not lid or lid in layer_ids:
                raise AgentCutError("INVALID_PROJECT", "Layer ids must be unique within scene", scene=sid, layer_id=lid)
            layer_ids.add(lid)
            if layer.get("type") not in {"text","rect","image"}:
                raise AgentCutError("INVALID_PROJECT", "Unsupported layer type", scene=sid, layer_type=layer.get("type"))
            _number(layer.get("start",0), field=f"{lf}.start", minimum=0)
            ldur=_number(layer.get("duration",duration), field=f"{lf}.duration", minimum=0, exclusive=True)
            if float(layer.get("start",0))+ldur > duration+1e-6:
                raise AgentCutError("INVALID_PROJECT", "Layer extends past scene end", scene=sid, layer_id=lid)
            if layer.get("type")=="image":
                laid=layer.get("asset_id")
                if laid not in assets or assets[laid].get("type")!="image":
                    raise AgentCutError("INVALID_ASSET", "Image layer must reference image asset", scene=sid, layer_id=lid, asset_id=laid)

        staging = scene.get("staging", {})
        if staging is not None:
            if not isinstance(staging, dict):
                raise AgentCutError("INVALID_PROJECT", "Scene staging must be an object", scene=sid)
            for staged_cid, row in staging.items():
                if staged_cid not in cast:
                    raise AgentCutError("INVALID_PROJECT", "Scene staging references unknown Cast member", scene=sid, character_id=staged_cid)
                if not isinstance(row, dict):
                    raise AgentCutError("INVALID_PROJECT", "Scene staging entry must be an object", scene=sid, character_id=staged_cid)
                fx = _number(row.get("focus_x", .5), field=f"{field}.staging.{staged_cid}.focus_x", minimum=0)
                fy = _number(row.get("focus_y", .5), field=f"{field}.staging.{staged_cid}.focus_y", minimum=0)
                if fx > 1 or fy > 1:
                    raise AgentCutError("INVALID_PROJECT", "Scene staging coordinates must be <= 1", scene=sid, character_id=staged_cid)
                if "visible" in row and not isinstance(row.get("visible"), bool):
                    raise AgentCutError("INVALID_PROJECT", "Scene staging visible must be boolean", scene=sid, character_id=staged_cid)

        filters = scene.get("filters", [])
        if not isinstance(filters, list):
            raise AgentCutError("INVALID_PROJECT", "Scene filters must be an array", scene=sid)
        for j, flt in enumerate(filters):
            if not isinstance(flt, str) or flt not in CAPABILITIES.get("filters", []):
                raise AgentCutError("INVALID_PROJECT", "Unsupported scene filter", scene=sid, filter=flt, index=j)

        effects = scene.get("effects", [])
        if not isinstance(effects, list):
            raise AgentCutError("INVALID_PROJECT", "Scene effects must be an array", scene=sid)
        for j, fx in enumerate(effects):
            fxf = f"{field}.effects[{j}]"
            if fx.get("type") not in CAPABILITIES["environment"]:
                raise AgentCutError("INVALID_PROJECT", "Unsupported environment effect", scene=sid, effect=fx.get("type"))
            intensity = _number(fx.get("intensity", 0.2), field=f"{fxf}.intensity", minimum=0)
            opacity = _number(fx.get("opacity", 0.6), field=f"{fxf}.opacity", minimum=0)
            speed = _number(fx.get("speed", 1), field=f"{fxf}.speed", minimum=0, exclusive=True)
            if intensity > 1 or opacity > 1 or speed > 8:
                raise AgentCutError("INVALID_PROJECT", "Effect intensity/opacity/speed out of range", scene=sid, effect=fx.get("type"))
            if fx.get("direction", "auto") not in DIRECTIONS:
                raise AgentCutError("INVALID_PROJECT", "Unsupported effect direction", scene=sid, direction=fx.get("direction"))
            if fx.get("depth", "foreground") not in DEPTHS:
                raise AgentCutError("INVALID_PROJECT", "Unsupported depth hint", scene=sid, depth=fx.get("depth"))

        tr = scene.get("transition_out") or {"type": "cut", "duration": 0}
        if tr.get("type", "cut") not in CAPABILITIES["transitions"]:
            raise AgentCutError("INVALID_PROJECT", "Unsupported transition", scene=sid, transition=tr.get("type"))
        td = _number(tr.get("duration", 0), field=f"{field}.transition_out.duration", minimum=0)
        if tr.get("type", "cut") == "cut" and td != 0:
            raise AgentCutError("INVALID_PROJECT", "Cut transition must have duration 0", scene=sid, duration=td)
        if tr.get("type", "cut") != "cut" and td <= 0:
            raise AgentCutError("INVALID_PROJECT", "Non-cut transition must have duration > 0", scene=sid, duration=td)
        sfx = tr.get("sfx")
        if sfx is not None:
            if not isinstance(sfx, dict):
                raise AgentCutError("INVALID_PROJECT", "transition_out.sfx must be an object", scene=sid)
            sfx_aid = sfx.get("asset_id")
            if sfx_aid not in assets or assets[sfx_aid].get("type") != "audio":
                raise AgentCutError("INVALID_ASSET", "Transition SFX must reference an audio asset", scene=sid, asset_id=sfx_aid)
            _number(sfx.get("volume_db", -12), field=f"{field}.transition_out.sfx.volume_db")
            _number(sfx.get("offset", 0), field=f"{field}.transition_out.sfx.offset")
            _number(sfx.get("fade_in", 0), field=f"{field}.transition_out.sfx.fade_in", minimum=0)
            _number(sfx.get("fade_out", 0), field=f"{field}.transition_out.sfx.fade_out", minimum=0)

        for j, track in enumerate(scene.get("audio", [])):
            _validate_audio_track(track, assets, field=f"{field}.audio[{j}]", scene_duration=duration)

    # Adjacent transition validation: do not let renderer silently change semantic duration.
    for i, scene in enumerate(scenes[:-1]):
        tr = scene.get("transition_out") or {"type": "cut", "duration": 0}
        if tr.get("type", "cut") != "cut":
            td = float(tr.get("duration", 0))
            max_d = min(float(scene["duration"]), float(scenes[i + 1]["duration"]))
            if td >= max_d:
                raise AgentCutError("INVALID_PROJECT", "Transition must be shorter than both adjacent scenes", scene=scene["id"], duration=td, maximum_exclusive=max_d)

    dialogue_segments = project.get("dialogue_segments", [])
    if not isinstance(dialogue_segments, list):
        raise AgentCutError("INVALID_PROJECT", "dialogue_segments must be an array")
    dialogue_ids = set()
    scene_ids = {s.get("id") for s in scenes}
    for i, seg in enumerate(dialogue_segments):
        field = f"dialogue_segments[{i}]"
        if not isinstance(seg, dict):
            raise AgentCutError("INVALID_PROJECT", "Dialogue segment must be an object", field=field)
        did = seg.get("id")
        if not did or did in dialogue_ids:
            raise AgentCutError("INVALID_PROJECT", "Dialogue IDs must be unique and non-empty", dialogue_id=did)
        dialogue_ids.add(did)
        if seg.get("scene_id") not in scene_ids:
            raise AgentCutError("SCENE_NOT_FOUND", "Dialogue references unknown scene", dialogue_id=did, scene=seg.get("scene_id"))
        if not str(seg.get("text", "")).strip():
            raise AgentCutError("INVALID_PROJECT", "Dialogue text cannot be empty", dialogue_id=did)
        _number(seg.get("start", 0), field=f"{field}.start", minimum=0)
        if seg.get("duration") is not None:
            _number(seg.get("duration"), field=f"{field}.duration", minimum=0, exclusive=True)
        aid = seg.get("audio_asset_id")
        if aid is not None and (aid not in assets or assets[aid].get("type") != "audio"):
            raise AgentCutError("INVALID_ASSET", "Dialogue audio must reference an audio asset", dialogue_id=did, asset_id=aid)
        if seg.get("position", "bottom") not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_PROJECT", "Unsupported dialogue caption position", dialogue_id=did, position=seg.get("position"))
        character_id = seg.get("character_id")
        if character_id is not None and character_id not in cast:
            raise AgentCutError("CHARACTER_NOT_FOUND", "Dialogue references unknown character", dialogue_id=did, character_id=character_id)
        if str(seg.get("subtitle_style", "default")) not in SUBTITLE_STYLES:
            raise AgentCutError("INVALID_PROJECT", "Unsupported dialogue subtitle style", dialogue_id=did, style=seg.get("subtitle_style"))
        mlc = seg.get("max_line_chars")
        if mlc is not None and (not isinstance(mlc, int) or isinstance(mlc, bool) or mlc < 8 or mlc > 80):
            raise AgentCutError("INVALID_PROJECT", "max_line_chars must be an integer in [8,80]", dialogue_id=did, max_line_chars=mlc)
        smlc = seg.get("secondary_max_line_chars")
        if smlc is not None and (not isinstance(smlc, int) or isinstance(smlc, bool) or smlc < 8 or smlc > 100):
            raise AgentCutError("INVALID_PROJECT", "secondary_max_line_chars must be an integer in [8,100]", dialogue_id=did, secondary_max_line_chars=smlc)
        density = seg.get("layout_density")
        if density is not None:
            _number(density, field=f"{field}.layout_density", minimum=0)
        if seg.get("layout_level") is not None and seg.get("layout_level") not in {"normal","dense","very_dense","split_recommended"}:
            raise AgentCutError("INVALID_PROJECT", "Unsupported subtitle layout_level", dialogue_id=did, layout_level=seg.get("layout_level"))
        if seg.get("secondary_text") is not None and not str(seg.get("secondary_text", "")).strip():
            raise AgentCutError("INVALID_PROJECT", "secondary_text must be non-empty when provided", dialogue_id=did)
        scale = _number(seg.get("secondary_font_scale", 0.72), field=f"{field}.secondary_font_scale", minimum=0, exclusive=True)
        if scale > 1.5:
            raise AgentCutError("INVALID_PROJECT", "secondary_font_scale must be <= 1.5", dialogue_id=did, value=scale)

    for i, track in enumerate(project.get("audio_tracks", [])):
        _validate_audio_track(track, assets, field=f"audio_tracks[{i}]")

    caption_ids = set()
    for i, cap in enumerate(project.get("captions", [])):
        field = f"captions[{i}]"
        cid = cap.get("id")
        if cap.get("character_id") is not None and cap.get("character_id") not in cast:
            raise AgentCutError("INVALID_PROJECT", "Caption references unknown Cast member", caption=cid, character_id=cap.get("character_id"))
        if not cid or cid in caption_ids:
            raise AgentCutError("INVALID_PROJECT", "Caption IDs must be unique and non-empty", caption_id=cid)
        caption_ids.add(cid)
        if not str(cap.get("text", "")).strip():
            raise AgentCutError("INVALID_PROJECT", "Caption text cannot be empty", caption_id=cid)
        start = _number(cap.get("start"), field=f"{field}.start", minimum=0)
        end = _number(cap.get("end"), field=f"{field}.end", minimum=0, exclusive=True)
        if end <= start:
            raise AgentCutError("INVALID_PROJECT", "Caption end must be after start", caption_id=cid, start=start, end=end)
        if cap.get("position", "bottom") not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_PROJECT", "Unsupported caption position", caption_id=cid, position=cap.get("position"))
        if int(cap.get("font_size", 54)) <= 0 or int(cap.get("outline", 3)) < 0:
            raise AgentCutError("INVALID_PROJECT", "Invalid caption style", caption_id=cid)
        if str(cap.get("subtitle_style", "default")) not in SUBTITLE_STYLES:
            raise AgentCutError("INVALID_PROJECT", "Unsupported caption subtitle style", caption_id=cid, style=cap.get("subtitle_style"))
        for field_name in ("max_line_chars", "secondary_max_line_chars"):
            value = cap.get(field_name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 8 or value > 100):
                raise AgentCutError("INVALID_PROJECT", f"{field_name} must be an integer in [8,100]", caption_id=cid, value=value)
        density = cap.get("layout_density")
        if density is not None:
            _number(density, field=f"{field}.layout_density", minimum=0)
        if cap.get("layout_level") is not None and cap.get("layout_level") not in {"normal","dense","very_dense","split_recommended"}:
            raise AgentCutError("INVALID_PROJECT", "Unsupported subtitle layout_level", caption_id=cid, layout_level=cap.get("layout_level"))
        if cap.get("secondary_text") is not None and not str(cap.get("secondary_text", "")).strip():
            raise AgentCutError("INVALID_PROJECT", "secondary_text must be non-empty when provided", caption_id=cid)
        scale = _number(cap.get("secondary_font_scale", 0.72), field=f"{field}.secondary_font_scale", minimum=0, exclusive=True)
        if scale > 1.5:
            raise AgentCutError("INVALID_PROJECT", "secondary_font_scale must be <= 1.5", caption_id=cid, value=scale)


def clone_project(project: dict) -> dict:
    return deepcopy(project)
