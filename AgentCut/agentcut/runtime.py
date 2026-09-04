from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import inspect
from datetime import datetime, timezone

from .util import hash_obj, json_dump, json_load

PROTOCOL_VERSION = 5
RUNTIME_DIR = ".agentcut"
RUNTIME_STATE = "agent_runtime.json"


def _runtime_path(root: Path) -> Path:
    return root / RUNTIME_DIR / RUNTIME_STATE


def _safe_load(path: Path) -> dict:
    try:
        if path.exists():
            value = json_load(path)
            return value if isinstance(value, dict) else {}
    except Exception:
        pass
    return {}


def _signature_map(editor) -> dict[str, str]:
    out = {}
    for name, fn in sorted(editor._operation_map().items()):
        try:
            out[name] = str(inspect.signature(fn))
        except Exception:
            out[name] = "?"
    return out


def _schema_delta(previous: dict[str, str], current: dict[str, str]) -> dict:
    previous = previous or {}; current = current or {}
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(k for k in set(previous) & set(current) if previous[k] != current[k])
    return {"added": added, "removed": removed, "changed": changed, "unchanged_count": len(set(previous) & set(current)) - len(changed)}


def _compact_receipt(receipt: dict | None) -> dict | None:
    if not isinstance(receipt, dict):
        return None
    impact = receipt.get("impact") or {}
    verification = receipt.get("verification") or {}
    return {
        "transaction_id": receipt.get("transaction_id"),
        "project_hash": receipt.get("project_hash"),
        "actions": [x.get("action") for x in receipt.get("normalized_operations", []) if isinstance(x, dict)][:12],
        "changed_scenes": list(impact.get("changed_scene_ids") or impact.get("scenes") or [])[:12],
        "domains": list(impact.get("domains") or [])[:8],
        "render": verification.get("render") or verification.get("recommended_render"),
        "checks": list(verification.get("checks") or [])[:8],
    }


def record_agent_receipt(root: Path, receipt: dict) -> None:
    path = _runtime_path(Path(root))
    state = _safe_load(path)
    state["last_receipt"] = _compact_receipt(receipt)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    json_dump(path, state)


def save_agent_checkpoint(root: Path, *, goal: str | None = None, active_scene_ids: list[str] | None = None,
                          domains: list[str] | None = None, decisions: list[str] | None = None) -> dict:
    """Persist a tiny semantic checkpoint for cross-agent/restart continuation.

    It intentionally stores decisions, not chat history. This is the anti-token-bloat contract.
    """
    path = _runtime_path(Path(root)); state = _safe_load(path)
    clean_decisions = [str(x).strip() for x in (decisions or []) if str(x).strip()][:12]
    # Keep individual decision strings bounded so a checkpoint cannot become a transcript dump.
    clean_decisions = [x[:280] for x in clean_decisions]
    checkpoint = {
        "goal": str(goal).strip()[:500] if goal else None,
        "active_scene_ids": [str(x) for x in (active_scene_ids or [])][:16],
        "domains": [str(x) for x in (domains or [])][:12],
        "decisions": clean_decisions,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    state["checkpoint"] = checkpoint
    path.parent.mkdir(parents=True, exist_ok=True); json_dump(path, state)
    return checkpoint


def compact_bootstrap(editor, *, package_version: str, task: str | None = None, scene_ids: list[str] | None = None, domains: list[str] | None = None, write: bool = True) -> dict:
    root = editor.root
    runtime_file = _runtime_path(root)
    prior = _safe_load(runtime_file)
    state = editor.state_digest()
    project_hash = state.get("project_hash")
    scenes = editor.project.get("scenes", [])
    if scene_ids:
        wanted = set(scene_ids)
        scene_rows = [s for s in scenes if s.get("id") in wanted]
    else:
        scene_rows = scenes[:4]
    scene_summary = [
        {
            "id": s.get("id"),
            "duration": round(float(s.get("duration", 0)), 3),
            "asset_id": s.get("asset_id"),
            "transition": (s.get("transition_out") or {}).get("type", "cut"),
        }
        for s in scene_rows
    ]
    signatures = _signature_map(editor)
    tools_fingerprint = hash_obj(sorted(signatures.items()))[:16]
    same_protocol = int(prior.get("protocol_version", -1)) == PROTOCOL_VERSION
    same_package = str(prior.get("package_version")) == str(package_version)
    # The runtime file is project-local. A changed project hash usually means successful edits,
    # not a new project. Treat it as a warm resume instead of forcing a full reread.
    if prior and same_protocol and same_package:
        mode = "warm_resume"
    elif prior and same_protocol:
        mode = "upgrade_resume"
    else:
        mode = "cold_resume"
    delta = _schema_delta(prior.get("tool_signatures") or {}, signatures) if prior else {"added": sorted(signatures), "removed": [], "changed": [], "unchanged_count": 0}
    project_changed = bool(prior and prior.get("project_hash") != project_hash)
    checkpoint = prior.get("checkpoint") if isinstance(prior.get("checkpoint"), dict) else None
    last_receipt = prior.get("last_receipt") if isinstance(prior.get("last_receipt"), dict) else None
    capsule = {
        "protocol_version": PROTOCOL_VERSION,
        "package_version": package_version,
        "mode": mode,
        "project_hash": project_hash,
        "project_changed_since_last_bootstrap": project_changed,
        "resume_key": hash_obj({"p": project_hash, "v": package_version, "protocol": PROTOCOL_VERSION, "tools": tools_fingerprint})[:20],
        "task": str(task).strip()[:500] if task else (checkpoint or {}).get("goal"),
        "schema_fingerprint": tools_fingerprint,
        "schema_changed": bool(prior and prior.get("tools_fingerprint") != tools_fingerprint),
        "schema_delta": delta if mode == "upgrade_resume" or any(delta[k] for k in ("added","removed","changed")) else {"added": [], "removed": [], "changed": [], "unchanged_count": len(signatures)},
        "project": {
            "name": editor.project.get("name"),
            "video": deepcopy(editor.project.get("video", {})),
            "scene_count": len(scenes),
            "asset_count": len(editor.project.get("assets", {})),
            "caption_count": len(editor.project.get("captions", [])),
            "dialogue_count": len(editor.project.get("dialogue_segments", [])),
            "cast": sorted((editor.project.get("cast") or {}).keys()),
        },
        "scenes": scene_summary,
        "domains": list(domains or (checkpoint or {}).get("domains") or []),
        "checkpoint": checkpoint,
        "last_receipt": last_receipt,
        "read_policy": {
            "warm_resume": "Do not reread full docs/schema. Resume from checkpoint/last_receipt; request only touched scenes/domains.",
            "upgrade_resume": "Project-local memory is valid. Read only schema_delta operations plus release delta; do not fetch the full tool schema.",
            "cold_resume": "Read this capsule first, then fetch task-scoped /agent/context; avoid full project unless required.",
        }[mode],
        "next": ["task_scoped_agent_context", "preflight", "apply", "render_recommended_scope", "qa"],
        "previous": {
            "package_version": prior.get("package_version"),
            "protocol_version": prior.get("protocol_version"),
            "project_hash": prior.get("project_hash"),
        } if prior else None,
    }
    if write:
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        json_dump(runtime_file, {
            "package_version": package_version,
            "protocol_version": PROTOCOL_VERSION,
            "project_hash": project_hash,
            "resume_key": capsule["resume_key"],
            "tools_fingerprint": tools_fingerprint,
            "tool_signatures": signatures,
            "checkpoint": checkpoint,
            "last_receipt": last_receipt,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
    # Approximation only; intentionally avoids a tokenizer dependency.
    capsule["estimated_token_budget"] = max(1, len(str(capsule)) // 4)
    capsule["runtime_file"] = str(runtime_file)
    return capsule


def setup_runtime(editor, *, package_version: str) -> dict:
    root = editor.root / RUNTIME_DIR
    root.mkdir(parents=True, exist_ok=True)
    (root / "cache").mkdir(exist_ok=True)
    (root / "logs").mkdir(exist_ok=True)
    capsule = compact_bootstrap(editor, package_version=package_version, write=True)
    return {
        "ok": True,
        "runtime_dir": str(root),
        "bootstrap": capsule,
        "deployment": {
            "project_is_portable": True,
            "bundled_realesrgan": False,
            "lightweight_checkout": True,
            "github_source_complete": True,
            "asr_optional": True,
            "asr_env": ["AGENTCUT_WHISPER", "AGENTCUT_WHISPER_MODEL"],
            "asr_layout": "~/.agentcut/backends/whisper/{v1.9.0/**,models/ggml-tiny-q5_1.bin}",
            "asr_setup": "Windows x64: `agentcut asr-install --accept-third-party`. Installed backend/model persist across project upgrades.",
        },
    }
