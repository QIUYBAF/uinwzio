from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .cutgraph import CutGraph, CutGraphError, object_sha256


def _id(prefix: str, value: Any, index: int) -> str:
    raw = str(value or "").strip()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-")
    return safe or f"{prefix}-{index + 1:03d}"


def _scenes(project: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if isinstance(project.get("scenes"), list):
        return [x for x in project["scenes"] if isinstance(x, Mapping)]
    if isinstance(project.get("timeline"), Mapping) and isinstance(project["timeline"].get("scenes"), list):
        return [x for x in project["timeline"]["scenes"] if isinstance(x, Mapping)]
    return []


def _asset_items(raw: Any):
    if isinstance(raw, Mapping):
        for key in sorted(raw):
            value = raw[key]
            yield str(key), value if isinstance(value, Mapping) else {"path": value}
    elif isinstance(raw, list):
        for i, value in enumerate(raw):
            if isinstance(value, Mapping):
                yield _id("asset", value.get("id") or value.get("name"), i), value


def migrate_mapping(project: Mapping[str, Any], *, source: str | None = None) -> CutGraph:
    fps = float(project.get("fps") or project.get("frame_rate") or 30)
    width = int(project.get("width") or project.get("canvas_width") or 1920)
    height = int(project.get("height") or project.get("canvas_height") or 1080)
    assets: list[dict[str, Any]] = []
    asset_ids: set[str] = set()
    for i, (suggested, raw) in enumerate(_asset_items(project.get("assets", []))):
        asset_id = _id("asset", raw.get("id") or suggested, i)
        asset_ids.add(asset_id)
        item = {
            "id": asset_id,
            "kind": str(raw.get("kind") or raw.get("type") or "unknown"),
            "uri": str(raw.get("path") or raw.get("uri") or raw.get("src") or raw.get("file") or ""),
            "metadata": {k: copy.deepcopy(v) for k, v in raw.items() if k not in {"id", "kind", "type", "path", "uri", "src", "file", "sha256"}},
        }
        if raw.get("sha256"):
            item["sha256"] = str(raw["sha256"]).lower()
        assets.append(item)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    cursor = 0
    scenes = _scenes(project)
    for i, scene in enumerate(scenes):
        scene_id = _id("scene", scene.get("id") or scene.get("name"), i)
        if isinstance(scene.get("duration_frames"), (int, float)):
            length = max(1, int(round(float(scene["duration_frames"]))))
        else:
            length = max(1, int(round(float(scene.get("duration") or scene.get("duration_seconds") or 3) * fps)))
        if isinstance(scene.get("start_frame"), (int, float)):
            start = max(0, int(round(float(scene["start_frame"]))))
        elif isinstance(scene.get("start"), (int, float)):
            start = max(0, int(round(float(scene["start"]) * fps)))
        else:
            start = cursor
        node = {
            "id": scene_id, "kind": "scene", "track": "video.main",
            "start_frame": start, "duration_frames": length,
            "props": {"title": str(scene.get("title") or scene.get("name") or scene_id), "legacy_kind": scene.get("kind") or scene.get("type")},
        }
        for key in ("asset_id", "image_asset_id", "video_asset_id", "background_asset_id", "asset", "image", "video", "background"):
            value = scene.get(key)
            if value is not None and str(value) in asset_ids:
                node["asset_refs"] = [str(value)]
                break
        nodes.append(node)
        if i:
            edges.append({"from": nodes[i - 1]["id"], "to": scene_id, "relation": "follows"})
        captions = []
        for key in ("captions", "dialogue", "subtitles"):
            if isinstance(scene.get(key), list):
                captions.extend(x for x in scene[key] if isinstance(x, Mapping))
        for caption in captions:
            text = caption.get("text") or caption.get("content") or caption.get("line")
            if text is None:
                continue
            local_start = int(round(float(caption.get("start_frame") or float(caption.get("start") or 0) * fps)))
            if caption.get("duration_frames") is not None:
                cap_length = int(round(float(caption["duration_frames"])))
            elif caption.get("end") is not None:
                cap_length = int(round((float(caption["end"]) - float(caption.get("start") or 0)) * fps))
            else:
                cap_length = int(round(float(caption.get("duration") or 2) * fps))
            cap_id = _id("caption", caption.get("id"), len(nodes))
            nodes.append({
                "id": cap_id, "kind": "caption", "track": "text.captions", "parent": scene_id,
                "start_frame": start + max(0, local_start), "duration_frames": max(1, min(cap_length, length - max(0, local_start))),
                "props": {"text": str(text), "speaker": caption.get("speaker"), "language": caption.get("language")},
            })
            edges.append({"from": scene_id, "to": cap_id, "relation": "contains"})
        cursor = max(cursor, start + length)

    duration = max(cursor, int(project.get("duration_frames") or 1))
    return CutGraph.create(
        project_id=str(project.get("id") or project.get("project_id") or "migrated-project"),
        title=str(project.get("title") or project.get("name") or "Migrated Classic 3 project"),
        width=width, height=height, fps=fps, duration_frames=duration,
        assets=assets, nodes=nodes, edges=edges,
        extensions={
            "migration": {"from": "AgentCut Classic 3", "to": "AgentCut Director 4", "source": source, "source_sha256": object_sha256(project)},
            "legacy_project": copy.deepcopy(dict(project)),
        },
    )


def migrate_file(source: str | Path, output: str | Path) -> dict[str, Any]:
    source_path, output_path = Path(source), Path(output)
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise CutGraphError("INVALID_CLASSIC_PROJECT", "Classic 3 project must be an object")
    graph = migrate_mapping(raw, source=str(source_path))
    graph.write(output_path)
    report = {
        "schema": "agentcut.migration-report.v1", "ok": True,
        "source": str(source_path), "source_sha256": object_sha256(raw),
        "output": str(output_path), "cutgraph_sha256": graph.sha256,
        "validation": graph.validate().to_dict(), "legacy_payload_preserved": True,
    }
    report_path = output_path.with_suffix(output_path.suffix + ".migration.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report
