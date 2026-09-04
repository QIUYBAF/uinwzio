from __future__ import annotations

import os
import shutil
from copy import deepcopy
from pathlib import Path

from .errors import AgentCutError
from .manifest import write_render_manifest
from .libraries import transition_backend, filter_backend
from .graphics import generate_graphics_video, graphics_cache_path, generate_shared_morph_video, shared_morph_cache_path
from .particles import generate_particle_video, particle_cache_path
from .timeline import build_timeline, effective_transition_duration, require_nonempty_timeline
from .util import ensure_binary, hash_obj, run


PROFILES = {
    "proxy": {"width": 640, "height": 360, "fps": 12, "crf": 32, "preset": "ultrafast", "audio_bitrate": "96k", "camera_supersample": 1},
    "preview": {"width": 1280, "height": 720, "fps": 24, "crf": 28, "preset": "veryfast", "audio_bitrate": "160k", "camera_supersample": 2},
    "showcase": {"width": 1920, "height": 1080, "fps": 30, "crf": 23, "preset": "ultrafast", "audio_bitrate": "192k", "camera_supersample": 2},
    "final": {"width": 1920, "height": 1080, "fps": 30, "crf": 18, "preset": "medium", "audio_bitrate": "256k", "camera_supersample": 2},
    "uhd_4k30": {"width": 3840, "height": 2160, "fps": 30, "crf": 18, "preset": "fast", "audio_bitrate": "320k", "camera_supersample": 1},
    "uhd_4k60": {"width": 3840, "height": 2160, "fps": 60, "crf": 18, "preset": "fast", "audio_bitrate": "320k", "camera_supersample": 1},
}

def list_render_profiles() -> dict:
    return {name: dict(spec) for name, spec in PROFILES.items()}

XFADES = {
    "fade": "fade",
    "crossfade": "fade",
    "fade_black": "fadeblack",
    "fade_white": "fadewhite",
    "smooth_left": "smoothleft",
    "smooth_right": "smoothright",
    "smooth_up": "smoothup",
    "smooth_down": "smoothdown",
    "zoom_in": "zoomin",
    "cover_left": "coverleft",
    "cover_right": "coverright",
}


class Renderer:
    def __init__(self, root: Path, project: dict):
        self.root = Path(root)
        self.project = project
        self.ffmpeg = ensure_binary("ffmpeg")

    def _resolve_text(self, text: str) -> str:
        import re
        facts=self.project.get("facts",{})
        def repl(m):
            key=m.group(1).strip(); return str(facts[key]) if key in facts else m.group(0)
        return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", repl, str(text))

    def _asset_path(self, asset_id: str) -> Path:
        asset = self.project["assets"].get(asset_id)
        if not asset:
            raise AgentCutError("INVALID_ASSET", "Unknown asset", asset_id=asset_id)
        p = Path(asset["path"])
        return p if p.is_absolute() else self.root / p

    def _profile(self, profile: str, override: dict | None = None) -> dict:
        if profile not in PROFILES:
            raise AgentCutError("INVALID_PROFILE", "Unknown render profile", profile=profile, allowed=sorted(PROFILES))
        p = dict(PROFILES[profile])
        if override:
            p.update({k: v for k, v in override.items() if v is not None})
        project_video = self.project["video"]
        allow_canvas_upscale = bool(p.pop("allow_canvas_upscale", False))
        if not allow_canvas_upscale:
            # Legacy profiles never upscale beyond the canonical project canvas.
            p["width"] = min(int(project_video["width"]), int(p["width"]))
            p["height"] = min(int(project_video["height"]), int(p["height"]))
            p["fps"] = min(float(project_video["fps"]), float(p["fps"]))
        else:
            p["width"] = int(p["width"]); p["height"] = int(p["height"]); p["fps"] = float(p["fps"])
        # h264/yuv420p requires even dimensions.
        p["width"] -= p["width"] % 2
        p["height"] -= p["height"] % 2
        if p["width"] < 2 or p["height"] < 2:
            raise AgentCutError("INVALID_PROFILE", "Render dimensions became invalid after yuv420p normalization", profile=profile, width=p["width"], height=p["height"])
        return p

    def _progress_expr(self, frames: int, easing: str) -> str:
        denom = max(1, frames - 1)
        base = f"on/{denom}"
        if easing in {"ease", "ease_in_out", "smooth"}:
            return f"(0.5-0.5*cos(PI*{base}))"
        if easing == "ease_in":
            return f"({base})*({base})"
        if easing == "ease_out":
            return f"1-(1-({base}))*(1-({base}))"
        return base

    @staticmethod
    def _anchor_factor(anchor: str, *, axis: str) -> float:
        """Return the crop-window anchor as a normalized 0..1 factor."""
        if axis == "x":
            if anchor in {"top_left", "left", "bottom_left"}:
                return 0.0
            if anchor in {"top_right", "right", "bottom_right"}:
                return 1.0
            return 0.5
        if anchor in {"top_left", "top", "top_right"}:
            return 0.0
        if anchor in {"bottom_left", "bottom", "bottom_right"}:
            return 1.0
        return 0.5

    @staticmethod
    def _offset_expr(axis_size: str, zoom_expr: str, factor: float) -> str:
        headroom = f"({axis_size}-{axis_size}/({zoom_expr}))"
        if factor <= 0:
            return "0"
        if factor >= 1:
            return headroom
        return f"({headroom})*{factor:.8f}"

    @staticmethod
    def _shot_value_expr(points: list[dict], key: str, frames: int, default: float) -> str:
        """Compile normalized camera shot keyframes into a per-frame expression.

        ``cut`` on the destination keyframe creates a true one-frame reframe jump.
        Otherwise values interpolate smoothly between keyframes. Expressions use FFmpeg's
        ``on`` frame counter, which is available to the perspective filter under eval=frame.
        """
        parsed = []
        lo, hi = ((1.0, 1.6) if key == "zoom" else (0.0, 1.0))
        for row in points or []:
            try:
                t = max(0.0, min(1.0, float(row.get("t", 0.0))))
                value = max(lo, min(hi, float(row.get(key, default))))
                parsed.append((int(round(t * max(1, frames - 1))), value, bool(row.get("cut", False))))
            except (TypeError, ValueError):
                continue
        if not parsed:
            return f"{default:.6f}"
        parsed.sort(key=lambda x: x[0])
        # Same-frame keys are legal; the later key wins so a semantic cut remains deterministic.
        dedup = []
        for item in parsed:
            if dedup and dedup[-1][0] == item[0]:
                dedup[-1] = item
            else:
                dedup.append(item)
        parsed = dedup
        if parsed[0][0] > 0:
            parsed.insert(0, (0, parsed[0][1], False))
        expr = f"{parsed[-1][1]:.6f}"
        for (f0, v0, _), (f1, v1, cut1) in reversed(list(zip(parsed[:-1], parsed[1:]))):
            if cut1 or f1 <= f0:
                value_expr = f"{v0:.6f}"
            else:
                span = max(1, f1 - f0)
                u = f"max(0,min(1,(on-{f0})/{span}))"
                # cosine ease avoids a robotic linear drift inside a held shot.
                smooth = f"(0.5-0.5*cos(PI*({u})))"
                value_expr = f"({v0:.6f}+({v1-v0:.6f})*({smooth}))"
            expr = f"if(lt(on,{f1}),{value_expr},{expr})"
        return expr

    def _motion_perspective_filter(self, scene: dict, p: dict) -> str:
        """Build a sub-pixel camera transform using per-frame perspective resampling.

        FFmpeg zoompan quantizes its crop origin enough to create periodic one-pixel jumps
        during slow motion.  perspective evaluates floating-point source coordinates for
        every frame and resamples cubically, so slow pans/zooms remain continuous instead
        of alternating between 'hold' and 'jump' frames.
        """
        w, h, fps = p["width"], p["height"], p["fps"]
        frames = max(1, int(round(float(scene["duration"]) * fps)))
        cam = scene.get("camera") or {"type": "static", "amount": 0}
        motion = cam.get("type", "static")
        amount = float(cam.get("amount", 0.0))
        easing = cam.get("easing", "linear")
        anchor = cam.get("anchor", "center")
        shot_path = cam.get("shot_path") or []

        if len(shot_path) >= 2:
            z = self._shot_value_expr(shot_path, "zoom", frames, 1.0)
            xf = self._shot_value_expr(shot_path, "x", frames, 0.5)
            yf = self._shot_value_expr(shot_path, "y", frames, 0.5)
            hx = f"(W-W/({z}))"
            hy = f"(H-H/({z}))"
            left = f"({hx})*({xf})"
            top = f"({hy})*({yf})"
            cw = f"W/({z})"; ch = f"H/({z})"
            right = f"({left})+({cw})"; bottom = f"({top})+({ch})"
            return (
                "perspective="
                f"x0='{left}':y0='{top}':"
                f"x1='{right}':y1='{top}':"
                f"x2='{left}':y2='{bottom}':"
                f"x3='{right}':y3='{bottom}':"
                "sense=source:eval=frame:interpolation=cubic"
            )

        prog = self._progress_expr(frames, easing)
        ax = self._anchor_factor(anchor, axis="x")
        ay = self._anchor_factor(anchor, axis="y")

        if motion == "slow_push":
            z = f"1+{amount:.8f}*({prog})"
            left = self._offset_expr("W", z, ax)
            top = self._offset_expr("H", z, ay)
        elif motion == "slow_pull":
            z = f"1+{amount:.8f}*(1-({prog}))"
            left = self._offset_expr("W", z, ax)
            top = self._offset_expr("H", z, ay)
        elif motion in {"pan_left", "pan_right", "pan_up", "pan_down"}:
            # Fixed zoom creates crop headroom. The crop window then translates with a
            # continuous floating-point trajectory rather than integer crop steps.
            z = f"{1 + max(amount, 0.03):.8f}"
            hx = f"(W-W/({z}))"
            hy = f"(H-H/({z}))"
            if motion == "pan_left":
                left = f"({hx})*(1-({prog}))"
                top = self._offset_expr("H", z, ay)
            elif motion == "pan_right":
                left = f"({hx})*({prog})"
                top = self._offset_expr("H", z, ay)
            elif motion == "pan_up":
                left = self._offset_expr("W", z, ax)
                top = f"({hy})*(1-({prog}))"
            else:  # pan_down
                left = self._offset_expr("W", z, ax)
                top = f"({hy})*({prog})"
        else:
            raise AgentCutError("UNSUPPORTED_CAMERA", "Renderer does not implement camera motion", motion=motion)

        cw = f"W/({z})"
        ch = f"H/({z})"
        right = f"({left})+({cw})"
        bottom = f"({top})+({ch})"
        return (
            "perspective="
            f"x0='{left}':y0='{top}':"
            f"x1='{right}':y1='{top}':"
            f"x2='{left}':y2='{bottom}':"
            f"x3='{right}':y3='{bottom}':"
            "sense=source:eval=frame:interpolation=cubic"
        )

    def _scene_filter_chain(self, scene: dict) -> list[str]:
        chain: list[str] = []
        for filter_id in scene.get("filters", []) or []:
            backend = filter_backend(filter_id)
            if backend and backend != "null":
                chain.extend([part.strip() for part in backend.split(",") if part.strip()])
        return chain

    @staticmethod
    def _focus_expr(comp: dict, axis: str, duration: float) -> str:
        key = "focus_x" if axis == "x" else "focus_y"
        coord = "x" if axis == "x" else "y"
        default = max(0.0, min(1.0, float(comp.get(key, 0.5))))
        path = comp.get("focus_path") or []
        if len(path) < 2 or duration <= 1e-6:
            return f"{default:.6f}"
        pts = []
        for row in path:
            try:
                tn = max(0.0, min(1.0, float(row.get("t", 0.0))))
                value = max(0.0, min(1.0, float(row.get(coord, default))))
                pts.append((tn * duration, value))
            except (TypeError, ValueError):
                continue
        if len(pts) < 2:
            return f"{default:.6f}"
        pts.sort(key=lambda z: z[0])
        if pts[0][0] > 1e-6:
            pts.insert(0, (0.0, pts[0][1]))
        if pts[-1][0] < duration - 1e-6:
            pts.append((duration, pts[-1][1]))
        expr = f"{pts[-1][1]:.6f}"
        for (t0, v0), (t1, v1) in reversed(list(zip(pts[:-1], pts[1:]))):
            dt = max(1e-6, t1 - t0)
            interp = f"({v0:.6f}+({v1-v0:.6f})*max(0,min(1,(t-{t0:.6f})/{dt:.6f})))"
            expr = f"if(lt(t,{t1:.6f}),{interp},{expr})"
        return expr

    def _composition_base_filter(self, scene: dict, p: dict) -> str:
        w, h = p["width"], p["height"]
        comp = scene.get("composition") or {"mode": "cover", "background": "black", "frame_scale": 1.0}
        mode = str(comp.get("mode", "cover"))
        scale = max(0.35, min(1.0, float(comp.get("frame_scale", 1.0))))
        if mode == "cover":
            fx = self._focus_expr(comp, "x", float(scene.get("duration", 0.0)))
            fy = self._focus_expr(comp, "y", float(scene.get("duration", 0.0)))
            crop_zoom = max(1.0, min(3.0, float(comp.get("crop_zoom", 1.0))))
            zw = max(w, int(round(w * crop_zoom))); zh = max(h, int(round(h * crop_zoom)))
            zw -= zw % 2; zh -= zh % 2
            # Focus-aware crop is the crucial bridge between composition planning and actual
            # rendering. crop_zoom is an immediate optical reframe used by micro-cut clusters;
            # unlike camera motion it does not restart a push on every short fragment.
            cx = f"max(0,min(iw-ow,({fx})*iw-ow/2))"
            cy = f"max(0,min(ih-oh,({fy})*ih-oh/2))"
            return (
                f"scale={zw}:{zh}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={w}:{h}:x='{cx}':y='{cy}'"
            )
        if mode == "contain":
            return f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"

        fw=max(2, int(round(w*scale))); fh=max(2, int(round(h*scale)))
        fw -= fw % 2; fh -= fh % 2
        if mode == "native_window":
            return (
                f"scale={fw}:{fh}:force_original_aspect_ratio=decrease:flags=lanczos,"
                f"pad=iw+8:ih+8:4:4:color=black,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
        if mode == "ambient":
            bg = str(comp.get("background", "dim_blur"))
            bg_fx = "boxblur=18:2"
            if bg == "dim_blur":
                bg_fx += ",eq=brightness=-0.14:saturation=0.72"
            elif bg == "blur":
                bg_fx += ",eq=saturation=0.82"
            else:
                bg_fx = "eq=brightness=-1.0"
            return (
                f"split=2[bg][fg];"
                f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase:flags=bilinear,crop={w}:{h},{bg_fx}[bg2];"
                f"[fg]scale={fw}:{fh}:force_original_aspect_ratio=decrease:flags=lanczos,pad=iw+6:ih+6:3:3:color=black[fg2];"
                f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2"
            )
        raise AgentCutError("INVALID_COMPOSITION", "Renderer does not implement composition mode", mode=mode)

    def _video_filter(self, scene: dict, p: dict, *, kind: str) -> str:
        w, h, fps = p["width"], p["height"], p["fps"]
        cam = scene.get("camera") or {"type": "static", "amount": 0}
        motion = cam.get("type", "static")
        amount = float(cam.get("amount", 0.0))
        playback_rate = float(scene.get("playback_rate", 1.0))

        prefix: list[str] = []
        if kind == "video":
            prefix += [f"setpts=(PTS-STARTPTS)/{playback_rate:.8f}", f"fps={fps}"]

        composition = self._composition_base_filter(scene, p)
        # composition may be a one-input graph containing split/overlay, so keep it as one
        # graph fragment instead of naively splitting on commas.
        filters = prefix + [composition]

        if (cam.get("shot_path") and len(cam.get("shot_path") or []) >= 2) or (motion != "static" and amount > 0):
            # Alpha 10 adaptive camera backend: 2x supersampling is useful at 1080p final,
            # but it turns a 4K60 scene into an 8K60 perspective job. UHD profiles render
            # the same cubic floating-point transform at native resolution instead.
            ss = max(1, int(p.get("camera_supersample", 1)))
            if ss > 1:
                filters += [
                    f"scale={w*ss}:{h*ss}:flags=lanczos",
                    self._motion_perspective_filter(scene, {**p, "width": w*ss, "height": h*ss}),
                    f"scale={w}:{h}:flags=lanczos",
                ]
            else:
                filters += [self._motion_perspective_filter(scene, p)]
        filters += [f"fps={fps}"]
        filters += self._scene_filter_chain(scene)
        filters += ["format=yuv420p"]
        return ",".join(filters)

    def _source_fingerprint(self, asset_id: str) -> dict:
        src = self._asset_path(asset_id)
        try:
            st = src.stat()
            return {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
        except FileNotFoundError:
            return {"missing": True}

    @staticmethod
    def _cache_ready(path: Path) -> bool:
        """Return True only for a non-empty cache artifact; remove failed zero-byte outputs."""
        if not path.exists():
            return False
        try:
            if path.stat().st_size > 0:
                return True
        except OSError:
            return False
        try:
            path.unlink()
        except OSError:
            pass
        return False

    def _run_atomic(self, cmd: list[str], target: Path) -> None:
        """Run an ffmpeg command into a temporary sibling and atomically publish on success.

        A killed render must never leave a non-zero truncated file at the canonical cache/output
        path. This makes interrupted long renders safe to resume.
        """
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f".{target.stem}.partial{target.suffix}")
        try:
            partial.unlink(missing_ok=True)
        except TypeError:
            if partial.exists():
                partial.unlink()
        rewritten = list(cmd)
        # All renderer ffmpeg commands publish their output as the final argument.
        rewritten[-1] = str(partial)
        try:
            run(rewritten)
            if not partial.exists() or partial.stat().st_size <= 0:
                raise AgentCutError("EMPTY_RENDER", "Renderer produced an empty temporary file", path=str(partial))
            os.replace(partial, target)
        except Exception:
            try:
                partial.unlink()
            except OSError:
                pass
            raise

    def _scene_cache_key(self, scene: dict, p: dict) -> str:
        asset = self.project["assets"][scene["asset_id"]]
        # Base scene render deliberately excludes transition/effects/audio/captions so
        # edits in those layers do not invalidate expensive camera/source rendering.
        base_semantics = {
            "asset_id": scene["asset_id"],
            "duration": scene["duration"],
            "source_in": scene.get("source_in", 0.0),
            "playback_rate": scene.get("playback_rate", 1.0),
            "camera": scene.get("camera"),
            "composition": scene.get("composition"),
            "filters": scene.get("filters", []),
        }
        return hash_obj({
            "base": base_semantics,
            "profile": p,
            "asset_sha256": asset.get("sha256"),
            "source_stat": self._source_fingerprint(scene["asset_id"]),
        })[:20]

    def _render_scene_base(self, scene: dict, p: dict) -> Path:
        key = self._scene_cache_key(scene, p)
        cache = self.root / "cache" / f"scene_{scene['id']}_{key}.mp4"
        if self._cache_ready(cache):
            return cache
        src = self._asset_path(scene["asset_id"])
        if not src.exists():
            raise AgentCutError("FILE_NOT_FOUND", "Scene asset file is missing", scene=scene["id"], path=str(src))
        kind = self.project["assets"][scene["asset_id"]]["type"]
        vf = self._video_filter(scene, p, kind=kind)
        duration = float(scene["duration"])
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        if kind == "image":
            cmd += ["-loop", "1", "-framerate", str(p["fps"]), "-i", str(src)]
        elif kind == "video":
            source_in = float(scene.get("source_in", 0.0))
            if source_in > 0:
                cmd += ["-ss", f"{source_in:.6f}"]
            cmd += ["-i", str(src)]
        else:
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene asset must be image or video", scene=scene["id"], type=kind)
        cmd += [
            "-t", f"{duration:.6f}", "-an", "-vf", vf,
            "-c:v", "libx264", "-preset", p["preset"], "-crf", str(p["crf"]),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(cache)
        ]
        self._run_atomic(cmd, cache)
        return cache

    def _ordinary_layer_scene(self, scene: dict) -> dict:
        """Return a render-only scene copy with shared layers hidden inside morph overlaps."""
        out = deepcopy(scene)
        scenes = self.project.get("scenes", [])
        idx = next((i for i, row in enumerate(scenes) if row.get("id") == scene.get("id")), None)
        if idx is None:
            return out
        timeline = build_timeline(self.project)
        transitions = {(x["from_scene"], x["to_scene"]): x for x in timeline.get("transitions", [])}
        prev_scene = scenes[idx - 1] if idx > 0 else None
        next_scene = scenes[idx + 1] if idx + 1 < len(scenes) else None
        prev_overlap = 0.0
        next_overlap = 0.0
        prev_shared: set[str] = set()
        next_shared: set[str] = set()
        if prev_scene and (prev_scene.get("transition_out") or {}).get("type") == "shared_morph":
            row = transitions.get((prev_scene["id"], scene["id"])) or {}
            prev_overlap = float(row.get("effective_duration", 0.0))
            prev_ids = {x.get("shared_id") for x in prev_scene.get("layers", []) if x.get("shared_id")}
            cur_ids = {x.get("shared_id") for x in scene.get("layers", []) if x.get("shared_id")}
            prev_shared = prev_ids & cur_ids
        if next_scene and (scene.get("transition_out") or {}).get("type") == "shared_morph":
            row = transitions.get((scene["id"], next_scene["id"])) or {}
            next_overlap = float(row.get("effective_duration", 0.0))
            next_ids = {x.get("shared_id") for x in next_scene.get("layers", []) if x.get("shared_id")}
            cur_ids = {x.get("shared_id") for x in scene.get("layers", []) if x.get("shared_id")}
            next_shared = next_ids & cur_ids

        duration = float(scene.get("duration", 0.0))
        kept = []
        for layer in out.get("layers", []) or []:
            sid = layer.get("shared_id")
            st = float(layer.get("start", 0.0))
            en = st + float(layer.get("duration", max(0.0, duration - st)))
            if sid in prev_shared and prev_overlap > 0:
                st = max(st, prev_overlap)
            if sid in next_shared and next_overlap > 0:
                en = min(en, max(0.0, duration - next_overlap))
            if en - st > 1e-6:
                layer["start"] = st
                layer["duration"] = en - st
                kept.append(layer)
        out["layers"] = kept
        return out

    def _apply_layers(self, scene: dict, base: Path, p: dict) -> Path:
        render_scene = self._ordinary_layer_scene(scene)
        layers=render_scene.get("layers",[]) or []
        if not layers:
            return base
        key=hash_obj({"base":base.name,"layers":layers,"facts":self.project.get("facts",{}),"profile":p,"shared_suppression":"v1"})[:20]
        out=self.root/"cache"/f"layers_{scene['id']}_{key}.mp4"
        if self._cache_ready(out): return out
        gp=graphics_cache_path(self.root/"cache",render_scene,self.project.get("facts",{}),p["width"],p["height"],p["fps"])
        generate_graphics_video(gp,render_scene,self.project,self.root,p["width"],p["height"],p["fps"])
        cmd=[self.ffmpeg,"-hide_banner","-loglevel","error","-y","-i",str(base),"-i",str(gp),"-filter_complex","[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[v]","-map","[v]","-an","-c:v","libx264","-preset",p["preset"],"-crf",str(p["crf"]),"-pix_fmt","yuv420p",str(out)]
        self._run_atomic(cmd,out); return out

    def _apply_effects(self, scene: dict, base: Path, p: dict) -> Path:
        effects = scene.get("effects", [])
        if not effects:
            return base
        key = hash_obj({"base": base.name, "effects": effects, "profile": p, "overlay_backend": "colorkey_alpha_v2"})[:20]
        out = self.root / "cache" / f"fx_{scene['id']}_{key}.mp4"
        if self._cache_ready(out):
            return out
        overlays = []
        for effect in effects:
            pp = particle_cache_path(self.root / "cache", effect, p["width"], p["height"], p["fps"], float(scene["duration"]))
            overlays.append(generate_particle_video(pp, effect, p["width"], p["height"], p["fps"], float(scene["duration"])))
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(base)]
        for overlay in overlays:
            cmd += ["-i", str(overlay)]
        filters = ["[0:v]format=rgba[base0]"]
        current = "[base0]"
        for i, effect in enumerate(effects, start=1):
            scaled = f"[ovs{i}]"; keyed=f"[ovk{i}]"; out_label=f"[fx{i}]"
            opacity=float(effect.get("opacity",0.6))
            # Proxy particle assets are scaled only at composition time. Black is converted
            # to alpha using RGB colorkey, much faster than full-resolution screen blending.
            filters.append(f"[{i}:v]scale={p['width']}:{p['height']}:flags=bilinear,format=rgba{scaled}")
            filters.append(f"{scaled}colorkey=0x000000:0.08:0.12,colorchannelmixer=aa={opacity:.4f}{keyed}")
            filters.append(f"{current}{keyed}overlay=0:0:format=auto{out_label}")
            current=out_label
        filters.append(f"{current}format=yuv420p[vout]")
        cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-an", "-c:v", "libx264", "-preset", p["preset"], "-crf", str(p["crf"]), "-pix_fmt", "yuv420p", str(out)]
        self._run_atomic(cmd, out)
        return out

    @staticmethod
    def _cinematic_bar_height(aspect: float, width: int, height: int) -> float:
        aspect = max(1e-6, float(aspect))
        visible_h = min(float(height), float(width) / aspect)
        return max(0.0, (float(height) - visible_h) / 2.0)

    def _cinematic_bar_expr(self, scene: dict, p: dict) -> tuple[str, int] | None:
        spec = scene.get("cinematic") or {}
        path = spec.get("frame_path") or []
        if not path:
            return None
        duration = max(1e-6, float(scene.get("duration", 0.0)))
        pts = []
        for row in path:
            try:
                tn = max(0.0, min(1.0, float(row.get("t", 0.0))))
                aspect = float(row.get("aspect", float(p["width"]) / float(p["height"])))
            except (TypeError, ValueError):
                continue
            pts.append((tn * duration, self._cinematic_bar_height(aspect, p["width"], p["height"])))
        if not pts:
            return None
        pts.sort(key=lambda x: x[0])
        if pts[0][0] > 1e-6:
            pts.insert(0, (0.0, pts[0][1]))
        if pts[-1][0] < duration - 1e-6:
            pts.append((duration, pts[-1][1]))
        max_bar = int(round(max(h for _, h in pts)))
        if max_bar <= 0:
            return None
        max_bar = max(2, max_bar + (max_bar % 2))
        easing = str(spec.get("frame_easing", "smooth"))
        expr = f"{pts[-1][1]:.6f}"
        for (t0, h0), (t1, h1) in reversed(list(zip(pts[:-1], pts[1:]))):
            dt = max(1e-6, t1 - t0)
            q = f"max(0,min(1,(t-{t0:.6f})/{dt:.6f}))"
            if easing == "snap":
                interp = f"{h0:.6f}"
            elif easing == "linear":
                interp = f"({h0:.6f}+({h1-h0:.6f})*({q}))"
            else:
                smooth = f"(({q})*({q})*(3-2*({q})))"
                interp = f"({h0:.6f}+({h1-h0:.6f})*({smooth}))"
            expr = f"if(lt(t,{t1:.6f}),{interp},{expr})"
        return expr, max_bar

    def _apply_cinematic_frame(self, scene: dict, base: Path, p: dict) -> Path:
        compiled = self._cinematic_bar_expr(scene, p)
        if compiled is None:
            return base
        height_expr, max_bar = compiled
        spec = scene.get("cinematic") or {}
        key = hash_obj({"base": base.name, "cinematic": spec, "profile": p, "backend": "moving_bars_v3_tpad"})[:20]
        out = self.root / "cache" / f"cinematic_{scene['id']}_{key}.mp4"
        if self._cache_ready(out):
            return out
        duration = float(scene["duration"])
        # Give overlay sources two guard frames beyond the scene. Exact-duration lavfi color
        # sources can otherwise end one frame before the base due to timestamp rounding, which
        # used to shorten every cinematic fragment and corrupt downstream xfade offsets.
        guarded = duration + 2.0 / max(1, int(p["fps"]))
        bar_src = f"color=c=black:s={p['width']}x{max_bar}:r={p['fps']}:d={guarded:.6f}"
        cmd = [
            self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(base),
            "-f", "lavfi", "-i", bar_src,
            "-f", "lavfi", "-i", bar_src,
        ]
        filters = (
            f"[0:v]setpts=PTS-STARTPTS[base];"
            f"[base][1:v]overlay=x=0:y='({height_expr})-{max_bar}':eval=frame:eof_action=pass[top];"
            f"[top][2:v]overlay=x=0:y='H-({height_expr})':eval=frame:eof_action=pass,"
            f"tpad=stop_mode=clone:stop_duration={2.0/max(1,int(p['fps'])):.6f},trim=duration={duration:.6f},fps={p['fps']},format=yuv420p[v]"
        )
        cmd += [
            "-filter_complex", filters, "-map", "[v]", "-an", "-t", f"{duration:.6f}",
            "-c:v", "libx264", "-preset", p["preset"], "-crf", str(p["crf"]),
            "-pix_fmt", "yuv420p", str(out),
        ]
        self._run_atomic(cmd, out)
        return out

    def render_single_scene(self, scene_id: str, *, profile="preview", output: str | Path | None = None) -> Path:
        p = self._profile(profile)
        scene = next((s for s in self.project["scenes"] if s["id"] == scene_id), None)
        if scene is None:
            raise AgentCutError("SCENE_NOT_FOUND", "Unknown scene", scene=scene_id)
        base = self._render_scene_base(scene, p)
        layered = self._apply_layers(scene, base, p)
        fx = self._apply_effects(scene, layered, p)
        cinematic = self._apply_cinematic_frame(scene, fx, p)
        if output is None:
            output = self.root / "preview" / f"{scene_id}_{profile}.mp4"
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cinematic, output)
        write_render_manifest(
            output,
            project=self.project,
            profile=f"scene:{profile}",
            expected_duration=float(scene["duration"]),
            render_profile=p,
            context={"scene_id": scene_id},
        )
        return output

    def _timeline(self) -> tuple[list[float], float, list[float]]:
        timeline = require_nonempty_timeline(self.project)
        starts = [float(row["start"]) for row in timeline["scenes"]]
        tr_durations = [float(tr["effective_duration"]) for tr in timeline["transitions"]]
        return starts, float(timeline["duration"]), tr_durations

    @staticmethod
    def _item_transition_duration(item: dict, next_item: dict | None) -> float:
        if next_item is None:
            return 0.0
        tr = item.get("transition_out") or {"type": "cut", "duration": 0.0}
        if tr.get("type", "cut") == "cut":
            return 0.0
        duration = max(0.0, float(tr.get("duration", 0.0)))
        max_overlap = min(float(item["duration"]), float(next_item["duration"]))
        return min(duration, max(0.0, max_overlap - 1e-6))

    def _combine_sequence_direct(self, items: list[dict], p: dict, *, level: int) -> dict:
        """Combine a small sequence into one cache artifact.

        The caller guarantees a bounded number of inputs. Keeping each filter graph small
        avoids the long xfade chains that made v0.1.x fragile on 2+ minute timelines.
        """
        if not items:
            raise AgentCutError("EMPTY_RENDER_GROUP", "Cannot combine an empty render group")
        if len(items) == 1:
            return dict(items[0])

        semantics = [
            {
                "path": Path(item["path"]).name,
                "duration": float(item["duration"]),
                "transition_out": item.get("transition_out") or {"type": "cut", "duration": 0.0},
                "first_scene": item.get("first_scene"),
                "last_scene": item.get("last_scene"),
            }
            for item in items
        ]
        key = hash_obj({"items": semantics, "profile": p, "level": level})[:20]
        out = self.root / "cache" / f"visual_dag_l{level}_{key}.mp4"

        current_duration = float(items[0]["duration"])
        for i in range(1, len(items)):
            current_duration += float(items[i]["duration"]) - self._item_transition_duration(items[i - 1], items[i])

        result = {
            "path": out,
            "duration": current_duration,
            "transition_out": items[-1].get("transition_out") or {"type": "cut", "duration": 0.0},
            "first_scene": items[0].get("first_scene"),
            "last_scene": items[-1].get("last_scene"),
        }
        if self._cache_ready(out):
            return result

        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        for item in items:
            cmd += ["-i", str(item["path"])]

        filters: list[str] = []
        for i in range(len(items)):
            filters.append(f"[{i}:v]settb=AVTB,setpts=PTS-STARTPTS,fps={p['fps']}[v{i}]")

        current = "[v0]"
        running_duration = float(items[0]["duration"])
        for i in range(1, len(items)):
            prev = items[i - 1]
            nxt = items[i]
            tr = prev.get("transition_out") or {"type": "cut", "duration": 0.0}
            raw_label = f"[raw{i}]"
            label = f"[x{i}]"
            if tr.get("type", "cut") == "cut":
                filters.append(f"{current}[v{i}]concat=n=2:v=1:a=0{raw_label}")
                running_duration += float(nxt["duration"])
            else:
                dur = self._item_transition_duration(prev, nxt)
                trans = XFADES.get(tr.get("type", "fade"), transition_backend(tr.get("type", "fade")))
                offset = running_duration - dur
                filters.append(f"{current}[v{i}]xfade=transition={trans}:duration={dur:.6f}:offset={offset:.6f}{raw_label}")
                running_duration += float(nxt["duration"]) - dur
            filters.append(f"{raw_label}settb=AVTB,setpts=PTS-STARTPTS,fps={p['fps']}{label}")
            current = label

        cmd += [
            "-filter_complex", ";".join(filters), "-map", current,
            "-an", "-c:v", "libx264", "-preset", p["preset"], "-crf", str(p["crf"]),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
        ]
        self._run_atomic(cmd, out)
        return result

    def _combine_sequence_dag(self, items: list[dict], p: dict, *, level: int = 0, fan_in: int = 4) -> dict:
        """Hierarchically combine timeline items with a bounded filter-graph fan-in."""
        if len(items) <= fan_in:
            return self._combine_sequence_direct(items, p, level=level)
        groups: list[dict] = []
        for i in range(0, len(items), fan_in):
            groups.append(self._combine_sequence_direct(items[i:i + fan_in], p, level=level))
        return self._combine_sequence_dag(groups, p, level=level + 1, fan_in=fan_in)

    def _combine_visuals(self, rendered_scenes: list[Path], p: dict) -> tuple[Path, float]:
        timeline = require_nonempty_timeline(self.project)
        scenes = self.project.get("scenes", [])
        items = [
            {
                "path": path,
                "duration": float(scene["duration"]),
                "transition_out": scene.get("transition_out") or {"type": "cut", "duration": 0.0},
                "first_scene": scene["id"],
                "last_scene": scene["id"],
            }
            for scene, path in zip(scenes, rendered_scenes)
        ]
        result = self._combine_sequence_dag(items, p)
        expected = float(timeline["duration"])
        if abs(float(result["duration"]) - expected) > max(0.001, 1 / max(1, p["fps"])):
            raise AgentCutError(
                "RENDER_DAG_DURATION_MISMATCH",
                "Hierarchical visual composition changed timeline duration",
                expected=expected,
                actual=float(result["duration"]),
            )
        return Path(result["path"]), expected

    @staticmethod
    def _ass_time(seconds: float) -> str:
        seconds = max(0.0, seconds)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    @staticmethod
    def _ass_escape(text: str) -> str:
        return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")

    @staticmethod
    def _ass_color(hex_color: str | None) -> str:
        raw = str(hex_color or "#FFFFFF").lstrip("#")
        if len(raw) != 6:
            raw = "FFFFFF"
        rr, gg, bb = raw[0:2], raw[2:4], raw[4:6]
        return f"&H00{bb}{gg}{rr}&".upper()

    @staticmethod
    def _wrap_dialogue_text(text: str, max_chars: int | None) -> str:
        text = str(text)
        if not max_chars or max_chars < 8 or "\n" in text or len(text) <= max_chars:
            return text
        # Prefer punctuation near the target width. This is deterministic and works well for CJK
        # dialogue without pulling in a language tokenizer. Limit to two lines unless text is huge.
        chunks = []
        remaining = text
        while len(remaining) > max_chars and len(chunks) < 2:
            lo = max(1, int(max_chars * .62)); hi = min(len(remaining) - 1, int(max_chars * 1.15))
            candidates = [i + 1 for i, ch in enumerate(remaining[:hi]) if i + 1 >= lo and ch in "，。！？；：、,.!?;:"]
            cut = candidates[-1] if candidates else max_chars
            chunks.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()
        if remaining:
            chunks.append(remaining)
        return "\n".join(x for x in chunks if x)

    def _dialogue_duration(self, seg: dict, scene: dict) -> float:
        if seg.get("duration") is not None:
            return float(seg["duration"])
        aid = seg.get("audio_asset_id")
        if aid is not None:
            asset = self.project.get("assets", {}).get(aid, {})
            try:
                return float((asset.get("metadata") or {}).get("format", {}).get("duration"))
            except (TypeError, ValueError):
                pass
        return max(0.01, float(scene["duration"]) - float(seg.get("start", 0.0)))

    def _compiled_dialogue_captions(self) -> list[dict]:
        timeline = build_timeline(self.project)
        starts = {row["scene_id"]: float(row["start"]) for row in timeline["scenes"]}
        scenes = {s["id"]: s for s in self.project.get("scenes", [])}
        compiled = []
        for seg in self.project.get("dialogue_segments", []):
            scene = scenes.get(seg.get("scene_id"))
            if scene is None:
                continue
            start = starts[scene["id"]] + float(seg.get("start", 0.0))
            dur = self._dialogue_duration(seg, scene)
            character = (self.project.get("cast", {}) or {}).get(seg.get("character_id")) or {}
            compiled.append({
                "id": seg.get("id"), "text": self._resolve_text(seg.get("text", "")),
                "start": start, "end": start + dur,
                "speaker": seg.get("speaker") or character.get("display_name"),
                "character_id": seg.get("character_id"), "speaker_color": character.get("color", "#FFFFFF"),
                "position": seg.get("position", "bottom"),
                "font_size": int(seg.get("font_size", 54)),
                "outline": int(seg.get("outline", 3)),
                "subtitle_style": seg.get("subtitle_style", "default"),
                "emotion": seg.get("emotion", "neutral"),
                "max_line_chars": seg.get("max_line_chars"),
                "secondary_max_line_chars": seg.get("secondary_max_line_chars"),
                "secondary_text": seg.get("secondary_text"),
                "secondary_language": seg.get("secondary_language", "en"),
                "secondary_font_scale": seg.get("secondary_font_scale", 0.72),
            })
        return compiled

    def _make_ass(self, p: dict) -> Path | None:
        captions = list(self.project.get("captions", [])) + self._compiled_dialogue_captions()
        captions = sorted(captions, key=lambda x: x["start"])
        if not captions:
            return None
        out = self.root / "cache" / f"captions_{hash_obj({'captions': captions, 'p': p})[:20]}.ass"
        if self._cache_ready(out):
            return out
        base_scale = p["height"] / 1080.0
        header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: {p['width']}\nPlayResY: {p['height']}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Noto Sans CJK SC,{max(18,int(54*base_scale))},&H00FFFFFF,&H000000FF,&H00111111,&H55000000,0,0,0,0,100,100,0,0,1,{max(1,int(3*base_scale))},0,2,80,80,{max(30,int(58*base_scale))},1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"""
        lines = [header]
        for c in captions:
            body_raw = self._wrap_dialogue_text(self._resolve_text(c["text"]), c.get("max_line_chars"))
            body = self._ass_escape(body_raw)
            speaker_raw = str(c.get("speaker") or "")
            speaker = self._ass_escape(speaker_raw)
            if speaker:
                speaker_color_value = c.get("speaker_color")
                if not speaker_color_value:
                    cast = self.project.get("cast", {}) or {}
                    character = cast.get(c.get("character_id")) if c.get("character_id") else None
                    if not character:
                        key = speaker_raw.strip().casefold()
                        for row in cast.values():
                            names = [row.get("id"), row.get("display_name"), *(row.get("aliases") or [])]
                            if key in {str(x).strip().casefold() for x in names if x}:
                                character = row
                                break
                    speaker_color_value = (character or {}).get("color")
                speaker_color = self._ass_color(speaker_color_value)
                text = f"{{\\c{speaker_color}\\b1}}{speaker}：{{\\c&H00FFFFFF&\\b0}}{body}"
            else:
                text = body
            secondary_raw = str(c.get("secondary_text") or "").strip()
            if secondary_raw:
                secondary_wrap = c.get("secondary_max_line_chars")
                if secondary_wrap is None:
                    secondary_wrap = max(24, int(c.get("max_line_chars") or 30) + 10)
                secondary = self._ass_escape(self._wrap_dialogue_text(secondary_raw, int(secondary_wrap)))
                secondary_scale = max(0.35, min(1.5, float(c.get("secondary_font_scale", 0.72))))
                secondary_size = max(16, int(int(c.get("font_size", 54)) * base_scale * secondary_scale))
                text += f"\\N{{\\fs{secondary_size}\\c&H00D9D9D9&\\b0\\i0}}{secondary}"
            alignment = {
                "top_left": 7, "top": 8, "top_right": 9,
                "left": 4, "center": 5, "right": 6,
                "bottom_left": 1, "bottom": 2, "bottom_right": 3,
            }.get(c.get("position", "bottom"), 2)
            size = max(18, int(int(c.get("font_size", 54)) * base_scale))
            outline = max(0, int(int(c.get("outline", 3)) * base_scale))
            style = str(c.get("subtitle_style", "default"))
            emotion = str(c.get("emotion", "neutral"))
            extras = ""
            if style == "band": extras += "\\fad(55,85)"
            elif style == "thought": extras += "\\i1\\alpha&H18&\\fad(90,130)"
            elif style == "shout": extras += "\\b1\\fscx106\\fscy106\\fad(35,65)"
            elif style == "whisper": extras += "\\alpha&H22&\\fad(100,130)"
            elif style == "aside": extras += "\\i1\\fad(70,110)"
            elif style == "karaoke": extras += "\\b1\\fad(35,55)\\fscx103\\fscy103"
            elif style == "neon": extras += "\\b1\\bord4\\shad2\\3c&H00FF70D8&\\4c&H00302050&\\fad(45,75)"
            elif style == "manga": extras += "\\b1\\bord5\\3c&H00000000&\\fad(25,55)"
            elif style == "boxed": extras += "\\b1\\bord7\\3c&H78000000&\\shad0\\fad(50,70)"
            elif style == "cinematic": extras += "\\fsp1\\fad(180,220)"
            elif style == "lower_third": extras += "\\b1\\fad(70,90)\\bord2"
            elif style == "bilingual": extras += "\\fad(55,85)"
            if emotion in {"excited", "angry", "impact"} and style not in {"shout"}:
                extras += "\\b1"
            override = f"{{\\an{alignment}\\fs{size}\\bord{outline}{extras}}}"
            lines.append(f"Dialogue: 0,{self._ass_time(c['start'])},{self._ass_time(c['end'])},Default,,0,0,0,,{override}{text}\n")
        out.write_text("".join(lines), encoding="utf-8")
        return out

    def _collect_audio(self, starts: list[float], total: float) -> list[dict]:
        tracks = []
        for tr in self.project.get("audio_tracks", []):
            item = dict(tr)
            item["timeline_start"] = float(tr.get("start", 0.0))
            item["effective_duration"] = float(tr["duration"]) if tr.get("duration") is not None else max(0.01, total - item["timeline_start"])
            tracks.append(item)
        scenes = self.project.get("scenes", [])
        for scene, scene_start in zip(scenes, starts):
            for tr in scene.get("audio", []):
                item = dict(tr)
                item["timeline_start"] = scene_start + float(tr.get("start", 0.0))
                max_scene_dur = max(0.01, float(scene["duration"]) - float(tr.get("start", 0.0)))
                item["effective_duration"] = float(tr["duration"]) if tr.get("duration") is not None else max_scene_dur
                tracks.append(item)

        # Dialogue segments are scene-relative single-source items: their text drives ASS
        # captions and the same object schedules the optional TTS/audio asset.
        by_scene = {s["id"]: (s, st) for s, st in zip(scenes, starts)}
        for seg in self.project.get("dialogue_segments", []):
            if not seg.get("audio_asset_id") or seg.get("scene_id") not in by_scene:
                continue
            scene, scene_start = by_scene[seg["scene_id"]]
            tracks.append({
                "id": f"dialogue_audio_{seg.get('id')}",
                "asset_id": seg["audio_asset_id"],
                "kind": "dialogue",
                "volume_db": float(seg.get("volume_db", 0.0)),
                "timeline_start": scene_start + float(seg.get("start", 0.0)),
                "effective_duration": self._dialogue_duration(seg, scene),
                "fade_in": 0.0, "fade_out": 0.0, "loop": False,
            })

        # A transition whoosh/impact is derived from the exact same transition event that
        # drives xfade/concat. Visual and SFX timing therefore cannot silently diverge.
        timeline = build_timeline(self.project)
        transition_rows = {(tr["from_scene"], tr["to_scene"]): tr for tr in timeline["transitions"]}
        for i, scene in enumerate(scenes[:-1]):
            tr = scene.get("transition_out") or {}
            sfx = tr.get("sfx")
            if not sfx:
                continue
            nxt = scenes[i + 1]
            row = transition_rows[(scene["id"], nxt["id"])]
            start = max(0.0, float(row["start"]) + float(sfx.get("offset", 0.0)))
            asset = self.project.get("assets", {}).get(sfx["asset_id"], {})
            try:
                asset_dur = float((asset.get("metadata") or {}).get("format", {}).get("duration"))
            except (TypeError, ValueError):
                asset_dur = max(0.05, float(row.get("effective_duration", 0.0)) or 0.35)
            tracks.append({
                "id": f"transition_sfx_{scene['id']}",
                "asset_id": sfx["asset_id"], "kind": "sfx",
                "volume_db": float(sfx.get("volume_db", -12.0)),
                "timeline_start": start, "effective_duration": max(0.01, asset_dur),
                "fade_in": float(sfx.get("fade_in", 0.0)),
                "fade_out": float(sfx.get("fade_out", 0.08)),
                "loop": False,
            })
        return tracks

    def _apply_shared_morphs(self, visual: Path, p: dict, total: float) -> Path:
        scenes = self.project.get("scenes", [])
        timeline = build_timeline(self.project)
        by_pair = {(x["from_scene"], x["to_scene"]): x for x in timeline.get("transitions", [])}
        overlays = []
        for i, scene in enumerate(scenes[:-1]):
            tr = scene.get("transition_out") or {}
            if tr.get("type") != "shared_morph":
                continue
            nxt = scenes[i + 1]
            row = by_pair.get((scene["id"], nxt["id"])) or {}
            dur = float(row.get("effective_duration", 0.0))
            if dur <= 0:
                continue
            shared_a = {x.get("shared_id") for x in scene.get("layers", []) if x.get("shared_id")}
            shared_b = {x.get("shared_id") for x in nxt.get("layers", []) if x.get("shared_id")}
            if not (shared_a & shared_b):
                continue
            gp = shared_morph_cache_path(self.root/"cache", scene, nxt, self.project.get("facts", {}), p["width"], p["height"], p["fps"], dur)
            generate_shared_morph_video(gp, scene, nxt, self.project, self.root, p["width"], p["height"], p["fps"], dur)
            overlays.append({"path": gp, "start": float(row.get("start", 0.0)), "duration": dur, "from": scene["id"], "to": nxt["id"]})
        if not overlays:
            return visual
        key=hash_obj({"visual":Path(visual).name,"overlays":[{**x,"path":Path(x["path"]).name} for x in overlays],"profile":p,"total":total})[:20]
        out=self.root/"cache"/f"shared_morph_composite_{key}.mp4"
        if self._cache_ready(out):
            return out
        cmd=[self.ffmpeg,"-hide_banner","-loglevel","error","-y","-i",str(visual)]
        for item in overlays:
            cmd += ["-i", str(item["path"])]
        filters=["[0:v]format=rgba[base0]"]
        current="[base0]"
        for i,item in enumerate(overlays, start=1):
            ov=f"[ov{i}]"; nxt=f"[m{i}]"
            filters.append(f"[{i}:v]format=rgba,setpts=PTS-STARTPTS+{item['start']:.6f}/TB{ov}")
            filters.append(f"{current}{ov}overlay=0:0:format=auto:eof_action=pass:shortest=0{nxt}")
            current=nxt
        filters.append(f"{current}format=yuv420p[vout]")
        cmd += ["-filter_complex",";".join(filters),"-map","[vout]","-an","-t",f"{total:.6f}","-c:v","libx264","-preset",p["preset"],"-crf",str(p["crf"]),"-pix_fmt","yuv420p",str(out)]
        self._run_atomic(cmd,out)
        return out

    def _finalize(self, visual: Path, p: dict, total: float, output: Path, *, profile_name: str) -> Path:
        starts, _, _ = self._timeline()
        audio = self._collect_audio(starts, total)
        ass = self._make_ass(p)
        output.parent.mkdir(parents=True, exist_ok=True)
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(visual)]
        for tr in audio:
            if tr.get("loop"):
                cmd += ["-stream_loop", "-1"]
            cmd += ["-i", str(self._asset_path(tr["asset_id"]))]

        filters = []
        vmap = "0:v"
        if ass:
            ass_path = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
            filters.append(f"[0:v]ass=filename='{ass_path}'[vout]")
            vmap = "[vout]"

        audio_labels = []
        for idx, tr in enumerate(audio, start=1):
            dur = max(0.01, float(tr["effective_duration"]))
            delay_ms = max(0, int(round(float(tr["timeline_start"]) * 1000)))
            fade_in = min(max(0.0, float(tr.get("fade_in", 0))), dur / 2)
            fade_out = min(max(0.0, float(tr.get("fade_out", 0))), dur / 2)
            volume = float(tr.get("volume_db", 0.0))
            chain = f"[{idx}:a]atrim=0:{dur:.6f},asetpts=PTS-STARTPTS,volume={volume:.3f}dB"
            if fade_in > 0:
                chain += f",afade=t=in:st=0:d={fade_in:.6f}"
            if fade_out > 0:
                chain += f",afade=t=out:st={max(0,dur-fade_out):.6f}:d={fade_out:.6f}"
            if delay_ms > 0:
                chain += f",adelay={delay_ms}:all=1"
            label = f"[a{idx}]"
            chain += label
            filters.append(chain)
            audio_labels.append(label)

        amap = None
        if audio_labels:
            filters.append(
                f"{''.join(audio_labels)}amix=inputs={len(audio_labels)}:normalize=0:dropout_transition=0,"
                f"alimiter=limit=0.95,apad=pad_dur={total:.6f},atrim=0:{total:.6f}[aout]"
            )
            amap = "[aout]"

        if filters:
            cmd += ["-filter_complex", ";".join(filters)]
        cmd += ["-map", vmap]
        if amap:
            cmd += ["-map", amap, "-c:a", "aac", "-b:a", p["audio_bitrate"]]
        cmd += [
            "-t", f"{total:.6f}", "-c:v", "libx264", "-preset", p["preset"], "-crf", str(p["crf"]),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)
        ]
        self._run_atomic(cmd, output)
        write_render_manifest(output, project=self.project, profile=profile_name, expected_duration=total, render_profile=p)
        return output

    def render(self, *, profile="preview", output: str | Path | None = None, profile_override: dict | None = None) -> Path:
        p = self._profile(profile, profile_override)
        scenes = self.project.get("scenes", [])
        if not scenes:
            raise AgentCutError("EMPTY_PROJECT", "Project has no scenes")
        rendered = []
        for scene in scenes:
            base = self._render_scene_base(scene, p)
            layered = self._apply_layers(scene, base, p)
            fx = self._apply_effects(scene, layered, p)
            rendered.append(self._apply_cinematic_frame(scene, fx, p))
        visual, total = self._combine_visuals(rendered, p)
        visual = self._apply_shared_morphs(visual, p, total)
        if output is None:
            target_dir = self.root / ("preview" if profile == "preview" else "output")
            if profile == "preview":
                filename = "preview.mp4"
            elif profile == "showcase":
                filename = "showcase_1080p.mp4"
            elif profile == "uhd_4k30":
                filename = "final_4k30.mp4"
            elif profile == "uhd_4k60":
                filename = "final_4k60.mp4"
            else:
                filename = "final_1080p.mp4"
            output = target_dir / filename
        return self._finalize(visual, p, total, Path(output), profile_name=profile)
