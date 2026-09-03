from __future__ import annotations

from typing import Any

from .cutgraph import canonical_json, project_hash
from .operations import preflight


def _task_context(project: dict[str, Any], impact: dict[str, Any]) -> dict[str, Any]:
    spans = impact.get("spans", [])
    scenes = []
    asset_ids: set[str] = set()
    for scene in project["timeline"]["scenes"]:
        start = int(scene["start_frame"])
        end = start + int(scene["duration_frames"])
        if not spans or any(start < span_end and end > span_start for span_start, span_end in spans):
            scenes.append(scene)
            if scene.get("asset_id"):
                asset_ids.add(scene["asset_id"])
    return {
        "schema": project["schema"],
        "product": project["product"],
        "project": project["project"],
        "project_hash": project_hash(project),
        "affected_scenes": scenes,
        "affected_assets": {key: project["assets"][key] for key in sorted(asset_ids)},
        "impact": impact,
    }


def structural_efficiency_audit(project: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    plan = preflight(project, operations)
    full_bytes = len(canonical_json(project).encode("utf-8"))
    scoped = _task_context(project, plan["impact"])
    scoped_bytes = len(canonical_json(scoped).encode("utf-8"))
    full_frames = int(project["project"]["duration_frames"])
    affected_frames = int(plan["impact"].get("affected_video_frames", 0))
    return {
        "schema": "agentcut.director.efficiency-audit.v1",
        "project_hash": project_hash(project),
        "full_context_bytes": full_bytes,
        "task_scoped_context_bytes": scoped_bytes,
        "context_reduction_ratio": 0.0 if full_bytes == 0 else 1 - scoped_bytes / full_bytes,
        "full_video_frames": full_frames,
        "affected_video_frames": affected_frames,
        "video_frame_reduction_ratio": 0.0 if full_frames == 0 else 1 - affected_frames / full_frames,
        "impact": plan["impact"],
        "billing_claim": "not_measured",
        "billing_note": "Structural bytes/frames are proxies and are not Codex tokens or credits.",
    }
