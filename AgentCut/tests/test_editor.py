from pathlib import Path

from PIL import Image

from agentcut import Editor


def make_image(path: Path):
    Image.new("RGB", (640, 360), (80, 100, 120)).save(path)


def test_semantic_edit_and_history(tmp_path):
    img = tmp_path / "a.png"
    make_image(img)
    root = tmp_path / "project"
    e = Editor.create(root, width=640, height=360, fps=24, name="test")
    e.add_asset(img, asset_id="img")
    e.add_scene("img", 2.0, scene_id="scene_01")
    e.set_camera("scene_01", motion="slow_push", amount=0.04)
    e.add_effect("scene_01", "snow", intensity=0.2, seed=7)
    e.set_transition("scene_01", "fade_black", 0.3)
    assert e.get_scene("scene_01")["camera"]["type"] == "slow_push"
    assert e.get_scene("scene_01")["effects"][0]["seed"] == 7
    versions = e.versions()
    assert len(versions) >= 6
    before = len(e.get_scene("scene_01")["effects"])
    e.clear_effects("scene_01")
    assert not e.get_scene("scene_01")["effects"]
    e.undo()
    assert len(e.get_scene("scene_01")["effects"]) == before
    e.redo()
    assert not e.get_scene("scene_01")["effects"]


def test_asset_tags(tmp_path):
    img = tmp_path / "wuhan.png"
    make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="wuhan", tags={"location": "Wuhan", "weather": "cloudy"})
    assert e.find_assets(location="Wuhan")[0]["id"] == "wuhan"


def test_atomic_batch_rolls_back(tmp_path):
    img = tmp_path / "a.png"
    make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img")
    e.add_scene("img", 2.0, scene_id="s")
    versions_before = len(e.versions())
    try:
        e.apply_operations([
            {"action": "set_duration", "args": {"scene_id": "s", "duration": 3.0}},
            {"action": "set_camera", "args": {"scene_id": "missing", "motion": "slow_push", "amount": 0.03}},
        ])
    except Exception:
        pass
    assert e.get_scene("s")["duration"] == 2.0
    assert len(e.versions()) == versions_before
    result = e.apply_operations([
        {"action": "set_duration", "args": {"scene_id": "s", "duration": 3.0}},
        {"action": "set_camera", "args": {"scene_id": "s", "motion": "slow_push", "amount": 0.03}},
    ])
    assert result["applied"] == 2
    assert e.get_scene("s")["duration"] == 3.0
    assert len(e.versions()) == versions_before + 1
