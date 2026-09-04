from __future__ import annotations

from pathlib import Path

from .probe import probe
from .util import hash_obj, json_dump


def manifest_path(output: Path) -> Path:
    return output.with_suffix(output.suffix + ".agentcut.json")


def write_render_manifest(output: Path, *, project: dict, profile: str, expected_duration: float, render_profile: dict, context: dict | None = None) -> Path:
    info = probe(output)
    data = {
        "agentcut_manifest_version": 1,
        "output": output.name,
        "profile": profile,
        "project_hash": hash_obj(project),
        "expected_duration": expected_duration,
        "render_profile": render_profile,
        "probe": info,
        "context": context or {},
    }
    path = manifest_path(output)
    json_dump(path, data)
    return path
