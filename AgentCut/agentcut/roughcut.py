"""Dependency-free long-recording planning; media stays outside project state."""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from .errors import AgentCutError
from .util import ensure_binary, hash_obj


def number(value, name, minimum=0.0, maximum=float("inf")):
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float("nan")
    if isinstance(value, bool) or not math.isfinite(result) or not minimum <= result <= maximum:
        raise AgentCutError("INVALID_ROUGHCUT", f"Invalid {name}", field=name)
    return result


def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def job_lock(path: Path):
    """OS-owned lock is released on crashes; the small lock file may remain."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise AgentCutError("ROUGHCUT_BUSY", "This job is already running", path=str(path)) from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def fingerprint(source: Path):
    source = source.expanduser().resolve()
    if not source.is_file():
        raise AgentCutError("FILE_NOT_FOUND", "Recording does not exist", path=str(source))
    stat = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        digest.update(stream.read(1024 * 1024))
        stream.seek(max(0, stat.st_size - 1024 * 1024))
        digest.update(stream.read(1024 * 1024))
    return {"path": str(source), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "sample_sha256": digest.hexdigest()}


def media_run(command, timeout=120):
    try:
        return subprocess.run(command, check=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise AgentCutError("MEDIA_TIMEOUT", "Media processing timed out; completed chunks can be resumed") from exc
    except subprocess.CalledProcessError as exc:
        raise AgentCutError("PROCESS_FAILED", "Media processing failed",
                            stderr=(exc.stderr or b"")[-3000:].decode("utf-8", errors="replace")) from exc


def inspect_source(source: Path):
    data = json.loads(media_run([ensure_binary("ffprobe"), "-v", "error", "-show_entries",
                                "format=duration:stream=codec_type", "-of", "json", str(source)]).stdout)
    if not any(s.get("codec_type") == "video" for s in data.get("streams", [])):
        raise AgentCutError("INVALID_ROUGHCUT", "Recording must contain a video stream")
    return {"duration": number(data.get("format", {}).get("duration"), "duration", 0.001),
            "audio_streams": sum(s.get("codec_type") == "audio" for s in data.get("streams", []))}


class Detector(Protocol):
    """Optional analyzers return absolute source-time events and a stable cache key.

    Change cache_key whenever algorithm, model, settings or external inputs change.
    Each call owns only one bounded chunk. No dynamic code is loaded from plans.
    """
    cache_key: str

    def analyze(self, source: Path, start: float, end: float, scratch: Path) -> list[dict]: ...


def validate_events(events, duration):
    if not isinstance(events, list):
        raise AgentCutError("INVALID_ROUGHCUT", "Events must be a JSON list")
    clean = []
    for event in events:
        if not isinstance(event, dict):
            raise AgentCutError("INVALID_ROUGHCUT", "Each event must be an object")
        start = number(event.get("start"), "event.start", 0, duration)
        end = number(event.get("end"), "event.end", 0, duration)
        if end <= start:
            raise AgentCutError("INVALID_ROUGHCUT", "Event end must be after start")
        label = event.get("label", "external_event")
        if not isinstance(label, str) or not label.strip():
            raise AgentCutError("INVALID_ROUGHCUT", "Event label must be non-empty text")
        clean.append({"start": start, "end": end,
                      "score": number(event.get("score", 1), "event.score", 0, 1), "label": label})
    return sorted(clean, key=lambda e: (e["start"], e["end"]))


def select_clips(events, duration, *, before=12, after=8, merge_gap=5, budget=None):
    duration = number(duration, "duration", 0.001)
    before = number(before, "before", 0, 600)
    after = number(after, "after", 0, 600)
    merge_gap = number(merge_gap, "merge_gap", 0, 600)
    budget = number(budget, "budget", 0.001) if budget is not None else None
    clips = []
    for event in validate_events(events, duration):
        start, end = max(0, event["start"] - before), min(duration, event["end"] + after)
        if clips and start <= clips[-1]["end"] + merge_gap:
            clip = clips[-1]
            clip["end"] = max(clip["end"], end)
            clip["score"] = max(clip["score"], event["score"])
            clip["reasons"] = sorted(set(clip["reasons"] + [event["label"]]))
        else:
            clips.append({"start": start, "end": end, "score": event["score"], "reasons": [event["label"]]})
    if budget is not None:
        selected, remaining = [], budget
        for clip in sorted(clips, key=lambda c: (-c["score"], c["start"])):
            length = clip["end"] - clip["start"]
            # Never truncate the context just to fill a target duration.
            if length <= remaining + 1e-6:
                selected.append(clip)
                remaining -= length
        clips = sorted(selected, key=lambda c: c["start"])
    offset = 0.0
    for i, clip in enumerate(clips):
        clip.update(id=f"clip_{i + 1:04d}", timeline_start=round(offset, 6))
        offset += clip["end"] - clip["start"]
    return clips


def analyze_recording(source, job, *, detector=None, events=None, chunk_seconds=300,
                      before=12, after=8, merge_gap=5, budget=None, audio_stream=0,
                      audio_threshold=-28, progress=None):
    source, job = Path(source).expanduser().resolve(), Path(job).expanduser().resolve()
    chunk_seconds = number(chunk_seconds, "chunk_seconds", 1, 900)
    # Validate selection settings even for an empty recording result.
    select_clips([], 1, before=before, after=after, merge_gap=merge_gap, budget=budget)
    identity = fingerprint(source)
    for name in ("plan.json", "checkpoint.json", "operations.json", ".lock"):
        if source == job / name:
            raise AgentCutError("INVALID_ROUGHCUT", "Job output must not replace the recording")
    with job_lock(job / ".lock"):
        info = inspect_source(source)
        duration = info["duration"]
        audio_stream = int(number(audio_stream, "audio_stream", 0))
        if info["audio_streams"] and audio_stream >= info["audio_streams"]:
            raise AgentCutError("INVALID_ROUGHCUT", "Selected audio stream does not exist")
        external = validate_events(events if events is not None else [], duration)
        warnings = []
        if detector is None and events is None:
            if info["audio_streams"]:
                from .roughcut_audio import AudioActivityDetector
                detector = AudioActivityDetector(audio_stream=audio_stream, threshold_db=audio_threshold)
            else:
                warnings.append("No audio stream; supply external events to select candidates.")
        if detector is not None and not isinstance(detector.cache_key, str):
            raise AgentCutError("INVALID_ROUGHCUT", "Detector cache_key must be a string")
        key = hash_obj({"source": identity, "duration": duration, "chunk": chunk_seconds,
                        "detector": detector.cache_key if detector else None})
        count = math.ceil(duration / chunk_seconds) if detector else 0
        checkpoint = {"schema_version": 1, "key": key, "status": "running", "completed": 0, "total": count}
        atomic_json(job / "checkpoint.json", checkpoint)
        found, reused = [], 0
        try:
            for index in range(count):
                start, end = index * chunk_seconds, min(duration, (index + 1) * chunk_seconds)
                cache = job / "chunks" / key / f"{index:06d}.json"
                chunk_events = None
                try:
                    saved = json.loads(cache.read_text(encoding="utf-8"))
                    if saved.get("start") == start and saved.get("end") == end:
                        chunk_events = validate_events(saved["events"], duration)
                        if any(e["start"] < start or e["end"] > end for e in chunk_events):
                            chunk_events = None
                except (OSError, ValueError, KeyError, AttributeError, AgentCutError):
                    pass
                if chunk_events is not None:
                    reused += 1
                else:
                    with tempfile.TemporaryDirectory(prefix="decode-", dir=job) as scratch:
                        chunk_events = validate_events(detector.analyze(source, start, end, Path(scratch)), duration)
                    if any(e["start"] < start or e["end"] > end for e in chunk_events):
                        raise AgentCutError("INVALID_ROUGHCUT", "Detector events must stay within the requested chunk")
                    atomic_json(cache, {"start": start, "end": end, "events": chunk_events})
                found.extend(chunk_events)
                checkpoint["completed"] = index + 1
                atomic_json(job / "checkpoint.json", checkpoint)
                if progress:
                    progress({"completed": index + 1, "total": count, "reused": reused})
            if fingerprint(source) != identity:
                raise AgentCutError("SOURCE_CHANGED", "Recording changed during analysis; run again")
            found.extend(external)
            clips = select_clips(found, duration, before=before, after=after, merge_gap=merge_gap, budget=budget)
            if not clips:
                warnings.append("No candidate fits the current signals and duration budget; no footage was selected.")
            plan = {"schema_version": 1, "kind": "agentcut.roughcut", "status": "needs_review",
                    "preset": "battlefield-highlights-context", "source": identity,
                    "source_duration": duration, "audio_stream": audio_stream,
                    "has_audio": bool(info["audio_streams"]), "analysis_key": key,
                    "selection": {"before": before, "after": after, "merge_gap": merge_gap, "budget": budget},
                    "clips": clips, "selected_duration": sum(c["end"] - c["start"] for c in clips),
                    "event_count": len(found), "warnings": warnings,
                    "limitations": ["Audio activity is a candidate signal, not recognition of kills or combat quality.",
                                    "Source identity uses path/stat and sampled bytes, not a full-file checksum."],
                    "chunks": {"total": count, "reused": reused}}
            atomic_json(job / "plan.json", plan)
            checkpoint["status"] = "complete"
            atomic_json(job / "checkpoint.json", checkpoint)
            return plan
        except BaseException:
            checkpoint["status"] = "interrupted"
            atomic_json(job / "checkpoint.json", checkpoint)
            raise


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(plan, dict) or plan.get("kind") != "agentcut.roughcut" or plan.get("schema_version") != 1:
        raise AgentCutError("INVALID_ROUGHCUT", "Unsupported rough-cut plan")
    identity = plan.get("source")
    if not isinstance(identity, dict) or not isinstance(identity.get("path"), str):
        raise AgentCutError("INVALID_ROUGHCUT", "Plan is missing the recording identity")
    source = Path(identity["path"])
    if fingerprint(source) != identity:
        raise AgentCutError("SOURCE_CHANGED", "Recording differs from the analyzed source; analyze again")
    duration = number(plan.get("source_duration"), "source_duration", 0.001)
    clips = plan.get("clips")
    clean = validate_events(clips, duration)
    previous = 0.0
    if not clean:
        raise AgentCutError("EMPTY_ROUGHCUT", "No clips selected; adjust signals or budget first")
    for clip, normalized in zip(clips, clean):
        if clip["start"] != normalized["start"] or clip["end"] != normalized["end"] or clip["start"] < previous:
            raise AgentCutError("INVALID_ROUGHCUT", "Clips must be ordered and must not overlap")
        previous = clip["end"]
    number(plan.get("audio_stream"), "audio_stream", 0)
    return plan


def export_recording(plan_path, output, *, progress=None):
    """Render only selected spans with original selected audio; no full-length proxy."""
    plan = load_plan(plan_path)
    source = plan["source"]["path"]
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != ".mp4":
        raise AgentCutError("INVALID_ROUGHCUT", "Rough-cut preview output must be .mp4")
    if output.exists():
        raise AgentCutError("OUTPUT_EXISTS", "Choose a new output path", path=str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ensure_binary("ffmpeg")
    with job_lock(output.with_suffix(".mp4.lock")), tempfile.TemporaryDirectory(prefix="roughcut-", dir=output.parent) as folder:
        if output.exists():
            raise AgentCutError("OUTPUT_EXISTS", "Choose a new output path", path=str(output))
        scratch, rows = Path(folder), []
        for index, clip in enumerate(plan["clips"]):
            segment = scratch / f"clip_{index:06d}.mp4"
            length = clip["end"] - clip["start"]
            command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-threads", "2",
                       "-ss", str(clip["start"]), "-i", source, "-t", str(length), "-map", "0:v:0"]
            if plan.get("has_audio"):
                command += ["-map", f"0:a:{int(plan['audio_stream'])}", "-af", "aresample=async=1:first_pts=0,apad",
                            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
            else:
                command += ["-an"]
            command += ["-vf", "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
                        "-r", "30", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "23",
                        "-pix_fmt", "yuv420p", "-map_metadata", "-1", "-map_chapters", "-1", str(segment)]
            media_run(command, timeout=max(120, length * 20))
            rows.append(f"file '{segment.name}'\n")
            if progress:
                progress({"exported": index + 1, "total": len(plan["clips"])})
        listing = scratch / "clips.txt"
        listing.write_text("".join(rows), encoding="utf-8")
        final = scratch / "roughcut.mp4"
        media_run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "concat", "-safe", "1",
                   "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(final)], timeout=600)
        if fingerprint(Path(source)) != plan["source"]:
            raise AgentCutError("SOURCE_CHANGED", "Recording changed during export")
        if output.exists():
            raise AgentCutError("OUTPUT_EXISTS", "Output appeared while exporting", path=str(output))
        os.replace(final, output)
    return {"output": str(output), "clips": len(plan["clips"]),
            "expected_duration": sum(c["end"] - c["start"] for c in plan["clips"]),
            "profile": "720p30-preview", "audio_preserved": bool(plan.get("has_audio"))}


def editor_operations(plan_path, asset_id="roughcut_source"):
    """Visual conform for an already registered asset; apply stays transactional."""
    plan = load_plan(plan_path)
    operations = []
    for index, clip in enumerate(plan["clips"]):
        operations.append({"action": "add_scene", "args": {"asset_id": asset_id,
                           "scene_id": f"{asset_id}_{index + 1:04d}", "source_in": clip["start"],
                           "duration": clip["end"] - clip["start"]}})
    return operations
