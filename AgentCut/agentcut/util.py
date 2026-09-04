from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from .errors import AgentCutError


def ensure_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise AgentCutError("MISSING_BINARY", f"Required binary not found: {name}", binary=name)
    return path


def run(cmd: list[str], *, capture: bool = True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=capture)
    except subprocess.CalledProcessError as exc:
        raise AgentCutError(
            "PROCESS_FAILED",
            "External process failed",
            command=cmd,
            returncode=exc.returncode,
            stderr=(exc.stderr or "")[-5000:],
        ) from exc


def json_dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def json_load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentCutError("FILE_NOT_FOUND", "JSON file does not exist", path=str(path)) from exc


def hash_obj(obj) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
