from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentcut import roughcut as rc
from agentcut.cli import main
from agentcut.errors import AgentCutError


def event(start, end, score=1):
    return {"start": start, "end": end, "score": score, "label": "test"}


def test_context_clamps_and_merges_across_chunk_boundary():
    clips = rc.select_clips([event(1, 2), event(299, 300), event(300, 302), event(599, 600)], 600)
    assert [(c["start"], c["end"]) for c in clips] == [(0, 10), (287, 310), (587, 600)]
    assert [c["timeline_start"] for c in clips] == [0, 10, 33]


def test_budget_selects_whole_candidates_then_restores_source_order():
    clips = rc.select_clips([event(10, 15, .4), event(100, 105, .9), event(200, 205, .8)],
                            300, before=2, after=3, budget=20)
    assert [c["start"] for c in clips] == [98, 198]
    assert rc.select_clips([event(10, 15)], 60, budget=1) == []


@pytest.mark.parametrize("events", [[event(-1, 2)], [event(3, 2)], [event(2, math.nan)],
                                   [event(2, 3, 2)], {}, [None], [event(True, 2)]])
def test_invalid_events_rejected(events):
    with pytest.raises(AgentCutError):
        rc.select_clips(events, 10)


class FakeDetector:
    cache_key = "fake-v1"

    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def analyze(self, source, start, end, scratch):
        self.calls.append((start, end))
        if start == self.fail_at:
            raise RuntimeError("simulated interruption")
        return [event(start, min(start + 1, end))]


@pytest.fixture
def recording(tmp_path, monkeypatch):
    source = tmp_path / "recording.mp4"
    source.write_bytes(b"synthetic source identity")
    monkeypatch.setattr(rc, "inspect_source", lambda _: {"duration": 601.5, "audio_streams": 1})
    return source, tmp_path / "job"


def test_interruption_resume_and_selection_changes_reuse_analysis(recording):
    source, job = recording
    detector = FakeDetector(fail_at=300)
    with pytest.raises(RuntimeError):
        rc.analyze_recording(source, job, detector=detector)
    checkpoint = json.loads((job / "checkpoint.json").read_text())
    assert checkpoint["status"] == "interrupted" and checkpoint["completed"] == 1
    detector = FakeDetector()
    plan = rc.analyze_recording(source, job, detector=detector)
    assert detector.calls == [(300, 600), (600, 601.5)]
    assert plan["chunks"] == {"total": 3, "reused": 1}
    detector = FakeDetector()
    rc.analyze_recording(source, job, detector=detector, before=20)
    assert detector.calls == []
    assert not list(job.glob("decode-*"))


def test_source_and_detector_changes_invalidate_cache(recording):
    source, job = recording
    rc.analyze_recording(source, job, detector=FakeDetector())
    source.write_bytes(b"different content")
    detector = FakeDetector()
    assert rc.analyze_recording(source, job, detector=detector)["chunks"]["reused"] == 0
    detector.cache_key = "fake-v2"
    assert rc.analyze_recording(source, job, detector=detector)["chunks"]["reused"] == 0


def test_corrupt_chunk_recomputed(recording):
    source, job = recording
    plan = rc.analyze_recording(source, job, detector=FakeDetector())
    (job / "chunks" / plan["analysis_key"] / "000001.json").write_text("broken")
    detector = FakeDetector()
    assert rc.analyze_recording(source, job, detector=detector)["chunks"]["reused"] == 2
    assert detector.calls == [(300, 600)]


def test_job_lock_released_and_concurrent_write_rejected(tmp_path):
    path = tmp_path / ".lock"
    with rc.job_lock(path):
        with pytest.raises(AgentCutError, match="ROUGHCUT_BUSY"):
            with rc.job_lock(path):
                pass
    with rc.job_lock(path):
        pass


def test_six_hour_plan_has_bounded_chunks(recording, monkeypatch):
    source, job = recording
    monkeypatch.setattr(rc, "inspect_source", lambda _: {"duration": 21600, "audio_streams": 1})
    detector = FakeDetector()
    plan = rc.analyze_recording(source, job, detector=detector)
    assert plan["chunks"]["total"] == 72
    assert all(end - start <= 300 for start, end in detector.calls)


def test_no_audio_returns_empty_plan_with_warning(recording, monkeypatch):
    source, job = recording
    monkeypatch.setattr(rc, "inspect_source", lambda _: {"duration": 20, "audio_streams": 0})
    plan = rc.analyze_recording(source, job)
    assert plan["clips"] == [] and plan["warnings"]
    with pytest.raises(AgentCutError, match="EMPTY_ROUGHCUT"):
        rc.export_recording(job / "plan.json", job / "out.mp4")


def test_events_only_cli_and_editor_operations(recording, capsys):
    source, job = recording
    markers = source.parent / "events.json"
    markers.write_text(json.dumps([event(100, 105)]))
    assert main(["roughcut", str(source), str(job), "--events", str(markers)]) == 0
    assert json.loads(capsys.readouterr().out)["clips"] == 1
    ops = rc.editor_operations(job / "plan.json")
    assert ops[0]["action"] == "add_scene"
    assert ops[0]["args"]["source_in"] == 88
    assert ops[0]["args"]["duration"] == 25
    source.write_bytes(b"changed recording")
    with pytest.raises(AgentCutError, match="SOURCE_CHANGED"):
        rc.load_plan(job / "plan.json")


def test_non_object_plan_is_rejected(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text("[]")
    with pytest.raises(AgentCutError, match="INVALID_ROUGHCUT"):
        rc.load_plan(plan)


def test_core_cli_works_without_site_packages():
    runner = Path(__file__).parents[1] / "run.py"
    cp = subprocess.run([sys.executable, "-S", str(runner), "modules"], capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr
    result = json.loads(cp.stdout)
    assert result["core"]["ready"] and not result["editor"]["ready"]


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="FFmpeg integration tools unavailable")
def test_real_audio_detection_preview_and_visual_conform(tmp_path):
    source = tmp_path / "game's 回放.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=12",
                    "-f", "lavfi", "-i", "aevalsrc=if(between(t\\,4\\,6)\\,0.5*sin(2*PI*440*t)\\,0):s=8000:d=12",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(source)], check=True)
    job = tmp_path / "job"
    plan = rc.analyze_recording(source, job, chunk_seconds=5, before=1, after=1, merge_gap=0)
    assert len(plan["clips"]) == 1
    assert 2.5 <= plan["clips"][0]["start"] <= 3.5
    assert 6.5 <= plan["clips"][0]["end"] <= 7.5
    assert rc.analyze_recording(source, job, chunk_seconds=5, before=1, after=1, merge_gap=0)["chunks"]["reused"] == 3
    # A second separated marker exercises concat as well as selected-span encoding.
    plan = rc.analyze_recording(source, job, events=[event(4, 6), event(9, 10)], before=0, after=0, merge_gap=0)
    output = tmp_path / "preview.mp4"
    result = rc.export_recording(job / "plan.json", output)
    info = rc.inspect_source(output)
    assert result["audio_preserved"] and info["audio_streams"] == 1
    assert abs(info["duration"] - 3) < .15
    from agentcut import Editor
    editor = Editor.create(tmp_path / "project")
    editor.add_asset(source, asset_id="roughcut_source", copy=False)
    editor.apply_operations(rc.editor_operations(job / "plan.json"))
    assert len(editor.get_project()["scenes"]) == 2
    assert sum(s["duration"] for s in editor.get_project()["scenes"]) == 3
    with pytest.raises(AgentCutError, match="OUTPUT_EXISTS"):
        rc.export_recording(job / "plan.json", output)
