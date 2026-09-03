from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

from .cutgraph import canonical_sha256, new_project, project_hash, recompute_duration, save_project, validate_project
from .identity import CLASSIC_FAMILY


def _asset_dict(raw: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw, dict):
        values = raw.values()
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("id") or item.get("asset_id") or f"asset-{index+1:03d}")
        kind = str(item.get("kind") or item.get("type") or "other").lower()
        if kind not in {"image", "video", "audio", "font", "data", "other"}:
            if kind in {"png", "jpg", "jpeg", "webp", "illustration"}:
                kind = "image"
            elif kind in {"mp3", "wav", "music", "sfx", "voice"}:
                kind = "audio"
            else:
                kind = "other"
        path = item.get("path") or item.get("source") or item.get("file") or f"MISSING/{asset_id}"
        result[asset_id] = {
            "id": asset_id,
            "kind": kind,
            "path": str(path),
            "sha256": item.get("sha256"),
            "metadata": {"classic_payload": copy.deepcopy(item)},
        }
    return result


def migrate_classic3(source: dict[str, Any], *, title: str | None = None) -> tuple[dict[str, Any], list[str]]:
    original = copy.deepcopy(source)
    warnings: list[str] = []
    info = source.get("project") if isinstance(source.get("project"), dict) else {}
    fps = int(info.get("fps") or source.get("fps") or 30)
    width = int(info.get("width") or source.get("width") or 1920)
    height = int(info.get("height") or source.get("height") or 1080)
    name = title or info.get("title") or source.get("title") or "Migrated Classic 3 Project"
    project = new_project(str(name), fps=fps, width=width, height=height)
    project["assets"] = _asset_dict(source.get("assets"))

    legacy_timeline = source.get("timeline") if isinstance(source.get("timeline"), dict) else {}
    raw_scenes = legacy_timeline.get("scenes") or source.get("scenes") or []
    cursor = 0
    for index, raw in enumerate(raw_scenes if isinstance(raw_scenes, list) else []):
        if not isinstance(raw, dict):
            continue
        scene_id = str(raw.get("id") or raw.get("scene_id") or f"s{index+1:03d}")
        start = int(raw.get("start_frame") if raw.get("start_frame") is not None else raw.get("start", cursor))
        duration = int(raw.get("duration_frames") if raw.get("duration_frames") is not None else raw.get("duration", fps * 3))
        if isinstance(raw.get("start"), float):
            start = round(float(raw["start"]) * fps)
        if isinstance(raw.get("duration"), float):
            duration = max(1, round(float(raw["duration"]) * fps))
        asset_id = raw.get("asset_id") or raw.get("asset") or raw.get("source_id")
        if asset_id is not None and asset_id not in project["assets"]:
            warnings.append(f"scene {scene_id} references unknown asset {asset_id}; reference cleared")
            asset_id = None
        project["timeline"]["scenes"].append({
            "id": scene_id,
            "kind": "visual",
            "start_frame": start,
            "duration_frames": max(1, duration),
            "asset_id": asset_id,
            "motion": copy.deepcopy(raw.get("motion") or {"type": "static"}),
            "metadata": {"classic_payload": copy.deepcopy(raw)},
        })
        cursor = max(cursor, start + max(1, duration))

    raw_captions = legacy_timeline.get("captions") or source.get("captions") or source.get("subtitles") or []
    for index, raw in enumerate(raw_captions if isinstance(raw_captions, list) else []):
        if not isinstance(raw, dict):
            continue
        start = raw.get("start_frame", raw.get("start", 0))
        duration = raw.get("duration_frames", raw.get("duration", fps * 2))
        if isinstance(start, float):
            start = round(start * fps)
        if isinstance(duration, float):
            duration = max(1, round(duration * fps))
        project["timeline"]["captions"].append({
            "id": str(raw.get("id") or f"cap-{index+1:03d}"),
            "start_frame": int(start),
            "duration_frames": max(1, int(duration)),
            "text": str(raw.get("text") or raw.get("content") or ""),
            "speaker": raw.get("speaker"),
            "style": copy.deepcopy(raw.get("style") or {}),
        })

    raw_audio = legacy_timeline.get("audio") or source.get("audio") or []
    for index, raw in enumerate(raw_audio if isinstance(raw_audio, list) else []):
        if not isinstance(raw, dict):
            continue
        asset_id = raw.get("asset_id") or raw.get("asset")
        if asset_id not in project["assets"]:
            warnings.append(f"audio item {index+1} references unknown asset and was skipped")
            continue
        start = raw.get("start_frame", raw.get("start", 0))
        duration = raw.get("duration_frames", raw.get("duration", fps * 3))
        if isinstance(start, float):
            start = round(start * fps)
        if isinstance(duration, float):
            duration = max(1, round(duration * fps))
        project["timeline"]["audio"].append({
            "id": str(raw.get("id") or f"audio-{index+1:03d}"),
            "asset_id": asset_id,
            "start_frame": int(start),
            "duration_frames": max(1, int(duration)),
            "volume": float(raw.get("volume", 1.0)),
            "metadata": {"classic_payload": copy.deepcopy(raw)},
        })

    project["project"]["metadata"]["migration"] = {
        "source_family": CLASSIC_FAMILY,
        "source_schema": source.get("schema"),
        "source_version": source.get("version") or (source.get("product") or {}).get("version"),
        "source_sha256": canonical_sha256(original),
        "migrated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "warnings": warnings,
    }
    recompute_duration(project)
    validate_project(project)
    if source != original:
        raise RuntimeError("migration mutated source document")
    return project, warnings


def migrate_file(source_path: str | Path, output_path: str | Path, *, overwrite: bool = False) -> dict[str, Any]:
    source_path = Path(source_path)
    output_path = Path(output_path)
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing file: {output_path}")
    source = json.loads(source_path.read_text(encoding="utf-8"))
    project, warnings = migrate_classic3(source)
    save_project(project, output_path)
    return {"output": str(output_path), "warnings": warnings, "project_hash": project_hash(project)}
