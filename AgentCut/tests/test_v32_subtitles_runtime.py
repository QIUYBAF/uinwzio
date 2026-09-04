from __future__ import annotations

import json
import os
import wave
from pathlib import Path

from PIL import Image

from agentcut import __version__
from agentcut.editor import Editor
from agentcut.render import Renderer
from agentcut.runtime import compact_bootstrap
from agentcut.subtitles import parse_srt, transcribe_media


def make_image(path: Path):
    Image.new("RGB", (640, 360), "#20242d").save(path)


def make_wav(path: Path, seconds=1.5, rate=16000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))


def seed(tmp_path: Path):
    img = tmp_path / "a.png"; make_image(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img")
    e.add_scene("img", 2.0, scene_id="s1")
    return e


def fake_whisper(path: Path):
    path.write_text(r'''#!/usr/bin/env python3
import json, sys
args=sys.argv[1:]
out=args[args.index('-of')+1] + '.json'
translated='-tr' in args
if translated:
    rows=[
      {'offsets': {'from': 0, 'to': 700}, 'text': 'Hello everyone.'},
      {'offsets': {'from': 750, 'to': 1450}, 'text': 'Let us begin.'},
    ]
    lang='zh'
else:
    rows=[
      {'offsets': {'from': 0, 'to': 700}, 'text': '大家好。'},
      {'offsets': {'from': 750, 'to': 1450}, 'text': '我们开始吧。'},
    ]
    lang='zh'
json.dump({'result': {'language': lang}, 'transcription': rows}, open(out,'w',encoding='utf-8'), ensure_ascii=False)
''', encoding="utf-8")
    path.chmod(0o755)


def test_bilingual_caption_is_structured_and_ass_renders_secondary_line(tmp_path):
    e = seed(tmp_path)
    cap = e.add_caption("下一首开始。", .1, 1.4, speaker="虹夏", subtitle_style="bilingual", secondary_text="Next song, go.", secondary_language="en")
    assert cap["secondary_text"] == "Next song, go."
    ass = Renderer(e.root, e.get_project())._make_ass(Renderer(e.root, e.get_project())._profile("preview"))
    text = ass.read_text(encoding="utf-8")
    assert "Next song, go." in text
    assert "\\N{\\fs" in text


def test_more_subtitle_styles_are_accepted(tmp_path):
    e = seed(tmp_path)
    for i, style in enumerate(["karaoke", "neon", "manga", "boxed", "cinematic", "lower_third"]):
        e.add_caption(style, .1 + i*.2, .25 + i*.2, subtitle_style=style)
    assert {x["subtitle_style"] for x in e.get_project()["captions"]} >= {"karaoke", "neon", "manga", "boxed", "cinematic", "lower_third"}


def test_parse_and_import_srt(tmp_path):
    e = seed(tmp_path)
    srt = tmp_path / "a.srt"
    srt.write_text("1\n00:00:00,100 --> 00:00:00,800\n第一句\n\n2\n00:00:00,900 --> 00:00:01,500\n第二句\n", encoding="utf-8")
    rows = parse_srt(srt)
    assert rows[0]["start"] == .1 and rows[1]["text"] == "第二句"
    out = e.import_subtitle_file(srt, subtitle_style="manga")
    assert out["count"] == 2
    assert all(x["subtitle_style"] == "manga" for x in e.get_project()["captions"])


def test_whisper_adapter_converts_audio_and_requires_real_json_product(tmp_path, monkeypatch):
    wav = tmp_path / "in.wav"; make_wav(wav)
    exe = tmp_path / "whisper-cli"; fake_whisper(exe)
    model = tmp_path / "ggml-tiny.bin"; model.write_bytes(b"fake")
    result = transcribe_media(wav, executable=str(exe), model=str(model), language="auto")
    assert result["language"] == "zh"
    assert result["segments"][0] == {"index": 0, "start": 0.0, "end": 0.7, "text": "大家好。"}


def test_auto_subtitles_can_create_bilingual_cues_with_overlap_alignment(tmp_path, monkeypatch):
    e = seed(tmp_path)
    wav = tmp_path / "voice.wav"; make_wav(wav)
    e.add_asset(wav, asset_id="voice")
    exe = tmp_path / "whisper-cli"; fake_whisper(exe)
    model = tmp_path / "ggml-tiny.bin"; model.write_bytes(b"fake")
    monkeypatch.setenv("AGENTCUT_WHISPER", str(exe))
    monkeypatch.setenv("AGENTCUT_WHISPER_MODEL", str(model))
    out = e.auto_subtitles("voice", bilingual=True, subtitle_style="bilingual")
    assert out["count"] == 2 and out["bilingual"] is True
    caps = e.get_project()["captions"]
    assert caps[0]["text"] == "大家好。"
    assert caps[0]["secondary_text"] == "Hello everyone."


def test_agent_bootstrap_warm_resume_and_project_change(tmp_path):
    e = seed(tmp_path)
    first = e.agent_bootstrap(task="fix subtitles", domains=["text"])
    assert first["mode"] == "cold_resume"
    second = e.agent_bootstrap(task="fix subtitles", domains=["text"])
    assert second["mode"] == "warm_resume"
    assert "Do not reread full docs" in second["read_policy"]
    e.add_caption("x", .1, .5)
    third = e.agent_bootstrap(task="fix subtitles", domains=["text"])
    assert third["mode"] == "warm_resume"
    assert third["project_changed_since_last_bootstrap"] is True


def test_upgrade_resume_does_not_require_full_project_reread(tmp_path):
    e = seed(tmp_path)
    a = compact_bootstrap(e, package_version="3.2.0", write=True)
    b = compact_bootstrap(e, package_version="3.2.1", write=True)
    assert b["mode"] == "upgrade_resume"
    assert b["schema_changed"] is False
    assert "schema_delta" in b["read_policy"]
    assert b["estimated_token_budget"] < 1000


def test_setup_runtime_creates_persistent_agent_state(tmp_path):
    e = seed(tmp_path)
    out = e.setup_runtime()
    assert out["ok"] is True
    runtime_file = Path(out["bootstrap"]["runtime_file"])
    assert runtime_file.exists()
    data = json.loads(runtime_file.read_text(encoding="utf-8"))
    assert data["package_version"] == __version__


def test_bilingual_qa_detects_missing_secondary_and_dense_pair(tmp_path):
    from agentcut.qa import run_qa
    e = seed(tmp_path)
    e.add_caption("主字幕", .1, .8, subtitle_style="bilingual")
    e.add_caption("这是一条非常非常长的中文主字幕用于测试双语密度检查。", .9, 1.8, subtitle_style="bilingual", secondary_text="This is also an intentionally very long translated subtitle used to test bilingual density checks.")
    qa = run_qa(e.root, e.get_project())
    codes = {x["code"] for x in qa["issues"]}
    assert "BILINGUAL_SECONDARY_MISSING" in codes
    assert "BILINGUAL_SPLIT_RECOMMENDED" in codes



def test_auto_subtitles_repeat_is_idempotent_and_uses_cache(tmp_path, monkeypatch):
    e = seed(tmp_path)
    wav = tmp_path / "voice_repeat.wav"; make_wav(wav)
    e.add_asset(wav, asset_id="voice_repeat")
    exe = tmp_path / "whisper-cli"; fake_whisper(exe)
    model = tmp_path / "ggml-tiny.bin"; model.write_bytes(b"fake")
    monkeypatch.setenv("AGENTCUT_WHISPER", str(exe))
    monkeypatch.setenv("AGENTCUT_WHISPER_MODEL", str(model))
    first = e.auto_subtitles("voice_repeat", bilingual=True, subtitle_style="bilingual")
    assert first["count"] == 2
    assert len(e.get_project()["captions"]) == 2
    assert all(c.get("generated_by") == "asr" and c.get("source_asset_id") == "voice_repeat" for c in e.get_project()["captions"])
    second = e.auto_subtitles("voice_repeat", bilingual=True, subtitle_style="bilingual")
    assert second["count"] == 2
    assert second["cache"]["primary_hit"] is True
    assert second["cache"]["translation_hit"] is True
    assert len(e.get_project()["captions"]) == 2


def test_caption_provenance_fields_validate_against_json_schema(tmp_path):
    import jsonschema
    e = seed(tmp_path)
    e.add_caption("auto", .1, .8)
    e.project["captions"][0]["generated_by"] = "asr"
    e.project["captions"][0]["source_asset_id"] = "voice"
    schema = json.loads((Path(__file__).parents[1] / "project.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(e.get_project(), schema)

def test_http_bootstrap_and_subtitle_status_endpoints(tmp_path):
    from fastapi.testclient import TestClient
    from agentcut.api import create_app
    e = seed(tmp_path)
    client = TestClient(create_app(e.root))
    boot = client.get("/agent/bootstrap", params={"task": "subtitle pass", "domains": "text"})
    assert boot.status_code == 200
    assert boot.json()["protocol_version"] == 5
    status = client.get("/subtitles/status")
    assert status.status_code == 200
    assert "bilingual" in status.json()["styles"]
