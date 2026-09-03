from __future__ import annotations

import copy
import datetime as dt
import uuid
from typing import Any

from .cutgraph import CutGraphError, deep_merge, find_by_id, project_hash, recompute_duration, validate_project
from .impact import build_impact_plan


class ConflictError(CutGraphError):
    """Raised when an agent applies against a stale project hash."""


SUPPORTED_ACTIONS = {
    "register_asset", "remove_asset", "add_scene", "update_scene", "remove_scene",
    "set_caption", "remove_caption", "set_audio_clip", "remove_audio_clip",
    "set_project", "set_delivery", "set_metadata",
}


def normalize_operations(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(operations, list) or not operations:
        raise CutGraphError("operations must be a non-empty array")
    result: list[dict[str, Any]] = []
    aliases = {
        "asset.register": "register_asset", "scene.add": "add_scene",
        "scene.update": "update_scene", "scene.remove": "remove_scene",
        "caption.set": "set_caption", "audio.set": "set_audio_clip",
    }
    for raw in operations:
        if not isinstance(raw, dict):
            raise CutGraphError("each operation must be an object")
        action = aliases.get(raw.get("action"), raw.get("action"))
        if action not in SUPPORTED_ACTIONS:
            raise CutGraphError(f"unsupported action: {action!r}")
        args = raw.get("args", {})
        if not isinstance(args, dict):
            raise CutGraphError(f"operation {action} args must be an object")
        result.append({"action": action, "args": copy.deepcopy(args)})
    return result


def _upsert(items: list[dict[str, Any]], value: dict[str, Any]) -> tuple[dict[str, Any] | None, int]:
    item_id = value.get("id")
    if not isinstance(item_id, str) or not item_id:
        raise CutGraphError("upsert item requires id")
    for index, item in enumerate(items):
        if item.get("id") == item_id:
            previous = copy.deepcopy(item)
            items[index] = copy.deepcopy(value)
            return previous, index
    items.append(copy.deepcopy(value))
    return None, len(items) - 1


def _apply_one(project: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    action = operation["action"]
    args = operation["args"]
    timeline = project["timeline"]

    if action == "register_asset":
        asset = copy.deepcopy(args.get("asset"))
        if not isinstance(asset, dict) or not asset.get("id"):
            raise CutGraphError("register_asset requires args.asset")
        asset_id = asset["id"]
        previous = copy.deepcopy(project["assets"].get(asset_id))
        project["assets"][asset_id] = asset
        return ({"action": "register_asset", "args": {"asset": previous}} if previous is not None else {"action": "remove_asset", "args": {"asset_id": asset_id}})

    if action == "remove_asset":
        asset_id = args.get("asset_id")
        if asset_id not in project["assets"]:
            raise CutGraphError(f"asset not found: {asset_id}")
        for scene in timeline["scenes"]:
            if scene.get("asset_id") == asset_id:
                raise CutGraphError(f"cannot remove asset {asset_id!r}; used by scene {scene['id']!r}")
        for clip in timeline["audio"]:
            if clip.get("asset_id") == asset_id:
                raise CutGraphError(f"cannot remove asset {asset_id!r}; used by audio {clip['id']!r}")
        previous = project["assets"].pop(asset_id)
        return {"action": "register_asset", "args": {"asset": previous}}

    if action == "add_scene":
        scene = copy.deepcopy(args.get("scene"))
        if not isinstance(scene, dict) or not scene.get("id"):
            raise CutGraphError("add_scene requires args.scene")
        if any(x.get("id") == scene["id"] for x in timeline["scenes"]):
            raise CutGraphError(f"scene already exists: {scene['id']}")
        timeline["scenes"].append(scene)
        timeline["scenes"].sort(key=lambda x: (x["start_frame"], x["id"]))
        recompute_duration(project)
        return {"action": "remove_scene", "args": {"scene_id": scene["id"]}}

    if action == "update_scene":
        scene_id = args.get("scene_id")
        patch = args.get("patch")
        if not isinstance(patch, dict):
            raise CutGraphError("update_scene requires args.patch")
        index, previous = find_by_id(timeline["scenes"], scene_id)
        updated = deep_merge(previous, patch)
        updated["id"] = scene_id
        timeline["scenes"][index] = updated
        timeline["scenes"].sort(key=lambda x: (x["start_frame"], x["id"]))
        recompute_duration(project)
        return {"action": "update_scene", "args": {"scene_id": scene_id, "patch": previous}}

    if action == "remove_scene":
        scene_id = args.get("scene_id")
        index, previous = find_by_id(timeline["scenes"], scene_id)
        timeline["scenes"].pop(index)
        recompute_duration(project)
        return {"action": "add_scene", "args": {"scene": previous}}

    if action == "set_caption":
        caption = copy.deepcopy(args.get("caption"))
        if not isinstance(caption, dict):
            raise CutGraphError("set_caption requires args.caption")
        previous, _ = _upsert(timeline["captions"], caption)
        timeline["captions"].sort(key=lambda x: (x["start_frame"], x["id"]))
        recompute_duration(project)
        return ({"action": "set_caption", "args": {"caption": previous}} if previous is not None else {"action": "remove_caption", "args": {"caption_id": caption["id"]}})

    if action == "remove_caption":
        caption_id = args.get("caption_id")
        index, previous = find_by_id(timeline["captions"], caption_id)
        timeline["captions"].pop(index)
        recompute_duration(project)
        return {"action": "set_caption", "args": {"caption": previous}}

    if action == "set_audio_clip":
        audio = copy.deepcopy(args.get("audio"))
        if not isinstance(audio, dict):
            raise CutGraphError("set_audio_clip requires args.audio")
        previous, _ = _upsert(timeline["audio"], audio)
        timeline["audio"].sort(key=lambda x: (x["start_frame"], x["id"]))
        recompute_duration(project)
        return ({"action": "set_audio_clip", "args": {"audio": previous}} if previous is not None else {"action": "remove_audio_clip", "args": {"audio_id": audio["id"]}})

    if action == "remove_audio_clip":
        audio_id = args.get("audio_id")
        index, previous = find_by_id(timeline["audio"], audio_id)
        timeline["audio"].pop(index)
        recompute_duration(project)
        return {"action": "set_audio_clip", "args": {"audio": previous}}

    if action == "set_project":
        patch = args.get("patch")
        if not isinstance(patch, dict):
            raise CutGraphError("set_project requires args.patch")
        previous = copy.deepcopy(project["project"])
        project["project"] = deep_merge(project["project"], patch)
        return {"action": "set_project", "args": {"patch": previous}}

    if action == "set_delivery":
        patch = args.get("patch")
        if not isinstance(patch, dict):
            raise CutGraphError("set_delivery requires args.patch")
        previous = copy.deepcopy(project["delivery"])
        project["delivery"] = deep_merge(project["delivery"], patch)
        return {"action": "set_delivery", "args": {"patch": previous}}

    if action == "set_metadata":
        key = args.get("key")
        if not isinstance(key, str) or not key:
            raise CutGraphError("set_metadata requires args.key")
        metadata = project["project"].setdefault("metadata", {})
        existed = key in metadata
        previous = copy.deepcopy(metadata.get(key))
        if args.get("delete", False):
            metadata.pop(key, None)
        else:
            metadata[key] = copy.deepcopy(args.get("value"))
        if existed:
            return {"action": "set_metadata", "args": {"key": key, "value": previous}}
        return {"action": "set_metadata", "args": {"key": key, "delete": True}}

    raise CutGraphError(f"unhandled action: {action}")


def _simulate(project: dict[str, Any], operations: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    working = copy.deepcopy(project)
    inverses: list[dict[str, Any]] = []
    for operation in operations:
        inverse = _apply_one(working, operation)
        inverses.insert(0, inverse)
    validate_project(working)
    return working, inverses


def preflight(project: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    validate_project(project)
    normalized = normalize_operations(operations)
    working, inverses = _simulate(project, normalized)
    impact = build_impact_plan(project, working, normalized)
    return {
        "ok": True,
        "before_hash": project_hash(project),
        "predicted_after_hash": project_hash(working),
        "normalized_operations": normalized,
        "inverse_operations": inverses,
        "impact": impact,
        "verification": ["validate_project", "verify_affected_assets", impact["recommended_action"], "qa"],
    }


def apply_transaction(project: dict[str, Any], operations: list[dict[str, Any]], *, expected_project_hash: str | None = None, receipt_note: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    validate_project(project)
    before_hash = project_hash(project)
    if expected_project_hash is not None and expected_project_hash != before_hash:
        raise ConflictError(f"stale project hash: expected {expected_project_hash}, current {before_hash}")
    normalized = normalize_operations(operations)
    working, inverses = _simulate(project, normalized)
    working["history"]["version"] = int(project["history"]["version"]) + 1
    impact = build_impact_plan(project, working, normalized)
    after_hash = project_hash(working)
    receipt = {
        "id": f"tx-{uuid.uuid4().hex[:16]}",
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "version": working["history"]["version"],
        "before_hash": before_hash,
        "after_hash": after_hash,
        "operations": normalized,
        "inverse_operations": inverses,
        "impact": impact,
        "note": receipt_note,
    }
    working["history"]["receipts"] = copy.deepcopy(project["history"]["receipts"]) + [receipt]
    validate_project(working)
    return working, receipt


def undo_last(project: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipts = project.get("history", {}).get("receipts", [])
    if not receipts:
        raise CutGraphError("no transaction to undo")
    target = receipts[-1]
    operations = target.get("inverse_operations")
    if not isinstance(operations, list) or not operations:
        raise CutGraphError("last transaction has no inverse operations")
    updated, receipt = apply_transaction(project, operations, expected_project_hash=project_hash(project), receipt_note=f"undo:{target.get('id')}")
    receipt["undoes"] = target.get("id")
    updated["history"]["receipts"][-1] = receipt
    return updated, receipt
