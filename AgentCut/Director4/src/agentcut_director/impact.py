from __future__ import annotations

from typing import Any, Iterable


def _merge_spans(spans: Iterable[tuple[int, int]]) -> list[list[int]]:
    clean = sorted((max(0, int(a)), max(0, int(b))) for a, b in spans if int(b) > int(a))
    merged: list[list[int]] = []
    for start, end in clean:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged


def _scene_span(project: dict[str, Any], scene_id: str) -> tuple[int, int] | None:
    for scene in project["timeline"]["scenes"]:
        if scene.get("id") == scene_id:
            start = int(scene["start_frame"])
            return start, start + int(scene["duration_frames"])
    return None


def build_impact_plan(before: dict[str, Any], after: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    domains: set[str] = set()
    spans: list[tuple[int, int]] = []
    full_render = False
    conservative = False

    for operation in operations:
        action = operation["action"]
        args = operation.get("args", {})
        if action == "set_project":
            patch = args.get("patch", {})
            if any(key in patch for key in ("fps", "width", "height", "duration_frames")):
                domains.update({"visual", "captions", "audio", "timeline"})
                full_render = True
            else:
                domains.add("metadata")
        elif action in {"add_scene", "remove_scene", "update_scene"}:
            domains.update({"visual", "timeline"})
            scene_id = args.get("scene_id") or (args.get("scene") or {}).get("id")
            found = (_scene_span(before, scene_id) or _scene_span(after, scene_id)) if scene_id else None
            if found:
                spans.append(found)
            else:
                conservative = True
                full_render = True
        elif action in {"set_caption", "remove_caption"}:
            domains.add("captions")
            item = args.get("caption") or {}
            if not item and args.get("caption_id"):
                for source in (before, after):
                    item = next((x for x in source["timeline"]["captions"] if x.get("id") == args["caption_id"]), {})
                    if item:
                        break
            if item:
                start = int(item["start_frame"])
                spans.append((start, start + int(item["duration_frames"])))
        elif action in {"set_audio_clip", "remove_audio_clip"}:
            domains.add("audio")
            item = args.get("audio") or {}
            if not item and args.get("audio_id"):
                for source in (before, after):
                    item = next((x for x in source["timeline"]["audio"] if x.get("id") == args["audio_id"]), {})
                    if item:
                        break
            if item:
                start = int(item["start_frame"])
                spans.append((start, start + int(item["duration_frames"])))
        elif action in {"register_asset", "remove_asset"}:
            domains.add("assets")
        elif action in {"set_delivery", "set_metadata"}:
            domains.add("metadata")
        else:
            domains.add("unknown")
            conservative = True
            full_render = True

    duration = int(after["project"]["duration_frames"])
    merged = [[0, duration]] if full_render and duration else _merge_spans(spans)
    visual_frames = sum(end - start for start, end in merged) if "visual" in domains or "captions" in domains else 0
    audio_frames = sum(end - start for start, end in merged) if "audio" in domains else 0
    if domains == {"audio"}:
        recommendation = "remix_audio_span"
    elif not merged and domains <= {"metadata", "assets"}:
        recommendation = "no_preview_render"
    elif full_render:
        recommendation = "render_full_proxy"
    else:
        recommendation = "render_affected_spans"

    return {
        "domains": sorted(domains),
        "spans": merged,
        "full_render": full_render,
        "conservative": conservative,
        "recommended_action": recommendation,
        "affected_video_frames": visual_frames,
        "affected_audio_frames": audio_frames,
        "project_total_frames": duration,
    }
