import json
from pathlib import Path

import pytest
from PIL import Image

from agentcut import Editor
from agentcut.errors import AgentCutError
from agentcut.probe import probe
from agentcut.render import Renderer
from agentcut.util import ensure_binary, run


def make_image(path: Path, size=(640, 360), color=(80, 100, 120)):
    Image.new("RGB", size, color).save(path)


def test_state_getters_are_snapshots(tmp_path):
    img = tmp_path / "a.png"; make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img")
    e.add_scene("img", 1.0, scene_id="s")
    project = e.get_project()
    project["scenes"][0]["duration"] = 99
    scene = e.get_scene("s")
    scene["duration"] = 88
    assert e.get_scene("s")["duration"] == 1.0


def test_transaction_dry_run_and_conflict(tmp_path):
    img = tmp_path / "a.png"; make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img")
    e.add_scene("img", 1.0, scene_id="s")
    before = e.state_digest()
    versions_before = len(e.versions())
    projected = e.apply_operations(
        [{"action": "set_duration", "args": {"scene_id": "s", "duration": 2.0}}],
        expected_project_hash=before["project_hash"],
        dry_run=True,
    )
    assert projected["dry_run"] is True
    assert projected["project"]["scenes"][0]["duration"] == 2.0
    assert e.get_scene("s")["duration"] == 1.0
    assert len(e.versions()) == versions_before

    e.set_duration("s", 1.5)
    with pytest.raises(AgentCutError) as exc:
        e.apply_operations([], expected_project_hash=before["project_hash"])
    assert exc.value.code == "STATE_CONFLICT"


def test_hard_cut_has_exact_zero_overlap(tmp_path):
    a = tmp_path / "a.png"; b = tmp_path / "b.png"
    make_image(a); make_image(b, color=(120, 80, 60))
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(a, asset_id="a"); e.add_asset(b, asset_id="b")
    e.add_scene("a", 1.0, scene_id="a1")
    e.add_scene("b", 1.25, scene_id="b1")
    tl = e.get_timeline()
    assert tl["duration"] == pytest.approx(2.25)
    assert tl["scenes"][1]["start"] == pytest.approx(1.0)
    assert tl["transitions"][0]["effective_duration"] == 0.0


def test_camera_anchor_affects_renderer_expression(tmp_path):
    img = tmp_path / "a.png"; make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img"); e.add_scene("img", 1.0, scene_id="s")
    e.set_camera("s", motion="slow_push", amount=0.04, anchor="top_left")
    r = Renderer(e.root, e.get_project())
    vf = r._video_filter(e.get_scene("s"), r._profile("preview"), kind="image")
    assert "perspective=" in vf
    assert "x0='0':y0='0'" in vf
    assert "interpolation=cubic" in vf



def test_camera_motion_uses_subpixel_perspective_backend(tmp_path):
    img = tmp_path / "a.png"; make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=30)
    e.add_asset(img, asset_id="img"); e.add_scene("img", 3.0, scene_id="s")
    e.set_camera("s", motion="pan_right", amount=0.06, easing="linear", anchor="center")
    r = Renderer(e.root, e.get_project())
    vf = r._video_filter(e.get_scene("s"), r._profile("preview"), kind="image")
    assert "zoompan=" not in vf
    assert "perspective=" in vf
    assert "eval=frame" in vf
    assert "interpolation=cubic" in vf
    assert "scale=640:360:flags=lanczos" in vf

def test_image_metadata_recorded(tmp_path):
    img = tmp_path / "a.png"; make_image(img, size=(777, 333))
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    asset = e.add_asset(img, asset_id="img")
    assert asset["metadata"]["width"] == 777
    assert asset["metadata"]["height"] == 333


def test_invalid_effect_speed_rejected(tmp_path):
    img = tmp_path / "a.png"; make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img"); e.add_scene("img", 1.0, scene_id="s")
    with pytest.raises(AgentCutError) as exc:
        e.add_effect("s", "snow", speed=-1)
    assert exc.value.code == "INVALID_EFFECT_SPEED"


def test_video_source_in_and_playback_rate_render(tmp_path):
    ffmpeg = ensure_binary("ffmpeg")
    src = tmp_path / "src.mp4"
    run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src),
    ])
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=24)
    e.add_asset(src, asset_id="v")
    e.add_scene("v", 0.5, scene_id="s", source_in=0.25, playback_rate=2.0)
    out = e.render_scene("s")
    info = probe(out)
    actual = float(info["format"]["duration"])
    assert actual == pytest.approx(0.5, abs=0.08)


def test_transition_change_invalidates_visual_cache(tmp_path):
    a = tmp_path / "a.png"; b = tmp_path / "b.png"
    make_image(a, size=(320, 180)); make_image(b, size=(320, 180), color=(150, 80, 50))
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=24)
    e.add_asset(a, asset_id="a"); e.add_asset(b, asset_id="b")
    e.add_scene("a", 0.5, scene_id="s1"); e.add_scene("b", 0.5, scene_id="s2")
    e.render_preview()
    first = {p.name for p in (e.root / "cache").glob("visual_*.mp4")}
    e.set_transition("s1", "crossfade", 0.2)
    e.render_preview()
    second = {p.name for p in (e.root / "cache").glob("visual_*.mp4")}
    assert len(second) > len(first)


def test_api_inspection_path_is_sandboxed(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from agentcut.api import create_app

    img = tmp_path / "a.png"; make_image(img)
    root = tmp_path / "p"
    e = Editor.create(root, width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img"); e.add_scene("img", 1.0, scene_id="s")
    client = TestClient(create_app(root))
    response = client.get("/inspect/frame", params={"time": 0.0, "video": "/etc/passwd"})
    assert response.status_code == 400
    assert response.json()["error"] == "PATH_OUTSIDE_PROJECT"


def test_low_intensity_background_fog_renders(tmp_path):
    from PIL import Image
    from agentcut import Editor
    src = tmp_path / "src.png"
    Image.new("RGB", (640, 360), (20, 30, 40)).save(src)
    root = tmp_path / "project"
    e = Editor.create(root, width=640, height=360, fps=24)
    e.add_asset(src, asset_id="img")
    e.add_scene("img", 0.5, scene_id="scene_01")
    e.add_effect("scene_01", "fog", intensity=0.01, opacity=0.1, depth="background", seed=7)
    out = e.render_scene("scene_01", profile="preview")
    assert out.exists() and out.stat().st_size > 0


def test_mixed_cut_then_xfade_renders(tmp_path):
    from PIL import Image
    from agentcut import Editor
    sources=[]
    for i, color in enumerate([(20,30,40),(50,40,30),(30,50,40)], start=1):
        p=tmp_path/f"{i}.png"
        Image.new("RGB", (640,360), color).save(p)
        sources.append(p)
    root=tmp_path/"project"
    e=Editor.create(root,width=640,height=360,fps=24)
    for i,p in enumerate(sources, start=1):
        e.add_asset(p,asset_id=f"img{i}")
        e.add_scene(f"img{i}",0.7,scene_id=f"scene_{i:02d}")
    e.set_transition("scene_01","cut",0)
    e.set_transition("scene_02","crossfade",0.2)
    out=e.render_preview()
    assert out.exists() and out.stat().st_size>0
    report=e.qa(out)
    assert report["status"] == "pass"


def test_zero_byte_visual_cache_is_not_reused(tmp_path):
    from PIL import Image
    from agentcut import Editor
    src=tmp_path/"a.png"
    Image.new("RGB",(640,360),(10,20,30)).save(src)
    root=tmp_path/"project"
    e=Editor.create(root,width=640,height=360,fps=24)
    e.add_asset(src,asset_id="a")
    e.add_scene("a",0.5,scene_id="scene_01")
    e.add_scene("a",0.5,scene_id="scene_02")
    # Create a zero-byte file matching the visual cache name by rendering once, then corrupting it.
    out=e.render_preview()
    visual=next((root/"cache").glob("visual*.mp4"))
    visual.write_bytes(b"")
    out2=e.render_preview()
    assert visual.stat().st_size > 0
    assert out2.exists() and out2.stat().st_size > 0


def test_editor_inspection_helpers(tmp_path):
    from PIL import Image
    from agentcut import Editor
    src=tmp_path/"a.png"
    Image.new("RGB",(640,360),(22,32,42)).save(src)
    root=tmp_path/"project"
    e=Editor.create(root,width=640,height=360,fps=24)
    e.add_asset(src,asset_id="a")
    e.add_scene("a",0.6,scene_id="scene_01")
    video=e.render_preview()
    frame=e.extract_frame(video,tmp_path/"frame.jpg",time=0.2)
    sheet=e.contact_sheet(video,tmp_path/"sheet.jpg",interval=0.3)
    assert frame.exists() and frame.stat().st_size>0
    assert sheet.exists() and sheet.stat().st_size>0


def test_update_audio_tracks(tmp_path):
    import wave
    import numpy as np
    from PIL import Image
    from agentcut import Editor
    img=tmp_path/"a.png"; Image.new("RGB",(640,360),(10,20,30)).save(img)
    wav=tmp_path/"a.wav"
    with wave.open(str(wav),"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000); wf.writeframes(np.zeros(48000,dtype=np.int16).tobytes())
    e=Editor.create(tmp_path/"p",width=640,height=360,fps=24)
    e.add_asset(img,asset_id="img"); e.add_asset(wav,asset_id="aud")
    e.add_scene("img",1.0,scene_id="s1")
    st=e.add_scene_audio("s1","aud",duration=0.5)
    gt=e.add_audio_track("aud",duration=0.8)
    assert e.update_scene_audio("s1",st["id"],volume_db=-3)["volume_db"] == -3
    assert e.update_audio_track(gt["id"],volume_db=2)["volume_db"] == 2


def test_checkpoint_and_segment_restore(tmp_path):
    img = tmp_path / "a.png"; make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img")
    e.add_scene("img", 1.0, scene_id="s1")
    e.add_scene("img", 1.0, scene_id="s2")
    e.set_camera("s1", motion="slow_push", amount=0.02)
    e.set_camera("s2", motion="slow_push", amount=0.03)
    cp = e.create_checkpoint("baseline", note="known-good")
    assert cp["safe_name"] == "baseline"

    e.set_camera("s1", motion="pan_right", amount=0.08)
    e.set_camera("s2", motion="pan_left", amount=0.07)
    # Restore only s1: successful edits on s2 must remain untouched.
    restored = e.restore_scene("s1", checkpoint="baseline")
    assert restored["camera"]["type"] == "slow_push"
    assert e.get_scene("s2")["camera"]["type"] == "pan_left"
    hist = e.scene_history("s1")
    assert len(hist) >= 2
    assert hist[-1]["scene"]["camera"]["type"] == "slow_push"


def test_render_span_is_visual_only_and_does_not_mutate_project(tmp_path):
    a = tmp_path / "a.png"; b = tmp_path / "b.png"; c = tmp_path / "c.png"
    make_image(a, size=(320,180)); make_image(b, size=(320,180), color=(120,80,60)); make_image(c, size=(320,180), color=(60,120,80))
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=24)
    for aid,p in (("a",a),("b",b),("c",c)):
        e.add_asset(p, asset_id=aid)
        e.add_scene(aid, 0.5, scene_id=f"s{aid}")
    e.set_transition("sa", "crossfade", 0.15)
    e.set_transition("sb", "smooth_left", 0.15)
    before = e.state_digest()["project_hash"]
    out = e.render_span("sa", "sb", profile="preview")
    assert out.exists() and out.stat().st_size > 0
    assert e.state_digest()["project_hash"] == before
    info = probe(out)
    assert float(info["format"]["duration"]) == pytest.approx(0.85, abs=0.1)


def test_atomic_renderer_does_not_publish_failed_output(tmp_path, monkeypatch):
    img = tmp_path / "a.png"; make_image(img, size=(320,180))
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=24)
    e.add_asset(img, asset_id="a"); e.add_scene("a", 0.5, scene_id="s")
    from agentcut import render as render_mod
    original_run = render_mod.run
    calls = {"n": 0}
    def failing_run(cmd, *args, **kwargs):
        calls["n"] += 1
        target = Path(cmd[-1])
        target.write_bytes(b"partial")
        raise AgentCutError("PROCESS_FAILED", "simulated interruption")
    monkeypatch.setattr(render_mod, "run", failing_run)
    target = e.root / "preview" / "will_fail.mp4"
    with pytest.raises(AgentCutError):
        e.render_scene("s", output=target)
    assert not target.exists()
    assert not list(target.parent.glob(".*.partial.mp4"))
    monkeypatch.setattr(render_mod, "run", original_run)


def test_component_scoped_scene_restore_preserves_timing(tmp_path):
    img=tmp_path/'a.png'; make_image(img)
    e=Editor.create(tmp_path/'p',width=640,height=360,fps=24)
    e.add_asset(img,asset_id='img'); e.add_scene('img',1.0,scene_id='s')
    e.set_camera('s',motion='slow_push',amount=0.02)
    e.create_checkpoint('base')
    e.set_duration('s',1.4)
    e.set_transition('s','fade',0.2)
    e.set_camera('s',motion='pan_right',amount=0.08)
    e.restore_scene('s',checkpoint='base',components=['camera'])
    scene=e.get_scene('s')
    assert scene['camera']['type']=='slow_push'
    assert scene['duration']==pytest.approx(1.4)
    assert scene['transition_out']['type']=='fade'


def test_render_dag_preserves_cross_chunk_transition_semantics(tmp_path):
    from PIL import Image
    e = Editor.create(tmp_path / "p", width=320, height=180, fps=24)
    for i in range(6):
        img = tmp_path / f"{i}.png"
        Image.new("RGB", (320, 180), (20 + i * 20, 40, 80)).save(img)
        e.add_asset(img, asset_id=f"a{i}")
        e.add_scene(f"a{i}", 0.35, scene_id=f"s{i}")
        if i > 0:
            e.set_transition(f"s{i-1}", "fade", 0.08)
    r = Renderer(e.root, e.get_project())
    p = r._profile("preview")
    rendered = []
    for scene in e.get_project()["scenes"]:
        rendered.append(r._render_scene_base(scene, p))
    out, dur = r._combine_visuals(rendered, p)
    assert out.exists() and out.stat().st_size > 0
    assert dur == pytest.approx(e.get_timeline()["duration"], abs=1/24)


def test_transition_event_binds_visual_and_sfx_timing(tmp_path):
    from PIL import Image
    from agentcut import Editor
    from agentcut.render import Renderer
    from agentcut.util import ensure_binary, run
    ffmpeg = ensure_binary("ffmpeg")
    img = tmp_path / "a.png"; Image.new("RGB", (320,180), (40,50,60)).save(img)
    sfx = tmp_path / "whoosh.wav"
    run([ffmpeg,"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","sine=frequency=900:duration=0.25","-c:a","pcm_s16le",str(sfx)])
    e = Editor.create(tmp_path/"p", width=320, height=180, fps=24)
    e.add_asset(img, asset_id="img"); e.add_asset(sfx, asset_id="whoosh")
    e.add_scene("img",1.0,scene_id="s1"); e.add_scene("img",1.0,scene_id="s2")
    e.set_transition_event("s1","fade",0.2,sfx_asset_id="whoosh",sfx_volume_db=-9)
    r=Renderer(e.root,e.get_project())
    starts,total,_=r._timeline()
    tracks=r._collect_audio(starts,total)
    bound=next(t for t in tracks if t["id"]=="transition_sfx_s1")
    tr=e.get_timeline()["transitions"][0]
    assert bound["timeline_start"] == pytest.approx(tr["start"], abs=1e-6)
    assert e.get_scene("s1")["transition_out"]["sfx"]["asset_id"] == "whoosh"


def test_dialogue_segment_is_single_source_for_audio_caption_and_scene_fit(tmp_path):
    from PIL import Image
    from agentcut import Editor
    from agentcut.render import Renderer
    from agentcut.util import ensure_binary, run
    ffmpeg=ensure_binary("ffmpeg")
    img=tmp_path/"a.png"; Image.new("RGB",(320,180),(80,40,20)).save(img)
    voice=tmp_path/"voice.wav"
    run([ffmpeg,"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","sine=frequency=440:duration=0.50","-c:a","pcm_s16le",str(voice)])
    e=Editor.create(tmp_path/"p",width=320,height=180,fps=24)
    e.add_asset(img,asset_id="img"); e.add_asset(voice,asset_id="voice")
    e.add_scene("img",1.0,scene_id="s1")
    seg=e.add_dialogue_segment("s1","人类群众也可以旁听。",audio_asset_id="voice",fit_scene=True,padding=0.2)
    assert e.get_scene("s1")["duration"] == pytest.approx(0.7,abs=0.03)
    r=Renderer(e.root,e.get_project())
    caps=r._compiled_dialogue_captions()
    assert caps[0]["text"] == seg["text"]
    starts,total,_=r._timeline(); tracks=r._collect_audio(starts,total)
    dialogue=next(t for t in tracks if t["id"].startswith("dialogue_audio_"))
    assert dialogue["asset_id"] == "voice"
    assert dialogue["timeline_start"] == pytest.approx(0.0)


def test_rebuild_plan_limits_work_to_scene_neighbors(tmp_path):
    from PIL import Image
    from agentcut import Editor
    e=Editor.create(tmp_path/"p",width=320,height=180,fps=24)
    img=tmp_path/"a.png"; Image.new("RGB",(320,180),(1,2,3)).save(img)
    e.add_asset(img,asset_id="a")
    for i in range(5): e.add_scene("a",0.5,scene_id=f"s{i}")
    plan=e.rebuild_plan(["s2"])
    assert plan["render_scenes"] == ["s1","s2","s3"]
    assert plan["recommended_span"] == {"start_scene":"s1","end_scene":"s3"}


def test_audio_mix_is_padded_to_video_duration(tmp_path):
    from PIL import Image
    from agentcut import Editor
    from agentcut.util import ensure_binary, run
    ffmpeg=ensure_binary("ffmpeg")
    img=tmp_path/"a.png"; Image.new("RGB",(320,180),(20,30,40)).save(img)
    voice=tmp_path/"voice.wav"
    run([ffmpeg,"-hide_banner","-loglevel","error","-y","-f","lavfi","-i","sine=frequency=440:duration=0.25","-c:a","pcm_s16le",str(voice)])
    e=Editor.create(tmp_path/"p",width=320,height=180,fps=24)
    e.add_asset(img,asset_id="img"); e.add_asset(voice,asset_id="voice")
    e.add_scene("img",1.0,scene_id="s1")
    e.add_audio_track("voice",kind="dialogue",start=0,duration=0.25,fade_in=0,fade_out=0)
    out=e.render_preview()
    report=e.qa(out)
    assert not any(i["code"]=="AV_DURATION_MISMATCH" for i in report["issues"])
