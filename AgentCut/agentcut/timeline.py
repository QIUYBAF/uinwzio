from __future__ import annotations

from .errors import AgentCutError


def effective_transition_duration(scene: dict, next_scene: dict | None) -> float:
    """Return the duration that actually overlaps two adjacent scenes.

    Hard cuts are exact and have zero overlap. Non-cut transitions are clamped only as a
    renderer safety net; project validation/QA should surface invalid declared values.
    """
    if next_scene is None:
        return 0.0
    tr = scene.get("transition_out") or {"type": "cut", "duration": 0.0}
    if tr.get("type", "cut") == "cut":
        return 0.0
    duration = max(0.0, float(tr.get("duration", 0.0)))
    max_overlap = min(float(scene.get("duration", 0.0)), float(next_scene.get("duration", 0.0)))
    if max_overlap <= 0:
        return 0.0
    return min(duration, max(0.0, max_overlap - 1e-6))


def build_timeline(project: dict) -> dict:
    scenes = project.get("scenes", [])
    if not scenes:
        return {"duration": 0.0, "scenes": [], "transitions": []}

    rows: list[dict] = []
    transitions: list[dict] = []
    start = 0.0
    for i, scene in enumerate(scenes):
        duration = float(scene["duration"])
        end = start + duration
        next_scene = scenes[i + 1] if i + 1 < len(scenes) else None
        declared = scene.get("transition_out") or {"type": "cut", "duration": 0.0}
        effective = effective_transition_duration(scene, next_scene)
        rows.append({"scene_id":scene["id"],"start":start,"end":end,"duration":duration,"transition_out":declared,"effective_transition_duration":effective})
        if next_scene is not None:
            transitions.append({"from_scene":scene["id"],"to_scene":next_scene["id"],"type":declared.get("type","cut"),"declared_duration":float(declared.get("duration",0.0)),"effective_duration":effective,"start":end-effective,"end":end})
            start=end-effective
        else:
            start=end
    return {"duration":start,"scenes":rows,"transitions":transitions}


def require_nonempty_timeline(project: dict) -> dict:
    timeline=build_timeline(project)
    if not timeline["scenes"]:
        raise AgentCutError("EMPTY_PROJECT", "Project has no scenes")
    return timeline
