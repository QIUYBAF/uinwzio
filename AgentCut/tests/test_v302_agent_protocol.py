from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from agentcut.editor import Editor


def make_image(path: Path, size=(640, 360)):
    Image.new("RGB", size, "#334455").save(path)


def seeded_editor(tmp_path):
    src = tmp_path / "a.png"
    make_image(src)
    e = Editor.create(tmp_path / "p")
    e.add_asset(src, asset_id="hero")
    e.add_scene("hero", 2.0, scene_id="scene_01")
    e.add_scene("hero", 2.0, scene_id="scene_02")
    return e


def test_protocol_v2_accepts_singleton_flattened_alias_shape(tmp_path):
    e = seeded_editor(tmp_path)
    check = e.preflight_operations({"operation": "camera", "scene": "scene_01", "type": "slow_push", "amount": 0.02})
    assert check["ok"] is True
    assert check["schema_version"] == 5
    assert check["operations"] == [{"action": "set_camera", "args": {"scene_id": "scene_01", "motion": "slow_push", "amount": 0.02}}]
    kinds = {x["kind"] for x in check["repairs"]}
    assert {"singleton_operation", "shape_alias", "flattened_args", "action_alias"}.issubset(kinds)


def test_protocol_v2_accepts_root_wrapper_and_params(tmp_path):
    e = seeded_editor(tmp_path)
    payload = {"operations": [{"op": "filter", "params": {"scene": "scene_01", "filter": "cool"}}]}
    check = e.preflight_operations(payload)
    assert check["ok"] is True
    assert check["operations"][0]["action"] == "add_filter"
    assert check["operations"][0]["args"] == {"scene_id": "scene_01", "filter_id": "cool"}


def test_protocol_v2_repairs_unique_action_and_arg_typos(tmp_path):
    e = seeded_editor(tmp_path)
    check = e.preflight_operations([{"action": "set_transiton", "args": {"scene_id": "scene_01", "transiton": "fade", "duration": 0.2}}])
    assert check["ok"] is True
    assert check["operations"][0] == {"action": "set_transition", "args": {"scene_id": "scene_01", "transition": "fade", "duration": 0.2}}
    assert any(x["kind"] == "action_typo" for x in check["repairs"])
    assert any(x["kind"] == "arg_typo" for x in check["repairs"])


def test_preflight_is_compact_and_returns_impact_and_verification(tmp_path):
    e = seeded_editor(tmp_path)
    check = e.preflight_operations([{"action": "camera", "args": {"scene": "scene_01", "type": "slow_push"}}])
    assert check["ok"] is True
    assert "projected_state" not in check
    assert check["projected_digest"]["scene_count"] == 2
    assert check["impact"]["changed_scene_ids"] == ["scene_01"]
    assert check["impact"]["render_scope"]["kind"] == "scene"
    assert "qa_render" in check["verification"]["recommended"]

    verbose = e.preflight_operations([{"action": "camera", "args": {"scene": "scene_01", "type": "slow_push"}}], include_projected_state=True)
    assert "projected_state" in verbose
    assert len(json.dumps(check, ensure_ascii=False)) < len(json.dumps(verbose, ensure_ascii=False))


def test_apply_returns_compact_transaction_receipt(tmp_path):
    e = seeded_editor(tmp_path)
    h = e.state_digest()["project_hash"]
    result = e.apply_agent_operations({"action": "camera", "scene": "scene_01", "type": "slow_push"}, expected_project_hash=h)
    assert result["ok"] is True
    assert result["transaction_id"].startswith("tx_")
    assert result["state"]["project_hash"] == result["project_hash"]
    assert result["impact"]["render_scope"]["kind"] == "scene"
    assert "project" not in result and "results" not in result
    assert result["result_summaries"]


def test_agent_context_can_filter_schema_by_domain(tmp_path):
    e = seeded_editor(tmp_path)
    ctx = e.agent_context(scene_ids=["scene_01"], domains=["cinematic", "transition"])
    assert ctx["protocol_version"] == 5
    assert [x["id"] for x in ctx["context"]["scenes"]] == ["scene_01"]
    assert ctx["entities"]["scenes"] == ["scene_01", "scene_02"]
    assert ctx["operations"]
    assert {v["domain"] for v in ctx["operations"].values()} <= {"cinematic", "transition"}
    assert "set_cinematic_frame" in ctx["operations"]
    assert "set_camera" not in ctx["operations"]


def test_preflight_syntax_error_is_structured_not_exception(tmp_path):
    e = seeded_editor(tmp_path)
    check = e.preflight_operations({"action": "definitely_not_an_operation", "scene": "scene_01"})
    assert check["ok"] is False
    assert check["error"]["error"] == "UNSUPPORTED_OPERATION"


def test_missing_scene_preflight_includes_recovery_candidates(tmp_path):
    e = seeded_editor(tmp_path)
    check = e.preflight_operations({"action": "camera", "scene": "scene_001", "type": "slow_push"})
    assert check["ok"] is False
    assert check["error"]["error"] == "SCENE_NOT_FOUND"
    assert check["recovery"]["entity"] == "scenes"
    assert "scene_01" in check["recovery"]["suggestions"]


def test_http_agent_v2_accepts_flexible_operation_shape(tmp_path):
    from fastapi.testclient import TestClient
    from agentcut.api import create_app

    e = seeded_editor(tmp_path)
    client = TestClient(create_app(e.root))
    ctx = client.get("/agent/context", params={"domains": "visual,cinematic"})
    assert ctx.status_code == 200 and ctx.json()["protocol_version"] == 5
    response = client.post("/agent/preflight", json={
        "operations": {"operation": "camera", "scene": "scene_01", "type": "slow_push"},
        "expected_project_hash": e.state_digest()["project_hash"],
    })
    assert response.status_code == 200
    assert response.json()["ok"] is True

def test_transition_change_recommends_boundary_span(tmp_path):
    e = seeded_editor(tmp_path)
    check = e.preflight_operations({"action": "transition", "scene": "scene_01", "type": "fade", "duration": 0.25})
    assert check["ok"] is True
    assert check["impact"]["render_scope"] == {
        "kind": "span", "start_scene": "scene_01", "end_scene": "scene_02", "reason": "transition_boundary_change"
    }


def test_operation_schema_exposes_domain_types_and_aliases(tmp_path):
    e = seeded_editor(tmp_path)
    schema = e.operation_schema(actions=["set_camera"])
    row = schema["set_camera"]
    assert row["domain"] == "visual"
    assert "camera" in row["action_aliases"]
    assert row["argument_aliases"]["scene"] == "scene_id"
    assert "scene_id" in row["parameters"]
