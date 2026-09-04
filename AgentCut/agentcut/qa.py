from __future__ import annotations

import re
from pathlib import Path

from .probe import probe
from .timeline import build_timeline
from .util import ensure_binary, file_sha256, run
from .performance import text_read_units


def _issue(level: str, code: str, message: str, **context):
    return {"level": level, "code": code, "message": message, "context": context}


def expected_timeline(project: dict) -> tuple[list[float], float]:
    timeline = build_timeline(project)
    return [float(s["start"]) for s in timeline["scenes"]], float(timeline["duration"])


def _asset_path(root: Path, asset: dict) -> Path:
    p = Path(asset["path"])
    return p if p.is_absolute() else root / p


def _source_dimensions(asset: dict, path: Path) -> tuple[int | None, int | None]:
    meta = asset.get("metadata") or {}
    if asset.get("type") == "image":
        w, h = meta.get("width"), meta.get("height")
        if w and h:
            return int(w), int(h)
        try:
            from PIL import Image
            with Image.open(path) as im:
                return int(im.width), int(im.height)
        except Exception:
            return None, None
    if asset.get("type") == "video":
        for stream in meta.get("streams", []):
            if stream.get("codec_type") == "video":
                return int(stream.get("width", 0) or 0), int(stream.get("height", 0) or 0)
    return None, None


def _source_duration(asset: dict) -> float | None:
    try:
        return float((asset.get("metadata") or {}).get("format", {}).get("duration"))
    except (TypeError, ValueError):
        return None


def run_qa(root: Path, project: dict, rendered: Path | None = None) -> dict:
    issues = []
    assets = project.get("assets", {})
    canvas_w = int(project.get("video", {}).get("width", 0))
    canvas_h = int(project.get("video", {}).get("height", 0))
    if canvas_w % 2 or canvas_h % 2:
        issues.append(_issue("warning", "ODD_CANVAS_NORMALIZED", "H.264 yuv420p output will round odd canvas dimensions down to even values", width=canvas_w, height=canvas_h))

    for aid, asset in assets.items():
        p = _asset_path(root, asset)
        if not p.exists():
            issues.append(_issue("error", "MISSING_ASSET", "Asset file is missing", asset_id=aid, path=str(p)))
            continue
        stored_hash = asset.get("sha256")
        if stored_hash:
            try:
                current_hash = file_sha256(p)
                if current_hash != stored_hash:
                    issues.append(_issue("warning", "ASSET_CONTENT_CHANGED", "Asset bytes changed after import; stored hash/metadata may be stale", asset_id=aid, stored_sha256=stored_hash, current_sha256=current_hash))
            except OSError:
                pass

        if asset.get("type") in {"image", "video"}:
            w, h = _source_dimensions(asset, p)
            if w and h and (w < canvas_w or h < canvas_h):
                issues.append(_issue("warning", "SOURCE_BELOW_CANVAS", "Visual source is smaller than the project canvas and may be upscaled", asset_id=aid, source_width=w, source_height=h, canvas_width=canvas_w, canvas_height=canvas_h))

    scenes = project.get("scenes", [])
    timeline_rows = {x.get("scene_id"): x for x in build_timeline(project).get("scenes", [])}
    if not scenes:
        issues.append(_issue("error", "EMPTY_PROJECT", "Project contains no scenes"))
    for i, scene in enumerate(scenes):
        sid = scene.get("id")
        dur = float(scene.get("duration", 0))
        if dur <= 0:
            issues.append(_issue("error", "INVALID_DURATION", "Scene duration must be positive", scene=sid, duration=dur))
        camera = scene.get("camera", {})
        amount = float(camera.get("amount", 0))
        if amount > 0.08:
            issues.append(_issue("warning", "AGGRESSIVE_CAMERA", "Camera motion may feel excessive for a static-image edit", scene=sid, amount=amount, recommended_max=0.08))
        shot_path = camera.get("shot_path") or []
        if shot_path:
            cuts = sum(1 for x in shot_path if x.get("cut"))
            if cuts >= 7 and dur < 4.5:
                issues.append(_issue("warning", "DENSE_SHOT_COVERAGE", "Many discrete reframes are packed into a short scene", scene=sid, cuts=cuts, duration=dur))
            if any(float(x.get("zoom", 1.0)) > 1.28 for x in shot_path):
                issues.append(_issue("info", "TIGHT_COVERAGE", "Dialogue coverage contains a very tight crop; verify facial/headroom framing", scene=sid, max_zoom=max(float(x.get("zoom",1.0)) for x in shot_path)))
        comp = scene.get("composition") or {}
        if comp.get("focus_path") and amount > 0.025:
            issues.append(_issue("warning", "STACKED_REFRAME_CAMERA", "Automatic subject tracking and camera motion are both active; the combined movement may feel busy", scene=sid, camera_amount=amount, tracking_points=len(comp.get("focus_path") or [])))
        if comp.get("focus_path") and len(comp.get("focus_path") or []) >= 9 and dur < 3.0:
            issues.append(_issue("warning", "DENSE_FOCUS_PATH", "Many speaker/performance focus changes are packed into a short scene", scene=sid, points=len(comp.get("focus_path") or []), duration=dur))
        cinematic = scene.get("cinematic") or {}
        if cinematic.get("frame_path") and amount > 0.04:
            issues.append(_issue("info", "STACKED_FRAME_CAMERA", "Dynamic aspect-ratio change and strong camera motion are both active; reserve this combination for deliberate impact", scene=sid, camera_amount=amount, treatment=cinematic.get("treatment")))
        if cinematic.get("fragment_group"):
            min_frames = dur * max(1, int(project.get("video", {}).get("fps", 30)))
            if min_frames < 2.5:
                issues.append(_issue("warning", "MICRO_FRAGMENT_TOO_SHORT", "Cinematic fragment is shorter than about 2.5 frames and may read as a compression glitch rather than an intentional cut", scene=sid, duration=dur, frames=round(min_frames, 2), group=cinematic.get("fragment_group")))
        if i < len(scenes) - 1:
            tr = scene.get("transition_out", {})
            td = float(tr.get("duration", 0))
            if tr.get("type", "cut") != "cut" and td >= min(dur, float(scenes[i+1].get("duration", 0))):
                issues.append(_issue("error", "TRANSITION_OVERLAP", "Transition is as long as or longer than an adjacent scene", scene=sid, duration=td))
            elif td > 1.5:
                issues.append(_issue("warning", "LONG_TRANSITION", "Transition may feel overly slow", scene=sid, duration=td))
        elif scene.get("transition_out", {}).get("type", "cut") != "cut":
            issues.append(_issue("warning", "TRAILING_TRANSITION_IGNORED", "The final scene has no following scene, so its transition_out is ignored", scene=sid))
        if i == len(scenes) - 1 and (scene.get("transition_out") or {}).get("sfx"):
            issues.append(_issue("warning", "TRAILING_TRANSITION_SFX_IGNORED", "The final scene has no outgoing boundary, so bound transition SFX is ignored", scene=sid))

        tr = timeline_rows.get(sid) or {}
        ss, se = float(tr.get("start", 0.0)), float(tr.get("end", 0.0))
        overlap_caps = [c for c in project.get("captions", []) if float(c.get("end",0)) > ss + 1e-6 and float(c.get("start",0)) < se - 1e-6 and (c.get("speaker") or c.get("character_id"))]
        # Native dialogue segments are local to the scene and count as speaker material too.
        overlap_dialogue = [d for d in project.get("dialogue_segments", []) if d.get("scene_id") == sid and (d.get("speaker") or d.get("character_id"))]
        speaker_material = len(overlap_caps) + len(overlap_dialogue)
        if dur >= 5.0 and speaker_material >= 2 and not shot_path and len(comp.get("focus_path") or []) <= 3:
            issues.append(_issue("warning", "LONG_SINGLE_COVERAGE", "Long dialogue scene uses one continuous reframe; consider dialogue coverage or additional reaction/insert shots", scene=sid, duration=dur, speaker_captions=speaker_material))
        # Dialogue coverage can still leave a long action-only opening untouched. Surface it so
        # an Agent can add an object/action insert instead of mistaking technical validity for pacing.
        if shot_path and overlap_caps:
            first_start = min(float(c.get("start", ss)) for c in overlap_caps)
            lead = max(0.0, first_start - ss)
            first_cut_t = min((float(x.get("t", 0)) for x in shot_path if x.get("cut")), default=1.0) * max(dur, 1e-6)
            if lead >= 2.4 and first_cut_t >= min(lead - .15, 2.2):
                issues.append(_issue("info", "LONG_PRE_DIALOGUE_HOLD", "A long action-only lead remains before the first dialogue shot; consider an object/action insert or dedicated visual beat", scene=sid, lead_duration=round(lead,3)))

        for fx in scene.get("effects", []):
            if float(fx.get("intensity", 0)) > 0.7:
                issues.append(_issue("warning", "HEAVY_EFFECT", "Environment effect may obscure the subject", scene=sid, effect=fx.get("type"), intensity=fx.get("intensity")))
            if fx.get("depth", "foreground") != "foreground":
                issues.append(_issue("info", "DEPTH_HINT_APPROXIMATE", "Depth currently changes particle scale/speed/density but is not subject-aware occlusion", scene=sid, effect=fx.get("type"), depth=fx.get("depth")))

        asset = assets.get(scene.get("asset_id"), {})
        if asset.get("type") == "video":
            source_duration = _source_duration(asset)
            if source_duration is not None:
                source_in = float(scene.get("source_in", 0.0))
                rate = float(scene.get("playback_rate", 1.0))
                required_source = dur * rate
                if source_in >= source_duration:
                    issues.append(_issue("error", "SOURCE_IN_OUTSIDE_MEDIA", "Video source_in is beyond source duration", scene=sid, source_in=source_in, source_duration=source_duration))
                elif source_in + required_source > source_duration + 0.05:
                    issues.append(_issue("warning", "SOURCE_TOO_SHORT", "Video scene requests more source media than is available; render may end early", scene=sid, source_in=source_in, playback_rate=rate, required_source_duration=required_source, source_duration=source_duration))

    fragment_groups = {}
    for scene in scenes:
        cine = scene.get("cinematic") or {}
        group = cine.get("fragment_group")
        if group:
            fragment_groups.setdefault(group, []).append(scene)
    for group, members in fragment_groups.items():
        if len(members) >= 7:
            issues.append(_issue("info", "DENSE_FRAGMENT_CLUSTER", "Fragment cluster is very dense; use this as an accent rather than a default cutting pattern", group=group, fragments=len(members)))

    # Project Facts are a single source of truth for version/test/user counters.
    # Unresolved placeholders are a hard QA error so stale literal data cannot sneak through.
    facts=project.get("facts",{})
    unresolved_re=re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
    for owner, text in [(f"caption:{c.get('id')}", str(c.get('text',''))) for c in project.get('captions',[])]:
        missing=[m.group(1).strip() for m in unresolved_re.finditer(text) if m.group(1).strip() not in facts]
        if missing: issues.append(_issue("error","UNRESOLVED_FACT","Text contains unresolved project fact",owner=owner,missing=missing))
    for seg in project.get('dialogue_segments',[]):
        text=str(seg.get('text','')); missing=[m.group(1).strip() for m in unresolved_re.finditer(text) if m.group(1).strip() not in facts]
        if missing: issues.append(_issue("error","UNRESOLVED_FACT","Dialogue contains unresolved project fact",owner=f"dialogue:{seg.get('id')}",missing=missing))
    for scene in scenes:
        for layer in scene.get('layers',[]) or []:
            if layer.get('type')=='text':
                text=str(layer.get('text','')); missing=[m.group(1).strip() for m in unresolved_re.finditer(text) if m.group(1).strip() not in facts]
                if missing: issues.append(_issue("error","UNRESOLVED_FACT","Layer text contains unresolved project fact",owner=f"layer:{scene.get('id')}:{layer.get('id')}",missing=missing))

    timeline = build_timeline(project)
    expected = float(timeline["duration"])
    cast = project.get("cast", {}) or {}
    cast_names = {}
    for cast_cid, row in cast.items():
        for name in [cast_cid, row.get("display_name"), *(row.get("aliases") or [])]:
            if name:
                cast_names[str(name).strip().casefold()] = cast_cid
    timeline_windows = [(x.get("scene_id"), float(x.get("start",0)), float(x.get("end",0))) for x in timeline.get("scenes", [])]
    for cap in project.get("captions", []):
        text = str(cap.get("text", ""))
        secondary = str(cap.get("secondary_text") or "")
        if not cap.get("speaker"):
            m = re.match(r"^\s*([^：:\n]{1,24})\s*[：:]", text)
            if m and m.group(1).strip().casefold() in cast_names:
                issues.append(_issue("warning", "UNPARSED_CAPTION_SPEAKER", "Caption begins with a known Cast name but speaker metadata is empty", caption=cap.get("id"), speaker=m.group(1).strip(), recovery="Re-import with Cast-aware speaker parsing or set caption speaker metadata."))
        cap_cid = cap.get("character_id")
        if cap_cid:
            t = float(cap.get("start",0))
            cap_sid = next((win_sid for win_sid,a,b in timeline_windows if a-1e-6 <= t < b+1e-6), None)
            if cap_sid:
                cap_scene = next((x for x in scenes if x.get("id")==cap_sid), None) or {}
                cap_staging = cap_scene.get("staging") or {}
                if cap_staging and cap_cid not in cap_staging:
                    issues.append(_issue("info", "SPEAKER_NOT_STAGED", "Caption speaker has Cast metadata but no position in the owning scene staging", caption=cap.get("id"), scene=cap_sid, character_id=cap_cid))
        if len(text) > 34 and "\n" not in text:
            issues.append(_issue("warning", "LONG_CAPTION", "Caption is long and may need a manual line break", caption=cap.get("id"), characters=len(text)))
        if cap.get("subtitle_style") == "bilingual" and not secondary:
            issues.append(_issue("info", "BILINGUAL_SECONDARY_MISSING", "Bilingual subtitle style has no secondary-language line", caption=cap.get("id")))
        if secondary and cap.get("layout_level") == "split_recommended":
            issues.append(_issue("warning", "BILINGUAL_SPLIT_RECOMMENDED", "Auto-fit reached its safe minimum; split or shorten this bilingual cue", caption=cap.get("id"), layout_density=cap.get("layout_density"), recovery="Split the cue at a phrase boundary or shorten the secondary translation; do not shrink text further."))
        elif secondary and len(text) + len(secondary) > 76 and not cap.get("layout_auto_fit"):
            issues.append(_issue("info", "DENSE_BILINGUAL_CAPTION", "Both subtitle lines are long and have not been auto-fitted", caption=cap.get("id"), primary_characters=len(text), secondary_characters=len(secondary), recovery="Run optimize_subtitle_layout or adjust manually."))
        if float(cap.get("end", 0)) > expected + 0.05:
            issues.append(_issue("warning", "CAPTION_OUTSIDE_TIMELINE", "Caption extends past the video", caption=cap.get("id"), end=cap.get("end"), timeline=expected))

    scene_map = {s.get("id"): s for s in scenes}
    dialogue_by_scene = {}
    for seg in project.get("dialogue_segments", []):
        dialogue_by_scene.setdefault(seg.get("scene_id"), []).append(seg)
    for scene_id, rows in dialogue_by_scene.items():
        rows = sorted(rows, key=lambda x: float(x.get("start", 0.0)))
        for a, b in zip(rows[:-1], rows[1:]):
            if a.get("duration") is not None and float(a.get("start", 0.0)) + float(a.get("duration", 0.0)) > float(b.get("start", 0.0)) + 0.03:
                issues.append(_issue("warning", "DIALOGUE_OVERLAP", "Dialogue subtitles overlap inside one scene; this is usually hard to read in dynamic-manga edits", scene=scene_id, first=a.get("id"), second=b.get("id")))
    for seg in project.get("dialogue_segments", []):
        text = str(seg.get("text", ""))
        secondary = str(seg.get("secondary_text") or "")
        if seg.get("subtitle_style") == "bilingual" and not secondary:
            issues.append(_issue("info", "BILINGUAL_SECONDARY_MISSING", "Bilingual dialogue style has no secondary-language line", dialogue=seg.get("id")))
        if secondary and seg.get("layout_level") == "split_recommended":
            issues.append(_issue("warning", "BILINGUAL_SPLIT_RECOMMENDED", "Auto-fit reached its safe minimum for dialogue; split or shorten the cue", dialogue=seg.get("id"), layout_density=seg.get("layout_density")))
        elif secondary and len(text) + len(secondary) > 76 and not seg.get("layout_auto_fit"):
            issues.append(_issue("info", "DENSE_BILINGUAL_CAPTION", "Both dialogue subtitle lines are long and have not been auto-fitted", dialogue=seg.get("id"), primary_characters=len(text), secondary_characters=len(secondary)))
        if len(text) > 34 and "\n" not in text and not seg.get("max_line_chars"):
            issues.append(_issue("warning", "LONG_DIALOGUE_CAPTION", "Dialogue subtitle may be too wide for one line", dialogue=seg.get("id"), characters=len(text)))
        if seg.get("duration") is not None:
            dur_text = max(.01, float(seg.get("duration", 0.0)))
            units_per_second = text_read_units(text) / dur_text
            if units_per_second > 8.8:
                issues.append(_issue("warning", "DIALOGUE_TOO_FAST", "Dialogue reading speed is likely too fast", dialogue=seg.get("id"), read_units_per_second=round(units_per_second, 2), duration=dur_text))
            elif units_per_second < 1.2 and dur_text > 2.5:
                issues.append(_issue("info", "DIALOGUE_LONG_HOLD", "Dialogue remains on screen much longer than its text requires", dialogue=seg.get("id"), read_units_per_second=round(units_per_second, 2), duration=dur_text))
        scene = scene_map.get(seg.get("scene_id"))
        if scene is not None:
            comp = scene.get("composition") or {}
            safe = comp.get("safe_zones") or []
            confidence = float(comp.get("visual_confidence", 0.0) or 0.0)
            if safe and confidence >= 0.25 and seg.get("position", "bottom") not in safe:
                issues.append(_issue("info", "TEXT_SUBJECT_OVERLAP_RISK", "Dialogue position is outside visually quiet zones estimated for this scene", dialogue=seg.get("id"), scene=seg.get("scene_id"), position=seg.get("position"), suggested_zones=safe[:4], visual_confidence=confidence))
        if scene is not None and seg.get("duration") is not None:
            local_end = float(seg.get("start", 0.0)) + float(seg.get("duration", 0.0))
            if local_end > float(scene.get("duration", 0.0)) + 0.05:
                issues.append(_issue("warning", "DIALOGUE_OUTSIDE_SCENE", "Dialogue extends past its owning scene", dialogue=seg.get("id"), scene=seg.get("scene_id"), local_end=local_end, scene_duration=scene.get("duration")))

    render_info = None
    audio_peak_db = None
    if rendered is not None:
        rendered = Path(rendered)
        if not rendered.exists():
            issues.append(_issue("error", "RENDER_MISSING", "Requested render for QA does not exist", path=str(rendered)))
        else:
            render_info = probe(rendered)
            actual = float(render_info.get("format", {}).get("duration", 0) or 0)
            if abs(actual - expected) > max(0.15, 1 / max(1, project["video"]["fps"]) * 3):
                issues.append(_issue("warning", "DURATION_MISMATCH", "Rendered duration differs from project timeline", expected=expected, actual=actual))
            vstreams = [s for s in render_info.get("streams", []) if s.get("codec_type") == "video"]
            if not vstreams:
                issues.append(_issue("error", "NO_VIDEO_STREAM", "Rendered file contains no video stream"))
            else:
                v = vstreams[0]
                if int(v.get("width", 0)) < 640 or int(v.get("height", 0)) < 360:
                    issues.append(_issue("warning", "LOW_RESOLUTION", "Rendered video resolution is unusually low", width=v.get("width"), height=v.get("height")))
            astreams = [s for s in render_info.get("streams", []) if s.get("codec_type") == "audio"]
            if vstreams and astreams:
                try:
                    vd = float(vstreams[0].get("duration"))
                    ad = float(astreams[0].get("duration"))
                    tolerance = max(0.15, 3 / max(1, project["video"]["fps"]))
                    if abs(vd - ad) > tolerance:
                        issues.append(_issue("error", "AV_DURATION_MISMATCH", "Rendered audio and video stream durations differ", video_duration=vd, audio_duration=ad, difference=abs(vd-ad)))
                except (TypeError, ValueError):
                    pass
            if astreams:
                ffmpeg = ensure_binary("ffmpeg")
                cp = run([ffmpeg, "-hide_banner", "-i", str(rendered), "-vn", "-af", "volumedetect", "-f", "null", "-"], capture=True)
                text = (cp.stderr or "") + (cp.stdout or "")
                m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", text)
                if m:
                    audio_peak_db = float(m.group(1))
                    if audio_peak_db > -0.1:
                        issues.append(_issue("warning", "AUDIO_NEAR_CLIPPING", "Audio peak is extremely close to digital full scale", max_volume_db=audio_peak_db))

    status = "fail" if any(i["level"] == "error" for i in issues) else ("warning" if any(i["level"] == "warning" for i in issues) else "pass")
    return {
        "status": status,
        "expected_duration": expected,
        "issues": issues,
        "render_info": render_info,
        "audio_peak_db": audio_peak_db,
        "motion_backend": "subpixel_perspective_cubic",
    }
