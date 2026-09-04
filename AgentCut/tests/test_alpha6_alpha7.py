from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from PIL import Image

from agentcut import Editor


def _image(path: Path, size=(640, 360), color=(30, 45, 65)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def _click_track(path: Path, *, bpm: float = 120.0, duration: float = 8.0, sr: int = 22050) -> Path:
    audio = np.zeros(int(sr * duration), dtype=np.float32)
    period = 60.0 / bpm
    for t in np.arange(0.0, duration, period):
        i = int(round(t * sr))
        n = min(int(0.035 * sr), len(audio) - i)
        if n <= 0:
            continue
        tt = np.arange(n, dtype=np.float32) / sr
        audio[i:i+n] += 0.8 * np.exp(-tt * 45.0) * np.sin(2 * np.pi * 1200 * tt)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def test_alpha6_rhythm_analysis_detects_120_bpm(tmp_path: Path):
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    wav = _click_track(tmp_path / "click.wav")
    aid = e.add_asset(wav, asset_id="bgm")["id"]
    analysis = e.analyze_audio_rhythm(aid)
    assert abs(float(analysis["tempo_bpm"]) - 120.0) < 0.8
    assert len(analysis["beats"]) >= 10
    pack = e.context_pack()
    assert pack["rhythm"]["bgm"]["beat_count"] == len(analysis["beats"])


def test_alpha6_rhythm_plan_accounts_for_transition_overlap(tmp_path: Path):
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    img = e.add_asset(_image(tmp_path / "x.png"), asset_id="img")["id"]
    wav = e.add_asset(_click_track(tmp_path / "click.wav"), asset_id="bgm")["id"]
    for sid in ("s1", "s2", "s3"):
        e.add_scene(img, 2.0, scene_id=sid)
    e.set_transition("s1", "fade", 0.5)
    e.set_transition("s2", "fade", 0.5)
    plan = e.rhythm_plan(["s1", "s2", "s3"], wav, snap_window=0.12)
    # semantic boundaries are 1.5s and 3.0s once overlap is accounted for
    assert abs(plan["starts"][1] - 1.5) < 0.13
    assert abs(plan["starts"][2] - 3.0) < 0.13
    result = e.apply_rhythm_plan(plan)
    assert result["applied"] == 3


def test_alpha6_shared_morph_renders_once(tmp_path: Path):
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    img = e.add_asset(_image(tmp_path / "x.png"), asset_id="img")["id"]
    e.add_scene(img, 0.8, scene_id="a")
    e.add_scene(img, 0.8, scene_id="b")
    e.add_layer("a", "rect", layer_id="card_a", shared_id="hero", x=40, y=80, width=160, height=90, fill="#ffffffcc")
    e.add_layer("b", "rect", layer_id="card_b", shared_id="hero", x=360, y=180, width=160, height=90, fill="#ffffffcc")
    e.set_transition("a", "shared_morph", 0.35)
    out = e.render_span("a", "b", profile="preview")
    assert out.exists() and out.stat().st_size > 0
    assert e.shared_element_plan("a", "b")[0]["mode"] == "morph"


def test_alpha7_auto_composition_preserves_4_3_source(tmp_path: Path):
    root = tmp_path / "p"
    e = Editor.create(root, width=1920, height=1080, fps=30)
    aid = e.add_asset(_image(tmp_path / "four_three.png", size=(1600, 1200)), asset_id="img")["id"]
    e.add_scene(aid, 1.0, scene_id="s1")
    plan = e.suggest_composition("s1")
    assert plan["mode"] == "native_window"
    assert plan["reason"] == "preserve_native_aspect_ratio"
    applied = e.apply_auto_composition("s1")
    assert applied["mode"] == "native_window"


def test_alpha7_low_res_source_uses_ambient_window(tmp_path: Path):
    root = tmp_path / "p"
    e = Editor.create(root, width=1920, height=1080, fps=30)
    aid = e.add_asset(_image(tmp_path / "low.png", size=(480, 270)), asset_id="img")["id"]
    e.add_scene(aid, 1.0, scene_id="s1")
    plan = e.suggest_composition("s1")
    assert plan["mode"] == "ambient"
    assert 0.35 <= plan["frame_scale"] < 0.85


def test_alpha7_ambient_render_and_corner_caption(tmp_path: Path):
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    aid = e.add_asset(_image(tmp_path / "portrait.png", size=(360, 640)), asset_id="img", tags={"focus_x": 0.25, "focus_y": 0.45})["id"]
    e.add_scene(aid, 0.6, scene_id="s1")
    e.set_composition("s1", mode="ambient", background="dim_blur", frame_scale=0.72, caption_zone="bottom_right")
    e.add_caption("composition aware", 0.0, 0.5, position="bottom_right", font_size=28, outline=2)
    out = e.render_preview()
    assert out.exists() and out.stat().st_size > 0
