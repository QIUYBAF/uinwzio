from __future__ import annotations

import json
import math
import statistics
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import AgentCutError
from .timeline import build_timeline
from .util import json_dump, json_load

SESSION_SCHEMA = "agentcut.efficiency.session.v1"
ARMS = {"agentcut", "remotion"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact_bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _session_dir(root: Path) -> Path:
    path = root / ".agentcut" / "efficiency_sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _session_path(root: Path, session_id: str) -> Path:
    return _session_dir(root) / f"{session_id}.json"


def _percent_reduction(full: float | int, reduced: float | int) -> float | None:
    full = float(full)
    if full <= 0:
        return None
    return round((1.0 - float(reduced) / full) * 100.0, 2)


def _scope_seconds(project: dict, scope: dict) -> float:
    timeline = build_timeline(project)
    rows = {row["scene_id"]: row for row in timeline.get("scenes", [])}
    kind = scope.get("kind")
    if kind in {"none", "audio_only"}:
        return 0.0
    if kind == "scene":
        row = rows.get(scope.get("scene_id"))
        return float(row.get("duration", 0.0)) if row else 0.0
    if kind == "span":
        if "start" in scope and "end" in scope:
            return max(0.0, float(scope["end"]) - float(scope["start"]))
        start = rows.get(scope.get("start_scene")); end = rows.get(scope.get("end_scene"))
        if start and end:
            return max(0.0, float(end["end"]) - float(start["start"]))
    return float(timeline.get("duration", 0.0))


def structural_measure(editor, operations: list[dict] | None = None) -> dict:
    operations = list(operations or [])
    full_context = editor.agent_context(include_schema=True)
    warm = editor.agent_bootstrap(write=False)
    timeline = build_timeline(editor.project)
    fps = int(editor.project.get("video", {}).get("fps", 30))
    full_frames = max(0, int(round(float(timeline.get("duration", 0.0)) * fps)))
    preflight = editor.preflight_operations(operations) if operations else None
    scope = (preflight or {}).get("impact", {}).get("render_scope", {"kind": "full"})
    impacted_seconds = _scope_seconds((preflight or {}).get("projected_project", editor.project), scope)
    impacted_frames = max(0, int(round(impacted_seconds * fps)))
    if scope.get("kind") == "full":
        impacted_frames = full_frames
    return {
        "schema": "agentcut.efficiency.structural.v1",
        "measured_at": _now(),
        "project_hash": editor.state_digest()["project_hash"],
        "full_agent_context_bytes": _compact_bytes(full_context),
        "warm_bootstrap_bytes": _compact_bytes(warm),
        "context_payload_reduction_percent": _percent_reduction(_compact_bytes(full_context), _compact_bytes(warm)),
        "timeline_duration_seconds": float(timeline.get("duration", 0.0)),
        "fps": fps,
        "full_render_frames": full_frames,
        "recommended_render_scope": deepcopy(scope),
        "recommended_render_frames": impacted_frames,
        "render_work_reduction_percent": _percent_reduction(full_frames, impacted_frames),
        "operations": deepcopy(operations),
        "preflight_ok": None if preflight is None else bool(preflight.get("ok")),
        "codex_usage_conclusion": "not_measured",
        "usage_note": "Payload and render-frame reductions are structural measurements; Codex tokens/credits require externally supplied actual usage.",
    }


def start_session(editor, *, arm: str, task_id: str, metadata: dict | None = None) -> dict:
    arm = str(arm).strip().lower()
    if arm not in ARMS:
        raise AgentCutError("INVALID_EFFICIENCY_ARM", "arm must be agentcut or remotion", arm=arm)
    if not str(task_id).strip():
        raise AgentCutError("INVALID_EFFICIENCY_SESSION", "task_id must be non-empty")
    sid = f"eff_{uuid.uuid4().hex[:16]}"
    row = {
        "schema": SESSION_SCHEMA,
        "id": sid,
        "arm": arm,
        "task_id": str(task_id),
        "status": "running",
        "started_at": _now(),
        "project_hash_start": editor.state_digest()["project_hash"],
        "baseline": structural_measure(editor),
        "metadata": deepcopy(metadata or {}),
    }
    json_dump(_session_path(editor.root, sid), row)
    return deepcopy(row)


def _validate_actual_usage(value: dict | None) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AgentCutError("INVALID_ACTUAL_USAGE", "actual_usage must be an object")
    allowed = {"input_tokens", "output_tokens", "cached_input_tokens", "credits", "source"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise AgentCutError("INVALID_ACTUAL_USAGE", "Unsupported actual usage fields", extra=extra)
    out: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "cached_input_tokens"):
        if key in value:
            v = value[key]
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise AgentCutError("INVALID_ACTUAL_USAGE", f"{key} must be a non-negative integer")
            out[key] = v
    if "credits" in value:
        v = value["credits"]
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)) or float(v) < 0:
            raise AgentCutError("INVALID_ACTUAL_USAGE", "credits must be a non-negative finite number")
        out["credits"] = float(v)
    if "source" in value:
        out["source"] = str(value["source"])
    if not any(k in out for k in ("input_tokens", "output_tokens", "credits")):
        raise AgentCutError("INVALID_ACTUAL_USAGE", "actual_usage must contain measured tokens or credits")
    out["reported_as"] = "actual_external_measurement"
    return out


def finish_session(editor, session_id: str, *, actual_usage: dict | None = None,
                   elapsed_seconds: float | None = None, tool_calls: int | None = None,
                   failed_commands: int | None = None, rendered_frames: int | None = None,
                   qa_issues: int | None = None, notes: str | None = None) -> dict:
    path = _session_path(editor.root, session_id)
    row = json_load(path)
    if row.get("schema") != SESSION_SCHEMA or row.get("status") != "running":
        raise AgentCutError("INVALID_EFFICIENCY_SESSION", "Session is missing or already finished", session_id=session_id)
    metrics: dict[str, Any] = {}
    for key, value, numeric_type in (
        ("elapsed_seconds", elapsed_seconds, (int, float)),
        ("tool_calls", tool_calls, (int,)),
        ("failed_commands", failed_commands, (int,)),
        ("rendered_frames", rendered_frames, (int,)),
        ("qa_issues", qa_issues, (int,)),
    ):
        if value is None:
            continue
        if not isinstance(value, numeric_type) or isinstance(value, bool) or float(value) < 0 or not math.isfinite(float(value)):
            raise AgentCutError("INVALID_EFFICIENCY_METRIC", f"{key} must be non-negative", field=key)
        metrics[key] = float(value) if key == "elapsed_seconds" else int(value)
    row.update({
        "status": "completed",
        "finished_at": _now(),
        "project_hash_end": editor.state_digest()["project_hash"],
        "metrics": metrics,
        "actual_usage": _validate_actual_usage(actual_usage),
        "notes": None if notes is None else str(notes),
    })
    json_dump(path, row)
    return deepcopy(row)


def list_sessions(editor) -> list[dict]:
    rows = []
    for path in sorted(_session_dir(editor.root).glob("*.json")):
        try:
            row = json_load(path)
        except Exception:
            continue
        if row.get("schema") == SESSION_SCHEMA:
            rows.append(row)
    return rows


def _median(rows: list[dict], extractor) -> float | None:
    values = [extractor(r) for r in rows]
    if not values or any(v is None for v in values):
        return None
    return float(statistics.median(float(v) for v in values))


def benchmark_report(editor) -> dict:
    completed = [r for r in list_sessions(editor) if r.get("status") == "completed"]
    arms = {name: [r for r in completed if r.get("arm") == name] for name in sorted(ARMS)}
    metric = None
    if completed and all((r.get("actual_usage") or {}).get("credits") is not None for r in completed):
        metric = "credits"
        usage_extractor = lambda r: r["actual_usage"]["credits"]
    elif completed and all((r.get("actual_usage") or {}).get("input_tokens") is not None and (r.get("actual_usage") or {}).get("output_tokens") is not None for r in completed):
        metric = "total_tokens"
        usage_extractor = lambda r: r["actual_usage"]["input_tokens"] + r["actual_usage"]["output_tokens"]
    else:
        usage_extractor = lambda r: None
    summary = {}
    for arm, rows in arms.items():
        summary[arm] = {
            "completed_runs": len(rows),
            "median_actual_usage": _median(rows, usage_extractor),
            "median_elapsed_seconds": _median(rows, lambda r: (r.get("metrics") or {}).get("elapsed_seconds")),
            "median_failed_commands": _median(rows, lambda r: (r.get("metrics") or {}).get("failed_commands")),
            "median_qa_issues": _median(rows, lambda r: (r.get("metrics") or {}).get("qa_issues")),
        }
    enough = all(len(rows) >= 3 for rows in arms.values())
    a, r = summary["agentcut"], summary["remotion"]
    usage_reduction = _percent_reduction(r["median_actual_usage"], a["median_actual_usage"]) if enough and metric and r["median_actual_usage"] is not None else None
    time_reduction = _percent_reduction(r["median_elapsed_seconds"], a["median_elapsed_seconds"]) if enough and r["median_elapsed_seconds"] is not None else None
    fail_reduction = _percent_reduction(r["median_failed_commands"], a["median_failed_commands"]) if enough and r["median_failed_commands"] is not None else None
    qa_not_worse = None if not enough or a["median_qa_issues"] is None or r["median_qa_issues"] is None else a["median_qa_issues"] <= r["median_qa_issues"]
    gates = {
        "actual_usage_reduction_at_least_25_percent": None if usage_reduction is None else usage_reduction >= 25.0,
        "elapsed_reduction_at_least_25_percent": None if time_reduction is None else time_reduction >= 25.0,
        "failed_command_reduction_at_least_50_percent": None if fail_reduction is None else fail_reduction >= 50.0,
        "qa_not_worse": qa_not_worse,
    }
    conclusive = enough and metric is not None and all(v is not None for v in gates.values())
    verdict = "pass" if conclusive and all(gates.values()) else "fail" if conclusive else "inconclusive"
    return {
        "schema": "agentcut.efficiency.benchmark.v1",
        "generated_at": _now(),
        "actual_usage_metric": metric,
        "arms": summary,
        "reductions_percent": {"actual_usage": usage_reduction, "elapsed": time_reduction, "failed_commands": fail_reduction},
        "gates": gates,
        "verdict": verdict,
        "reason": None if conclusive else "At least 3 completed runs per arm and complete externally measured usage/time/failure/QA metrics are required.",
        "structural_evidence": structural_measure(editor),
    }
