from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from .errors import AgentCutError


REQUIRED_RUNTIME = [
    "agentcut/cli.py",
    "agentcut/editor.py",
    "agentcut/render.py",
    "agentcut/agent_reliability.py",
    "agentcut/runtime.py",
    "agentcut/subtitles.py",
    "agentcut/gen3.py",
    "run.py",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def check_release(root: str | Path, *, strict: bool = False) -> dict:
    root = Path(root)
    errors: list[str] = []
    checks: dict[str, object] = {}
    pyproject = tomllib.loads(_read(root / "pyproject.toml"))
    version = str(pyproject.get("project", {}).get("version", ""))
    checks["pyproject"] = version
    init_match = re.search(r'__version__\s*=\s*["\']([^"\']+)', _read(root / "agentcut/__init__.py"))
    init_version = init_match.group(1) if init_match else None
    checks["package"] = init_version
    if not version or init_version != version:
        errors.append(f"package version mismatch: pyproject={version!r}, __init__={init_version!r}")

    manifest = json.loads(_read(root / "agentcut.manifest.json") or "{}")
    checks["manifest"] = manifest.get("version")
    checks["github_source_complete"] = manifest.get("github_source_complete")
    if manifest.get("version") != version:
        errors.append("agentcut.manifest.json version is inconsistent")
    if manifest.get("github_source_complete") is not True:
        errors.append("manifest does not declare a complete GitHub source checkout")

    readme = _read(root / "README.md")
    checks["readme_mentions_version"] = version in readme
    if version not in readme:
        errors.append("README does not mention the current version")

    tools = json.loads(_read(root / "agent_tools.json") or "{}")
    checks["agent_tools"] = tools.get("version")
    if tools.get("version") != version:
        errors.append("agent_tools.json version is inconsistent")
    for name, path, key in (
        ("openapi", root / "openapi.json", ("info", "version")),
        ("project_schema", root / "project.schema.json", ("x-agentcut-version",)),
    ):
        data = json.loads(_read(path) or "{}")
        value = data
        for part in key:
            value = value.get(part) if isinstance(value, dict) else None
        checks[name] = value
        if value != version:
            errors.append(f"{path.name} version is inconsistent")

    runtime = {name: (root / name).is_file() for name in REQUIRED_RUNTIME}
    checks["runtime"] = runtime
    missing = [name for name, present in runtime.items() if not present]
    if missing:
        errors.append("missing runtime files: " + ", ".join(missing))

    forbidden = list((root / "agentcut/vendor").rglob("*.exe")) + list((root / "agentcut/vendor").rglob("*.bin")) if (root / "agentcut/vendor").exists() else []
    checks["heavy_binaries_absent"] = not forbidden
    if forbidden:
        errors.append("heavy optional binaries are present in the lightweight checkout")

    if strict:
        tests = list((root / "tests").glob("test_*.py"))
        checks["test_modules"] = len(tests)
        if not tests:
            errors.append("no regression tests found")

    return {"ok": not errors, "version": version, "checks": checks, "errors": errors, "strict": strict}


def require_release(root: str | Path, *, strict: bool = False) -> dict:
    result = check_release(root, strict=strict)
    if not result["ok"]:
        raise AgentCutError("RELEASE_INCONSISTENT", "Release truth check failed", errors=result["errors"])
    return result
