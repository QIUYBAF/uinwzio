from __future__ import annotations

import json
import tomllib
from pathlib import Path

from agentcut import __version__
from agentcut.cli import main
from agentcut.director import choose_backend
from agentcut.discovery import discover
from agentcut.doctor import run_doctor


ROOT = Path(__file__).parents[1]


def test_release_truth_and_full_lightweight_runtime_are_consistent():
    manifest = json.loads((ROOT / "agentcut.manifest.json").read_text(encoding="utf-8"))
    tools = json.loads((ROOT / "agent_tools.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == manifest["version"] == tools["version"] == pyproject["project"]["version"] == "1.0.1"
    assert manifest["github_source_complete"] is True
    for name in ("editor.py", "render.py", "agent_reliability.py", "runtime.py", "subtitles.py", "gen3.py"):
        assert (ROOT / "agentcut" / name).is_file()


def test_discovery_does_not_require_a_project():
    result = discover()
    assert result["release"] == "1.0.1-remaster"
    assert result["backend"]["selected"] in {"ffmpeg/pillow", "pillow-only", "unavailable"}


def test_node_alone_is_not_reported_as_remotion(monkeypatch):
    import agentcut.director as director
    monkeypatch.setattr(director, "_local_remotion", lambda project_root=None: None)
    result = choose_backend(needs_react_ui=True)
    assert result["remotion_available"] is False
    assert result["selected"] != "remotion"


def test_doctor_degrades_instead_of_crashing_without_external_tools(monkeypatch):
    import agentcut.doctor as doctor
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    result = run_doctor()
    assert result["status"] == "degraded"
    assert result["editing_ready"] is True
    assert result["rendering_ready"] is False
    assert result["suggestions"]


def test_quickstart_creates_project_and_bootstrap(tmp_path, capsys):
    project = tmp_path / "project"
    assert main(["quickstart", str(project), "--create", "--task", "Make a short edit"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "ready"
    assert result["created"] is True
    assert result["bootstrap"]["task"] == "Make a short edit"
    assert (project / "project.json").is_file()
    assert (project / ".agentcut" / "agent_runtime.json").is_file()
