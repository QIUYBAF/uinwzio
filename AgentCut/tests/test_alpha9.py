from __future__ import annotations

from pathlib import Path

from PIL import Image

from agentcut.cinematic import fragment_recipe, preset_frame_path
from agentcut.editor import Editor
from agentcut.project import validate_project


def _solid(path: Path, color=(210, 50, 35), size=(640, 360)):
    Image.new("RGB", size, color).save(path)


def _bands(path: Path, size=(640, 360)):
    im = Image.new("RGB", size)
    px = im.load()
    for y in range(size[1]):
        for x in range(size[0]):
            if x < size[0] // 3:
                px[x, y] = (230, 30, 30)
            elif x < size[0] * 2 // 3:
                px[x, y] = (30, 220, 50)
            else:
                px[x, y] = (30, 60, 230)
    im.save(path)


def test_frame_presets_and_recipe_are_deterministic():
    p = preset_frame_path("scope_lock", canvas_aspect=16 / 9)
    assert p[0]["aspect"] == round(16 / 9, 6)
    assert p[-1]["aspect"] == 2.39
    a = fragment_recipe("impact_cluster", count=5, intensity=.8)
    b = fragment_recipe("impact_cluster", count=5, intensity=.8)
    assert a == b
    assert abs(sum(x["duration_ratio"] for x in a) - 1) < 1e-9
    assert max(x["crop_zoom"] for x in a) > 1.5


def test_dynamic_aspect_ratio_renders_real_moving_bars(tmp_path: Path):
    src = tmp_path / "red.png"; _solid(src)
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 2.0, scene_id="s")
    e.set_cinematic_frame("s", preset="scope_lock")
    out = e.render_scene("s", profile="preview", output=tmp_path / "scope.mp4")
    f0 = tmp_path / "f0.png"; f1 = tmp_path / "f1.png"
    e.extract_frame(out, f0, time=.25)
    e.extract_frame(out, f1, time=1.55)
    a = Image.open(f0).convert("RGB"); b = Image.open(f1).convert("RGB")
    # Early frame remains full image; late frame has genuine black cinematic bars.
    assert sum(a.getpixel((320, 4))) > 120
    assert sum(b.getpixel((320, 4))) < 20
    assert sum(b.getpixel((320, 180))) > 120


def test_crop_zoom_is_immediate_focus_aware_closeup(tmp_path: Path):
    src = tmp_path / "bands.png"; _bands(src)
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 1.0, scene_id="s")
    e.set_composition("s", mode="cover", focus_x=.12, focus_y=.5, crop_zoom=2.0)
    out = e.render_scene("s", profile="preview", output=tmp_path / "zoom.mp4")
    frame = tmp_path / "zoom.png"; e.extract_frame(out, frame, time=.5)
    center = Image.open(frame).convert("RGB").getpixel((320, 180))
    assert center[0] > center[1] * 2 and center[0] > center[2] * 2


def test_fragment_scene_preserves_duration_and_transition(tmp_path: Path):
    src = tmp_path / "x.png"; _solid(src)
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 2.4, scene_id="s")
    e.add_scene("img", 1.0, scene_id="next")
    e.set_transition("s", "fade", .25)
    before = e.get_timeline()["duration"]
    result = e.fragment_scene("s", style="impact_cluster", count=5, intensity=.8)
    validate_project(e.get_project())
    assert len(result["fragment_ids"]) == 5
    assert abs(result["total_duration"] - 2.4) < 1e-6
    fragments = e.get_project()["scenes"][:5]
    assert all(x["transition_out"]["type"] == "cut" for x in fragments[:-1])
    assert fragments[-1]["transition_out"]["type"] == "fade"
    assert max(x["composition"]["crop_zoom"] for x in fragments) > 1.5
    # External timeline timing remains unchanged because internal fragments are hard cuts.
    assert abs(e.get_timeline()["duration"] - before) < 1e-6


def test_fragmentation_is_one_undoable_semantic_edit(tmp_path: Path):
    src = tmp_path / "x.png"; _solid(src)
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 2.0, scene_id="s")
    e.fragment_scene("s", style="detail_burst", count=5)
    assert len(e.get_project()["scenes"]) == 5
    e.undo()
    assert [x["id"] for x in e.get_project()["scenes"]] == ["s"]


def test_cinematic_treatment_is_agent_operation(tmp_path: Path):
    src = tmp_path / "x.png"; _solid(src)
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 3.2, scene_id="s")
    result = e.apply_operation("apply_cinematic_treatment", {"scene_id": "s", "style": "scope_lock"})
    assert result["plan"]["treatment"] == "scope_lock"
    assert e.get_scene("s")["cinematic"]["frame_path"][-1]["aspect"] == 2.39
