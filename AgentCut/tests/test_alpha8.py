from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

from agentcut import Editor
from agentcut.visual import analyze_image_path


def _subject_image(path: Path, *, size=(800, 450), side="left") -> Path:
    im = Image.new("RGB", size, (22, 24, 27))
    d = ImageDraw.Draw(im)
    w, h = size
    if side == "left":
        x0 = int(w * 0.05)
    else:
        x0 = int(w * 0.70)
    d.rectangle((x0, int(h * 0.28), x0 + int(w * 0.25), int(h * 0.83)), fill=(235, 218, 184))
    d.ellipse((x0 + int(w * 0.07), int(h * 0.34), x0 + int(w * 0.18), int(h * 0.52)), fill=(25, 25, 27))
    im.save(path)
    return path


def _moving_video(path: Path) -> Path:
    frames = path.parent / "frames"
    frames.mkdir(exist_ok=True)
    for i in range(12):
        im = Image.new("RGB", (640, 360), (18, 20, 23))
        d = ImageDraw.Draw(im)
        x = int(40 + i * (480 / 11))
        d.rectangle((x, 100, x + 100, 280), fill=(235, 210, 180))
        d.ellipse((x + 25, 130, x + 75, 180), fill=(20, 20, 22))
        im.save(frames / f"{i:03d}.png")
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-framerate", "10", "-i", str(frames / "%03d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ], check=True)
    return path


def test_alpha8_saliency_finds_offcenter_subject_and_safe_caption(tmp_path: Path):
    src = _subject_image(tmp_path / "left.png", side="left")
    visual = analyze_image_path(src)
    assert visual["focus_x"] < 0.35
    assert visual["confidence"] > 0.15
    assert visual["caption_zone"] in {"top_right", "right", "bottom_right"}
    assert visual["zone_scores"]["right"] < visual["zone_scores"]["left"]


def test_alpha8_focus_aware_cover_really_preserves_edge_subject(tmp_path: Path):
    src = tmp_path / "wide.png"
    im = Image.new("RGB", (1400, 720), (10, 10, 10))
    ImageDraw.Draw(im).rectangle((0, 180, 80, 540), fill=(245, 245, 245))
    im.save(src)

    e = Editor.create(tmp_path / "p", width=1280, height=720, fps=24)
    aid = e.add_asset(src, asset_id="img")["id"]
    e.add_scene(aid, 0.5, scene_id="s1")
    e.set_composition("s1", mode="cover", focus_x=0.02, focus_y=0.5)
    out = e.render_scene("s1")
    frame = tmp_path / "frame.png"
    e.extract_frame(out, frame, time=0.2)
    pix = Image.open(frame).convert("RGB")
    left = ImageStat.Stat(pix.crop((0, 180, 40, 540))).mean
    assert sum(left) / 3 > 180  # subject survives the crop instead of being centered away


def test_alpha8_dynamic_focus_path_moves_crop_during_render(tmp_path: Path):
    src = tmp_path / "tracking.png"
    im = Image.new("RGB", (1800, 720), (10, 10, 10))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 200, 150, 520), fill=(240, 20, 20))
    d.rectangle((1650, 200, 1799, 520), fill=(20, 20, 240))
    im.save(src)

    e = Editor.create(tmp_path / "p", width=1280, height=720, fps=24)
    aid = e.add_asset(src, asset_id="img")["id"]
    e.add_scene(aid, 1.0, scene_id="s1")
    e.set_composition(
        "s1", mode="cover", focus_x=0.5, focus_y=0.5,
        focus_path=[{"t": 0, "x": 0.05, "y": 0.5}, {"t": 1, "x": 0.95, "y": 0.5}],
    )
    out = e.render_scene("s1")
    f1, f2 = tmp_path / "f1.png", tmp_path / "f2.png"
    e.extract_frame(out, f1, time=0.05)
    e.extract_frame(out, f2, time=0.90)
    a = Image.open(f1).convert("RGB")
    b = Image.open(f2).convert("RGB")
    left_early = ImageStat.Stat(a.crop((0, 180, 180, 540))).mean
    right_late = ImageStat.Stat(b.crop((1100, 180, 1280, 540))).mean
    assert left_early[0] > left_early[2] * 3
    assert right_late[2] > right_late[0] * 3


def test_alpha8_scene_video_analysis_creates_tracking_path(tmp_path: Path):
    video = _moving_video(tmp_path / "move.mp4")
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    aid = e.add_asset(video, asset_id="v")["id"]
    e.add_scene(aid, 1.0, scene_id="s1")
    visual = e.analyze_scene_visual("s1", sample_count=3)
    assert visual["movement"] > 0.08
    assert len(visual["focus_path"]) == 3
    assert visual["focus_path"][0]["x"] < visual["focus_path"][-1]["x"]
    applied = e.apply_visual_composition("s1", sample_count=3)
    assert applied["mode"] == "cover"
    assert applied["visual"]["tracking_points"] == 3


def test_alpha8_persisted_visual_analysis_enters_context_pack(tmp_path: Path):
    e = Editor.create(tmp_path / "p", width=800, height=450, fps=24)
    aid = e.add_asset(_subject_image(tmp_path / "left.png"), asset_id="img")["id"]
    analysis = e.analyze_visual(aid)
    pack = e.context_pack()
    assert pack["visual"][aid]["focus_x"] == analysis["focus_x"]
    e.add_scene(aid, 0.5, scene_id="s1")
    plan = e.suggest_composition("s1", text_hint="short title")
    assert plan["focus_x"] < 0.35
    assert plan["caption_zone"] in {"top_right", "right", "bottom_right"}


def test_alpha8_composition_changes_invalidate_scene_cache(tmp_path: Path):
    src = _subject_image(tmp_path / "src.png")
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    aid = e.add_asset(src, asset_id="img")["id"]
    e.add_scene(aid, 0.4, scene_id="s1")
    first = e.render_scene("s1")
    cache_before = {p.name for p in (e.root / "cache").glob("scene_s1_*.mp4")}
    e.set_composition("s1", mode="native_window", frame_scale=0.8)
    second = e.render_scene("s1")
    cache_after = {p.name for p in (e.root / "cache").glob("scene_s1_*.mp4")}
    assert first.exists() and second.exists()
    assert len(cache_after) > len(cache_before)


def test_alpha8_bulk_auto_compose_is_one_practical_workflow(tmp_path: Path):
    e = Editor.create(tmp_path / "p", width=800, height=450, fps=24)
    a1 = e.add_asset(_subject_image(tmp_path / "left.png", side="left"), asset_id="left")["id"]
    a2 = e.add_asset(_subject_image(tmp_path / "right.png", side="right"), asset_id="right")["id"]
    e.add_scene(a1, 0.4, scene_id="s1")
    e.add_scene(a2, 0.4, scene_id="s2")
    before = e.state_digest()["history_version"]
    result = e.auto_compose_scenes(sample_count=2)
    after = e.state_digest()["history_version"]
    assert result["applied"] == 2
    assert after == before + 1
    assert e.get_scene("s1")["composition"]["focus_x"] < 0.35
    assert e.get_scene("s2")["composition"]["focus_x"] > 0.60


def test_alpha8_dialogue_auto_position_uses_visual_composition(tmp_path: Path):
    e = Editor.create(tmp_path / "p", width=800, height=450, fps=24)
    aid = e.add_asset(_subject_image(tmp_path / "left.png", side="left"), asset_id="img")["id"]
    e.add_scene(aid, 1.0, scene_id="s1")
    e.apply_visual_composition("s1", text_hint="一句短字幕")
    seg = e.add_dialogue_segment("s1", "一句短字幕", start=0.1, duration=0.5, position="auto")
    assert seg["position"] in {"top_right", "right", "bottom_right"}


def test_alpha8_qa_flags_stacked_tracking_and_camera(tmp_path: Path):
    e = Editor.create(tmp_path / "p", width=800, height=450, fps=24)
    aid = e.add_asset(_subject_image(tmp_path / "left.png"), asset_id="img")["id"]
    e.add_scene(aid, 1.0, scene_id="s1")
    e.set_composition(
        "s1", mode="cover", focus_path=[{"t": 0, "x": 0.2, "y": 0.5}, {"t": 1, "x": 0.6, "y": 0.5}],
    )
    e.set_camera("s1", motion="slow_push", amount=0.04)
    codes = {issue["code"] for issue in e.qa()["issues"]}
    assert "STACKED_REFRAME_CAMERA" in codes
