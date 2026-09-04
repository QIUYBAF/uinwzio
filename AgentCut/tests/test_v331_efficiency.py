from __future__ import annotations

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image

from agentcut.agent_reliability import change_impact
from agentcut.editor import Editor
from agentcut.errors import AgentCutError
from agentcut.remotion_bridge import MANIFEST_SCHEMA


def seeded(tmp_path: Path, scenes=3) -> Editor:
    src = tmp_path / "frame.png"
    Image.new("RGB", (640, 360), "#334455").save(src)
    e = Editor.create(tmp_path / "project", width=640, height=360, fps=24, name="v331")
    e.add_asset(src, asset_id="frame")
    for i in range(scenes):
        e.add_scene("frame", 2.0, scene_id=f"s{i+1:02d}")
    return e


def test_remotion_v2_register_bind_export_and_verify(tmp_path):
    e = seeded(tmp_path)
    component = tmp_path / "Badge.tsx"
    component.write_text("export default ({text}:{text:string}) => <div>{text}</div>;", encoding="utf-8")
    row = e.register_remotion_component(component, component_id="badge", props_schema={
        "type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"], "additionalProperties": False,
    })
    assert len(row["source_sha256"]) == 64
    binding = e.bind_remotion_component("s02", "badge", start=.25, duration=.5, props={"text": "Hi"})
    assert binding["id"].startswith("rb_")
    out = tmp_path / "bundle"
    exported = e.export_gen3_remotion(out)
    assert exported["schema"] == MANIFEST_SCHEMA
    package = json.loads((out / "package.json").read_text())
    assert package["dependencies"]["remotion"] == "4.0.506"
    assert "latest" not in json.dumps(package)
    manifest = json.loads((out / "public/manifest.json").read_text())
    assert manifest["schema"] == MANIFEST_SCHEMA
    assert manifest["scenes"][1]["custom_components"][0]["from_frame"] == 6
    assert e.verify_remotion_bundle(out)["ok"] is True
    if shutil.which("node"):
        subprocess.run(["node", "scripts/verify-manifest.mjs"], cwd=out, check=True)


def test_remotion_binding_rejects_timing_and_props(tmp_path):
    e = seeded(tmp_path)
    component = tmp_path / "Badge.tsx"
    component.write_text("export default () => null;", encoding="utf-8")
    e.register_remotion_component(component, component_id="badge", props_schema={
        "type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]
    })
    with pytest.raises(AgentCutError):
        e.bind_remotion_component("s01", "badge", start=1.8, duration=.5, props={"value": 1})
    with pytest.raises(AgentCutError):
        e.bind_remotion_component("s01", "badge", start=0, duration=.5, props={"value": "1"})


def test_remotion_verify_detects_tamper(tmp_path):
    e = seeded(tmp_path)
    out = tmp_path / "bundle"
    e.export_gen3_remotion(out)
    path = out / "public/manifest.json"
    data = json.loads(path.read_text())
    data["schema"] = "tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AgentCutError):
        e.verify_remotion_bundle(out)


def test_structural_measure_is_honest_and_local(tmp_path):
    e = seeded(tmp_path, scenes=12)
    result = e.efficiency_measure([{"action": "camera", "args": {"scene": "s06", "type": "slow_push"}}])
    assert result["full_agent_context_bytes"] > result["warm_bootstrap_bytes"]
    assert result["context_payload_reduction_percent"] > 50
    assert result["full_render_frames"] == 576
    assert result["recommended_render_frames"] == 48
    assert result["render_work_reduction_percent"] > 80
    assert result["codex_usage_conclusion"] == "not_measured"


def test_efficiency_session_requires_actual_external_usage(tmp_path):
    e = seeded(tmp_path)
    s = e.efficiency_start(arm="agentcut", task_id="warm-edit")
    done = e.efficiency_finish(s["id"], actual_usage={"input_tokens": 100, "output_tokens": 20, "source": "codex export"}, elapsed_seconds=4, failed_commands=0, qa_issues=0)
    assert done["actual_usage"]["reported_as"] == "actual_external_measurement"
    with pytest.raises(AgentCutError):
        e.efficiency_finish(s["id"], actual_usage={"estimated_tokens": 10})


def test_ab_report_is_inconclusive_until_three_actual_runs_each(tmp_path):
    e = seeded(tmp_path)
    for arm in ("agentcut", "remotion"):
        s = e.efficiency_start(arm=arm, task_id="one")
        e.efficiency_finish(s["id"], actual_usage={"credits": 1 if arm == "agentcut" else 2}, elapsed_seconds=1, failed_commands=0, qa_issues=0)
    report = e.efficiency_report()
    assert report["verdict"] == "inconclusive"
    assert report["actual_usage_metric"] == "credits"


def test_dependency_dag_caption_audio_and_metadata(tmp_path):
    e = seeded(tmp_path)
    before = e.get_project()
    after = deepcopy(before)
    after["captions"].append({"id": "c1", "text": "x", "start": 2.2, "end": 2.8})
    cap = change_impact(before, after, [{"action": "add_caption"}])
    assert cap["render_scope"]["kind"] == "span"
    assert cap["render_scope"]["mode"] == "overlay_only"
    assert cap["render_scope"]["start_scene"] == "s02"

    after = deepcopy(before); after["audio_tracks"].append({"id": "a"})
    audio = change_impact(before, after, [{"action": "update_audio_track"}])
    assert audio["render_scope"]["kind"] == "audio_only"
    assert audio["render_scope"]["video_render_required"] is False

    after = deepcopy(before); after.setdefault("facts", {})["note"] = "x"
    facts = change_impact(before, after, [])
    assert facts["render_scope"]["kind"] == "none"

def test_api_surfaces_efficiency_and_remotion(tmp_path):
    from fastapi.testclient import TestClient
    from agentcut.api import create_app
    e = seeded(tmp_path)
    source = e.root / "Badge.tsx"
    source.write_text("export default () => null;", encoding="utf-8")
    client = TestClient(create_app(e.root))
    r = client.post("/remotion/components/register", json={"source":"Badge.tsx","component_id":"badge","props_schema":{"type":"object"}})
    assert r.status_code == 200, r.text
    r = client.post("/remotion/bindings", json={"scene_id":"s01","component_id":"badge","start":0.0,"duration":0.5,"props":{}})
    assert r.status_code == 200, r.text
    r = client.post("/efficiency/measure", json={"operations":[]})
    assert r.status_code == 200 and r.json()["codex_usage_conclusion"] == "not_measured"


def test_release_truth_check(tmp_path):
    from agentcut.release_check import check_release
    root = Path(__file__).resolve().parents[1]
    result = check_release(root, strict=True)
    assert result["ok"] is True, result
