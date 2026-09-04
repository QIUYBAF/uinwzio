from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from agentcut.editor import Editor
from agentcut.qa import run_qa
from agentcut.render import Renderer


def make_band_image(path: Path, size=(640, 360)):
    im = Image.new("RGB", size, "#161821")
    d = ImageDraw.Draw(im)
    # Four deliberately separated performer silhouettes so focus positions have meaning.
    colors = ["#ff7f9f", "#f6c85f", "#6ccff6", "#b58cff"]
    xs = [90, 240, 400, 545]
    for x, c in zip(xs, colors):
        d.ellipse((x-32, 62, x+32, 126), fill=c)
        d.rectangle((x-40, 122, x+40, 290), fill=c)
    im.save(path)


def seed(tmp_path: Path):
    src = tmp_path / "band.png"; make_band_image(src)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(src, asset_id="band")
    e.add_scene("band", 2.0, scene_id="s1")
    e.define_character("n", display_name="虹夏", focus_x=.16, focus_y=.48, color="#F6C85F", aliases=["nijika"])
    e.define_character("r", display_name="凉", focus_x=.63, focus_y=.48, color="#6CCFF6", aliases=["ryo"])
    return e


def test_cast_registry_and_speaker_alias_resolution(tmp_path):
    e = seed(tmp_path)
    seg = e.add_dialogue_segment("s1", "开始吧。", speaker="nijika", duration=1.0, position="auto", subtitle_style="band")
    assert seg["character_id"] == "n"
    assert seg["speaker"] == "nijika"  # caller label is preserved
    assert seg["position"] in {"top_right", "bottom_right"}
    assert e.state_digest()["cast_count"] == 2


def test_compose_dialogue_scene_builds_timing_subtitles_and_speaker_tracking(tmp_path):
    e = seed(tmp_path)
    result = e.compose_dialogue_scene("s1", [
        {"speaker": "虹夏", "text": "一、二、三，开始！", "emotion": "excited"},
        {"speaker": "凉", "text": "等等，我还没调完音。", "style": "aside"},
        {"speaker": "虹夏", "text": "你每次都这么说。"},
    ], pace="snappy", replace_existing=True)
    assert result["line_count"] == 3
    assert result["speaker_tracking"] is True
    assert result["direction_mode"] == "coverage"
    assert result["coverage_shots"] >= 3
    scene = e.get_scene("s1")
    assert len(scene["camera"].get("shot_path") or []) >= 3
    assert not scene["composition"].get("focus_path")
    assert scene["camera"]["amount"] == 0.0
    rows = [x for x in e.get_project()["dialogue_segments"] if x["scene_id"] == "s1"]
    assert len(rows) == 3
    assert all(x["max_line_chars"] == 18 for x in rows)
    assert rows[1]["subtitle_style"] == "aside"
    assert rows[0]["start"] < rows[1]["start"] < rows[2]["start"]


def test_recipe_is_idempotent_for_auto_dialogue_and_single_scene_is_inferred(tmp_path):
    e = seed(tmp_path)
    payload = {"action": "recipe", "recipe": "dialogue", "payload": {"lines": [
        {"speaker": "虹夏", "text": "第一遍。"},
        {"speaker": "凉", "text": "收到。"},
    ]}}
    a = e.apply_agent_operations(payload)
    assert a["ok"] is True
    assert any(r["kind"] == "single_scene_inference" for r in a["repairs"])
    e.apply_agent_operations(payload)
    rows = [x for x in e.get_project()["dialogue_segments"] if x["scene_id"] == "s1"]
    assert len(rows) == 2  # recipe replaces its scene dialogue rather than duplicating it


def test_band_performance_recipe_uses_cast_focus_path(tmp_path):
    e = seed(tmp_path)
    out = e.direct_performance_scene("s1", member_ids=["n", "r"], energy=.75, points=6)
    assert out["focus_points"] == 6
    assert out["crop_zoom"] > 1.1
    scene = e.get_scene("s1")
    xs = {round(x["x"], 2) for x in scene["composition"]["focus_path"]}
    assert .16 in xs and .63 in xs


def test_ass_subtitles_use_character_color_wrap_and_style(tmp_path):
    e = seed(tmp_path)
    e.compose_dialogue_scene("s1", [{
        "speaker": "虹夏",
        "text": "这是一句故意写得比较长的测试台词，用来验证自动换行不会把整句话挤在画面底部。",
        "style": "shout",
        "duration": 2.0,
        "max_line_chars": 14,
    }], fit_scene=True)
    r = Renderer(e.root, e.get_project())
    ass = r._make_ass(r._profile("preview"))
    text = ass.read_text(encoding="utf-8")
    assert "\\N" in text
    assert "\\fscx106" in text
    # F6C85F -> ASS BGR 5FC8F6
    assert "&H005FC8F6&" in text


def test_dialogue_qa_flags_unreadably_fast_lines(tmp_path):
    e = seed(tmp_path)
    e.add_dialogue_segment("s1", "这么长的一整句话不应该只在屏幕上闪现零点二秒钟。", duration=.2)
    qa = run_qa(e.root, e.get_project())
    assert any(x["code"] == "DIALOGUE_TOO_FAST" for x in qa["issues"])


def test_actual_dialogue_band_preview_renders(tmp_path):
    e = seed(tmp_path)
    e.compose_dialogue_scene("s1", [
        {"speaker": "虹夏", "text": "准备好了吗？", "duration": .7},
        {"speaker": "凉", "text": "随时。", "duration": .65},
    ], start=.1, gap=.08, fit_scene=True)
    out = e.render_preview(output=tmp_path / "band_dialogue.mp4")
    assert Path(out).exists() and Path(out).stat().st_size > 0
    cp = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(out)], capture_output=True, text=True, check=True)
    assert float(json.loads(cp.stdout)["format"]["duration"]) > 1.3


def make_silence_wav(path: Path, seconds=4.0, rate=8000):
    import wave
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))


def test_band_sequence_combines_rhythm_snap_and_member_direction(tmp_path):
    src = tmp_path / "band.png"; make_band_image(src)
    wav = tmp_path / "beat.wav"; make_silence_wav(wav)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(src, asset_id="band")
    e.add_asset(wav, asset_id="music")
    e.add_scene("band", 1.05, scene_id="s1")
    e.add_scene("band", 1.05, scene_id="s2")
    e.add_scene("band", 1.05, scene_id="s3")
    e.define_character("a", display_name="A", focus_x=.18, focus_y=.5)
    e.define_character("b", display_name="B", focus_x=.68, focus_y=.5)
    # Seed a known 120 BPM grid so this test verifies direction logic rather than onset analysis.
    e.project["assets"]["music"].setdefault("metadata", {})["rhythm"] = {
        "version": 1, "duration": 4.0, "tempo_bpm": 120.0,
        "beats": [0, .5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5], "onsets": [],
    }
    result = e.direct_band_sequence(["s1", "s2", "s3"], "music", energy=.8, member_ids=["a", "b"], snap_window=.12)
    assert len(result["directions"]) == 3
    assert all(x["beat_aligned"] for x in result["directions"])
    assert all(len(e.get_scene(s)["composition"]["focus_path"]) >= 2 for s in ["s1", "s2", "s3"])
    assert result["durations"][0] in {1.0, 1.05}


def test_reaction_recipe_resolves_display_name_and_creates_close_focus(tmp_path):
    e = seed(tmp_path)
    result = e.apply_scene_recipe("s1", "reaction", payload={"character": "凉", "intensity": .7})
    r = result["result"]
    assert r["character_id"] == "r"
    assert r["crop_zoom"] > 1.2
    scene = e.get_scene("s1")
    assert scene["composition"]["focus_path"][-1]["x"] == .63
    assert scene["camera"]["amount"] < .02


def test_low_structure_colon_script_and_chinese_agent_aliases(tmp_path):
    e = seed(tmp_path)
    check = e.preflight_operations({
        "action": "对话场景",
        "场景": "s1",
        "台词": ["虹夏：开始吧！", "凉：我知道。"],
        "pace": "snappy",
    })
    assert check["ok"] is True
    assert check["operations"][0]["action"] == "compose_dialogue_scene"
    e.apply_agent_operations({
        "action": "对话场景",
        "场景": "s1",
        "台词": ["虹夏：开始吧！", "凉：我知道。"],
        "pace": "snappy",
        "replace_existing": True,
    })
    rows = e.get_project()["dialogue_segments"]
    assert [x["speaker"] for x in rows] == ["虹夏", "凉"]
    assert [x["character_id"] for x in rows] == ["n", "r"]


def test_dialogue_duration_extension_on_only_scene_recommends_scene_render(tmp_path):
    e = seed(tmp_path)
    # Force the dialogue recipe to extend the only scene.
    check = e.preflight_operations({
        "action": "compose_dialogue_scene",
        "args": {
            "scene_id": "s1",
            "lines": [{"speaker": "虹夏", "text": "这一句故意拉得很长，用来确保对白时长会超过原镜头并触发时间线影响分析。", "duration": 5.0}],
            "fit_scene": True,
            "replace_existing": True,
        },
    })
    assert check["ok"] is True
    assert check["impact"]["duration_changed_scene_ids"] == ["s1"]
    assert check["impact"]["render_scope"] == {
        "kind": "scene", "scene_id": "s1", "reason": "duration_change_last_scene"
    }
    assert "render_scene:s1" in check["verification"]["recommended"]


def test_early_scene_duration_extension_recommends_tail_span(tmp_path):
    src = tmp_path / "band.png"; make_band_image(src)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(src, asset_id="band")
    for sid in ["s1", "s2", "s3"]:
        e.add_scene("band", 1.0, scene_id=sid)
    e.define_character("n", display_name="虹夏", focus_x=.18, focus_y=.5)
    check = e.preflight_operations({
        "action": "compose_dialogue_scene",
        "args": {
            "scene_id": "s1",
            "lines": [{"speaker": "虹夏", "text": "延长第一镜之后，后面的所有时间码都会整体后移。", "duration": 2.4}],
            "fit_scene": True,
            "replace_existing": True,
        },
    })
    assert check["ok"] is True
    assert check["impact"]["duration_changed_scene_ids"] == ["s1"]
    assert check["impact"]["timeline_shifted"] is True
    assert check["impact"]["render_scope"] == {
        "kind": "span", "start_scene": "s1", "end_scene": "s3", "reason": "timeline_shift_from_duration"
    }
    assert "render_span:s1..s3" in check["verification"]["recommended"]
