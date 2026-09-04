from __future__ import annotations

import difflib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .errors import AgentCutError
from .util import json_dump, json_load


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name).strip()).strip("._")
    if not value:
        raise AgentCutError("INVALID_CHECKPOINT", "Checkpoint name is empty after normalization", name=name)
    return value[:96]


class History:
    def __init__(self, root: Path):
        self.root = root / ".agentcut"
        self.file = self.root / "history.json"
        self.checkpoints_dir = self.root / "checkpoints"
        self.root.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self, project: dict) -> None:
        if not self.file.exists():
            json_dump(self.file, {"cursor": 0, "entries": [{"label": "init", "created_at": _utc_now(), "project": project}]})

    def _load(self) -> dict:
        return json_load(self.file)

    def commit(self, label: str, project: dict) -> int:
        h = self._load()
        cursor = int(h["cursor"])
        entries = h["entries"][: cursor + 1]
        entries.append({"label": label, "created_at": _utc_now(), "project": project})
        h = {"cursor": len(entries) - 1, "entries": entries}
        json_dump(self.file, h)
        return h["cursor"]

    def undo(self) -> dict:
        h = self._load()
        if h["cursor"] <= 0:
            raise AgentCutError("NO_UNDO", "No earlier version is available")
        h["cursor"] -= 1
        json_dump(self.file, h)
        return h["entries"][h["cursor"]]["project"]

    def redo(self) -> dict:
        h = self._load()
        if h["cursor"] >= len(h["entries"]) - 1:
            raise AgentCutError("NO_REDO", "No later version is available")
        h["cursor"] += 1
        json_dump(self.file, h)
        return h["entries"][h["cursor"]]["project"]

    def list_versions(self) -> list[dict]:
        h = self._load()
        return [
            {
                "version": i,
                "label": e["label"],
                "created_at": e.get("created_at"),
                "current": i == h["cursor"],
            }
            for i, e in enumerate(h["entries"])
        ]

    def get(self, version: int) -> dict:
        h = self._load()
        try:
            return h["entries"][version]["project"]
        except (IndexError, TypeError) as exc:
            raise AgentCutError("INVALID_VERSION", "Unknown history version", version=version) from exc

    def diff(self, a: int, b: int) -> str:
        pa = json.dumps(self.get(a), ensure_ascii=False, indent=2, sort_keys=True).splitlines(True)
        pb = json.dumps(self.get(b), ensure_ascii=False, indent=2, sort_keys=True).splitlines(True)
        return "".join(difflib.unified_diff(pa, pb, fromfile=f"version-{a}", tofile=f"version-{b}"))

    def create_checkpoint(self, name: str, project: dict, *, note: str | None = None) -> dict:
        safe = _safe_name(name)
        payload = {
            "name": name,
            "safe_name": safe,
            "created_at": _utc_now(),
            "note": note,
            "project": project,
        }
        path = self.checkpoints_dir / f"{safe}.json"
        json_dump(path, payload)
        return {k: v for k, v in payload.items() if k != "project"} | {"path": str(path)}

    def list_checkpoints(self) -> list[dict]:
        out = []
        for path in sorted(self.checkpoints_dir.glob("*.json")):
            try:
                payload = json_load(path)
                out.append({
                    "name": payload.get("name", path.stem),
                    "safe_name": payload.get("safe_name", path.stem),
                    "created_at": payload.get("created_at"),
                    "note": payload.get("note"),
                    "path": str(path),
                })
            except Exception:
                continue
        return out

    def get_checkpoint(self, name: str) -> dict:
        safe = _safe_name(name)
        path = self.checkpoints_dir / f"{safe}.json"
        if not path.exists():
            raise AgentCutError("CHECKPOINT_NOT_FOUND", "Unknown checkpoint", checkpoint=name)
        payload = json_load(path)
        project = payload.get("project")
        if not isinstance(project, dict):
            raise AgentCutError("INVALID_CHECKPOINT", "Checkpoint does not contain a valid project", checkpoint=name)
        return project
