from __future__ import annotations

import math
import mimetypes
import shutil
import uuid
import re
from copy import deepcopy
from pathlib import Path

from .capabilities import CAPABILITIES
from .errors import AgentCutError
from .history import History
from .libraries import list_items as library_list_items, get_item as library_get_item
from .composition import CAPTION_ZONES, plan_composition, validate_composition, caption_zone_for_focus
from .cinematic import FRAME_PRESETS, FRAGMENT_STYLES, fragment_recipe, preset_frame_path, validate_cinematic
from .visual import analyze_image_path, analyze_video_path, choose_caption_zone, suggest_visual_anchors
from .rhythm import analyze_audio as analyze_audio_rhythm_file, suggest_cut_points
from .performance import (
    DIALOGUE_STYLES, PERFORMANCE_STYLES, dialogue_focus_path, estimate_dialogue_duration,
    normalize_color, performance_focus_path, plan_dialogue_sequence, resolve_character,
)
from .probe import probe
from .project import default_project, load_project, save_project, validate_project
from .timeline import build_timeline
from .util import file_sha256, hash_obj, json_dump, json_load
from .subtitles import transcribe_media, align_secondary, parse_srt, asr_status, split_speaker_prefix, infer_subtitle_style, fit_subtitle_layout
from .gen3 import normalize_config, validate_scene_gen3, category_layers, info_card_layers, make_blurred_background, chroma_key_image, make_actor_shadow, write_remotion_bundle


AUDIO_KINDS = {"bgm", "ambience", "sfx", "dialogue"}
EASINGS = {"linear", "ease", "ease_in", "ease_out", "ease_in_out", "smooth"}
ANCHORS = {"center", "top", "bottom", "left", "right", "top_left", "top_right", "bottom_left", "bottom_right"}
DIRECTIONS = {"auto", "up", "down", "left", "right", "up_left", "up_right", "down_left", "down_right"}
DEPTHS = {"foreground", "midground", "background"}
CAPTION_POSITIONS = set(CAPTION_ZONES)


VIDEO_MODES = {
    "1080p30": {"width": 1920, "height": 1080, "fps": 30},
    "1080p60": {"width": 1920, "height": 1080, "fps": 60},
    "4k30": {"width": 3840, "height": 2160, "fps": 30},
    "4k60": {"width": 3840, "height": 2160, "fps": 60},
    "uhd_4k30": {"width": 3840, "height": 2160, "fps": 30},
    "uhd_4k60": {"width": 3840, "height": 2160, "fps": 60},
}

def _finite(value: float, *, field: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise AgentCutError("INVALID_NUMBER", f"{field} must be finite", field=field, value=value)
    return value


class Editor:
    """High-level semantic editor API intended for autonomous agents.

    Public state getters return snapshots. Mutations must go through semantic methods so
    history, validation and cache behavior remain coherent.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.project = load_project(self.root)
        validate_project(self.project)
        self.history = History(self.root)
        self.history.initialize(self.project)
        self._batch_mode = False

    @classmethod
    def create(cls, root: str | Path, *, width=1920, height=1080, fps=30, name="Untitled AgentCut Project") -> "Editor":
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        for d in ("assets/images", "assets/video", "assets/audio", "assets/subtitles", "assets/fonts", "cache", "preview", "output"):
            (root / d).mkdir(parents=True, exist_ok=True)
        project = default_project(width, height, fps)
        project["name"] = name
        save_project(root, project)
        History(root).initialize(project)
        return cls(root)

    def _commit(self, label: str) -> None:
        if self._batch_mode:
            return
        save_project(self.root, self.project)
        self.history.commit(label, self.project)

    def _scene(self, scene_id: str) -> dict:
        for scene in self.project["scenes"]:
            if scene["id"] == scene_id:
                return scene
        raise AgentCutError("SCENE_NOT_FOUND", "Unknown scene", scene=scene_id)

    def _asset(self, asset_id: str) -> dict:
        try:
            return self.project["assets"][asset_id]
        except KeyError as exc:
            raise AgentCutError("INVALID_ASSET", "Unknown asset", asset_id=asset_id) from exc

    def get_project(self) -> dict:
        return deepcopy(self.project)

    def get_scene(self, scene_id: str) -> dict:
        return deepcopy(self._scene(scene_id))

    def get_assets(self) -> list[dict]:
        return deepcopy(list(self.project.get("assets", {}).values()))

    def get_audio_mix(self) -> dict:
        return deepcopy({
            "global_tracks": self.project.get("audio_tracks", []),
            "scene_tracks": [
                {"scene_id": s["id"], "tracks": s.get("audio", [])}
                for s in self.project.get("scenes", []) if s.get("audio")
            ],
        })

    def set_video_mode(self, preset: str) -> dict:
        key = str(preset).strip().lower()
        if key not in VIDEO_MODES:
            raise AgentCutError("VIDEO_MODE_NOT_FOUND", "Unknown video mode preset", preset=preset, allowed=sorted(VIDEO_MODES))
        self.project["video"] = deepcopy(VIDEO_MODES[key])
        validate_project(self.project)
        self._commit(f"set_video_mode:{key}")
        return {"preset": key, **deepcopy(self.project["video"])}

    def get_timeline(self) -> dict:
        return deepcopy(build_timeline(self.project))

    def configure_gen3(self, **config) -> dict:
        """Configure the Gen3/Jane3 director layer at project level."""
        base = deepcopy(self.project.get("gen3") or {})
        base.update(config)
        self.project["gen3"] = normalize_config(base)
        validate_project(self.project)
        self._commit("configure_gen3")
        return deepcopy(self.project["gen3"])

    def set_gen3_scene(self, scene_id: str, *, kind: str = "exhibit", category: str | None = None,
                       work_title: str | None = None, author: str | None = None,
                       motion: str = "static", card: dict | None = None) -> dict:
        scene = self._scene(scene_id)
        meta = {"kind": kind, "motion": motion, "actors": deepcopy((scene.get("gen3") or {}).get("actors", []))}
        if category is not None: meta["category"] = str(category)
        if work_title is not None: meta["work_title"] = str(work_title)
        if author is not None: meta["author"] = str(author)
        if card is not None: meta["card"] = deepcopy(card)
        meta = validate_scene_gen3(meta, scene_duration=float(scene["duration"]))
        scene["gen3"] = meta
        # Stillness-first is a semantic default, not a ban on deliberate motion.
        if self.project.get("gen3", {}).get("stillness_first", True) and motion == "static":
            scene["camera"] = {"type": "static", "amount": 0.0, "easing": "linear", "anchor": "center"}
        self._compile_gen3_scene(scene_id)
        validate_project(self.project)
        self._commit(f"set_gen3_scene:{scene_id}")
        return deepcopy(scene["gen3"])

    def set_gen3_card(self, scene_id: str, *, title: str, body: str, subtitle: str | None = None,
                      start: float = 3.0, duration: float = 3.2, blur: bool = True,
                      category: str | None = None, kind: str = "info_card") -> dict:
        scene = self._scene(scene_id)
        current = deepcopy(scene.get("gen3") or {})
        current.update({"kind": kind, "motion": current.get("motion", "static")})
        if category is not None: current["category"] = category
        current["card"] = {"title": title, "subtitle": subtitle, "body": body, "start": float(start), "duration": float(duration), "blur": bool(blur)}
        current.setdefault("actors", [])
        scene["gen3"] = validate_scene_gen3(current, scene_duration=float(scene["duration"]))
        self._compile_gen3_scene(scene_id)
        validate_project(self.project)
        self._commit(f"set_gen3_card:{scene_id}")
        return deepcopy(scene["gen3"])

    def register_gen3_actor_card(self, path: str, *, asset_id: str | None = None, key_color: str | None = None,
                                 make_shadow: bool = True) -> dict:
        """Import a solid-key actor card and rebuild a deterministic RGBA matte."""
        src = Path(path).expanduser().resolve()
        if not src.exists():
            raise AgentCutError("FILE_NOT_FOUND", "Actor card file not found", path=str(src))
        aid = asset_id or f"actor_{uuid.uuid4().hex[:8]}"
        if aid in self.project.get("assets", {}):
            raise AgentCutError("ASSET_EXISTS", "Asset id already exists", asset_id=aid)
        key = key_color or self.project.get("gen3", {}).get("actor_matte_key", "#FF00FF")
        actor_rel = Path("assets/images") / f"{aid}_rgba.png"
        actor_abs = self.root / actor_rel
        chroma_key_image(src, actor_abs, key_color=key)
        self.project["assets"][aid] = {"id": aid, "name": actor_abs.name, "type": "image", "path": str(actor_rel), "sha256": file_sha256(actor_abs), "tags": {"gen3_actor": True, "matte_key": key}}
        shadow_id = None
        if make_shadow:
            shadow_id = f"{aid}_shadow"
            shadow_rel = Path("assets/images") / f"{shadow_id}.png"
            shadow_abs = self.root / shadow_rel
            make_actor_shadow(actor_abs, shadow_abs)
            self.project["assets"][shadow_id] = {"id": shadow_id, "name": shadow_abs.name, "type": "image", "path": str(shadow_rel), "sha256": file_sha256(shadow_abs), "tags": {"gen3_shadow": True, "source_actor": aid}}
        validate_project(self.project)
        self._commit(f"register_gen3_actor_card:{aid}")
        return {"asset_id": aid, "shadow_asset_id": shadow_id, "key_color": key, "path": str(actor_rel)}

    def place_gen3_actor(self, scene_id: str, asset_id: str, *, x: float, floor_y: float, scale: float = 1.0,
                         end_x: float | None = None, end_floor_y: float | None = None,
                         shadow_asset_id: str | None = None, z: int = 40, opacity: float = 1.0) -> dict:
        scene = self._scene(scene_id); asset = self._asset(asset_id)
        if asset.get("type") != "image":
            raise AgentCutError("INVALID_ASSET_TYPE", "Gen3 actor must be an image", asset_id=asset_id)
        for name, value in (("x", x), ("floor_y", floor_y), ("opacity", opacity)):
            if not 0 <= float(value) <= 1: raise AgentCutError("INVALID_GEN3_ACTOR", f"{name} must be in [0,1]", value=value)
        if scale <= 0: raise AgentCutError("INVALID_GEN3_ACTOR", "scale must be > 0")
        if end_x is not None and not 0 <= float(end_x) <= 1: raise AgentCutError("INVALID_GEN3_ACTOR", "end_x must be in [0,1]")
        if end_floor_y is not None and not 0 <= float(end_floor_y) <= 1: raise AgentCutError("INVALID_GEN3_ACTOR", "end_floor_y must be in [0,1]")
        meta = scene.setdefault("gen3", {"kind": "exhibit", "motion": "static", "actors": []})
        meta.setdefault("actors", [])
        row = {"asset_id": asset_id, "x": float(x), "y": float(floor_y), "scale": float(scale), "opacity": float(opacity), "z": int(z)}
        if shadow_asset_id: row["shadow_asset_id"] = shadow_asset_id
        if end_x is not None: row["end_x"] = float(end_x)
        if end_floor_y is not None: row["end_y"] = float(end_floor_y)
        # Replace placement for same actor asset instead of duplicating it accidentally.
        meta["actors"] = [a for a in meta["actors"] if a.get("asset_id") != asset_id] + [row]
        validate_scene_gen3(meta, scene_duration=float(scene["duration"]))
        self._compile_gen3_scene(scene_id)
        validate_project(self.project)
        self._commit(f"place_gen3_actor:{scene_id}:{asset_id}")
        return deepcopy(row)

    def _compile_gen3_scene(self, scene_id: str) -> dict:
        """Compile Gen3 semantics into ordinary AgentCut layers for deterministic fallback render."""
        from PIL import Image
        scene = self._scene(scene_id); meta = validate_scene_gen3(scene.get("gen3") or {}, scene_duration=float(scene["duration"]))
        video = self.project["video"]; width, height = int(video["width"]), int(video["height"]); duration = float(scene["duration"])
        scene["layers"] = [l for l in scene.get("layers", []) if not str(l.get("id", "")).startswith("gen3_")]
        layers = []
        if meta.get("category"):
            layers += category_layers(meta["category"], width=width, height=height, duration=duration)
        card = meta.get("card")
        if card and card.get("blur", True):
            bg = self._asset(scene["asset_id"])
            if bg.get("type") == "image":
                src = Path(bg["path"]); src = src if src.is_absolute() else self.root / src
                blur_id = f"gen3_blur_{scene_id}"
                rel = Path("assets/images") / f"{blur_id}.png"; out = self.root / rel
                make_blurred_background(src, out, width=width, height=height, radius=max(10, width/220), darken=.72)
                self.project["assets"][blur_id] = {"id": blur_id, "name": out.name, "type": "image", "path": str(rel), "sha256": file_sha256(out), "tags": {"gen3_generated": "card_blur", "scene_id": scene_id}}
                layers.append({"id": "gen3_card_blur", "type": "image", "asset_id": blur_id, "start": card["start"], "duration": card["duration"], "x": 0, "y": 0, "width": width, "height": height, "scale": 1.0, "opacity": 1.0, "rotation": 0.0, "z": 20, "keyframes": []})
        if card:
            layers += info_card_layers(card["title"], card.get("subtitle"), card["body"], width=width, height=height, start=card["start"], duration=card["duration"])
        for idx, actor in enumerate(meta.get("actors", [])):
            aid = actor["asset_id"]; asset = self._asset(aid); p = Path(asset["path"]); p = p if p.is_absolute() else self.root / p
            with Image.open(p) as im: aw, ah = im.size
            scale = float(actor.get("scale", 1)); x = float(actor.get("x", .5)); fy = float(actor.get("y", 1.0))
            x0 = x * width - aw * scale / 2; y0 = fy * height - ah * scale
            layer = {"id": f"gen3_actor_{idx}_{aid}", "type": "image", "asset_id": aid, "start": 0.0, "duration": duration, "x": x0, "y": y0, "scale": scale, "opacity": float(actor.get("opacity",1)), "rotation": 0.0, "z": int(actor.get("z",40)), "keyframes": []}
            if "end_x" in actor or "end_y" in actor:
                ex = float(actor.get("end_x", x)); efy = float(actor.get("end_y", fy)); x1 = ex*width-aw*scale/2; y1=efy*height-ah*scale
                layer["keyframes"]=[{"t":0.0,"x":x0,"y":y0},{"t":1.0,"x":x1,"y":y1,"easing":"ease_in_out"}]
            shid = actor.get("shadow_asset_id")
            if shid and shid in self.project["assets"]:
                sp=Path(self.project["assets"][shid]["path"]); sp=sp if sp.is_absolute() else self.root/sp
                with Image.open(sp) as sim: sw, sh=sim.size
                sl={"id":f"gen3_shadow_{idx}_{aid}","type":"image","asset_id":shid,"start":0.0,"duration":duration,"x":x*width-sw*scale/2,"y":fy*height-sh*scale*.55,"scale":scale,"opacity":1.0,"rotation":0.0,"z":int(actor.get("z",40))-1,"keyframes":[]}
                if layer["keyframes"]:
                    sl["keyframes"]=[{"t":0.0,"x":sl["x"],"y":sl["y"]},{"t":1.0,"x":ex*width-sw*scale/2,"y":efy*height-sh*scale*.55,"easing":"ease_in_out"}]
                layers.append(sl)
            layers.append(layer)
        scene["layers"].extend(layers)
        return {"scene_id": scene_id, "compiled_layers": len(layers), "gen3": deepcopy(meta)}

    def compile_gen3(self, scene_ids: list[str] | None = None) -> dict:
        ids = scene_ids or [s["id"] for s in self.project.get("scenes", []) if s.get("gen3")]
        results=[self._compile_gen3_scene(sid) for sid in ids]
        validate_project(self.project); self._commit(f"compile_gen3:{len(results)}")
        return {"compiled": len(results), "scenes": results}

    def register_remotion_component(self, source_path: str | Path, *, component_id: str,
                                    export_name: str = "default", props_schema: dict | None = None) -> dict:
        from .remotion_bridge import register_component
        row = register_component(self.project, self.root, source_path, component_id=component_id,
                                 export_name=export_name, props_schema=props_schema)
        validate_project(self.project)
        self._commit(f"register_remotion_component:{component_id}")
        return row

    def bind_remotion_component(self, scene_id: str, component_id: str, *, start: float, duration: float,
                                props: dict | None = None, z: int = 50, binding_id: str | None = None) -> dict:
        from .remotion_bridge import bind_component
        row = bind_component(self.project, scene_id=scene_id, component_id=component_id, start=start,
                             duration=duration, props=props, z=z, binding_id=binding_id)
        validate_project(self.project)
        self._commit(f"bind_remotion_component:{row['id']}")
        return row

    def remove_remotion_binding(self, binding_id: str) -> dict:
        from .remotion_bridge import remove_binding
        result = remove_binding(self.project, binding_id)
        validate_project(self.project)
        self._commit(f"remove_remotion_binding:{binding_id}")
        return result

    def export_gen3_remotion(self, output_dir: str | None = None) -> dict:
        from . import __version__
        from .remotion_bridge import write_bundle
        out = Path(output_dir) if output_dir else self.root / "remotion_gen3"
        return write_bundle(self.project, self.root, out, package_version=__version__)

    def verify_remotion_bundle(self, output_dir: str | None = None) -> dict:
        from .remotion_bridge import verify_bundle
        out = Path(output_dir) if output_dir else self.root / "remotion_gen3"
        return verify_bundle(out)

    def efficiency_start(self, *, arm: str, task_id: str, metadata: dict | None = None) -> dict:
        from .efficiency import start_session
        return start_session(self, arm=arm, task_id=task_id, metadata=metadata)

    def efficiency_finish(self, session_id: str, *, actual_usage: dict | None = None,
                          elapsed_seconds: float | None = None, tool_calls: int | None = None,
                          failed_commands: int | None = None, rendered_frames: int | None = None,
                          qa_issues: int | None = None, notes: str | None = None) -> dict:
        from .efficiency import finish_session
        return finish_session(self, session_id, actual_usage=actual_usage, elapsed_seconds=elapsed_seconds,
                              tool_calls=tool_calls, failed_commands=failed_commands, rendered_frames=rendered_frames,
                              qa_issues=qa_issues, notes=notes)

    def efficiency_measure(self, operations: list[dict] | None = None) -> dict:
        from .efficiency import structural_measure
        return structural_measure(self, operations)

    def efficiency_report(self) -> dict:
        from .efficiency import benchmark_report
        return benchmark_report(self)

    def list_capabilities(self) -> dict:
        return deepcopy(CAPABILITIES)

    def list_library(self, kind: str, *, tags: list[str] | None = None, stable_only: bool = False) -> list[dict]:
        return library_list_items(kind, tags=tags, stable_only=stable_only)

    def inspect_library_item(self, kind: str, item_id: str) -> dict:
        return library_get_item(kind, item_id)

    def state_digest(self) -> dict:
        versions = self.history.list_versions()
        current = next((v["version"] for v in versions if v["current"]), None)
        timeline = build_timeline(self.project)
        return {
            "project_hash": hash_obj(self.project),
            "history_version": current,
            "timeline_duration": timeline["duration"],
            "scene_count": len(self.project.get("scenes", [])),
            "asset_count": len(self.project.get("assets", {})),
            "caption_count": len(self.project.get("captions", [])),
            "dialogue_count": len(self.project.get("dialogue_segments", [])),
            "cast_count": len(self.project.get("cast", {})),
        }

    def set_fact(self, key: str, value) -> dict:
        if not isinstance(key, str) or not key.strip():
            raise AgentCutError("INVALID_FACT", "Fact key must be non-empty")
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise AgentCutError("INVALID_FACT", "Fact value must be scalar", key=key)
        self.project.setdefault("facts", {})[key] = value
        self._commit(f"set_fact:{key}")
        return {"key": key, "value": value}

    def remove_fact(self, key: str) -> dict:
        existed = key in self.project.setdefault("facts", {})
        value = self.project["facts"].pop(key, None)
        self._commit(f"remove_fact:{key}")
        return {"key": key, "removed": existed, "value": value}

    def resolve_text(self, text: str) -> str:
        facts = self.project.get("facts", {})
        def repl(m):
            k=m.group(1).strip()
            return str(facts[k]) if k in facts else m.group(0)
        return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", repl, str(text))

    def context_pack(self, *, scene_ids: list[str] | None = None) -> dict:
        timeline = build_timeline(self.project)
        wanted = set(scene_ids or [])
        scenes=[]
        for row in timeline.get("scenes", []):
            if wanted and row["scene_id"] not in wanted:
                continue
            scene=self._scene(row["scene_id"])
            scenes.append({
                "id":scene["id"], "asset_id":scene["asset_id"], "duration":scene["duration"],
                "camera":deepcopy(scene.get("camera")), "composition":deepcopy(scene.get("composition")), "cinematic":deepcopy(scene.get("cinematic")), "filters":list(scene.get("filters",[])),
                "effects":[{"type":x.get("type"),"preset_id":x.get("preset_id")} for x in scene.get("effects",[])],
                "layer_count":len(scene.get("layers",[])), "transition_out":deepcopy(scene.get("transition_out")),
                "timeline_start":row["start"],
            })
        rhythm = {}
        visual = {}
        for aid, asset in self.project.get("assets", {}).items():
            meta = asset.get("metadata") or {}
            ra = meta.get("rhythm")
            if ra:
                rhythm[aid] = {
                    "tempo_bpm": ra.get("tempo_bpm"),
                    "beat_count": len(ra.get("beats") or []),
                    "onset_count": len(ra.get("onsets") or []),
                }
            va = meta.get("visual")
            if va:
                visual[aid] = {
                    "focus_x": va.get("focus_x"), "focus_y": va.get("focus_y"),
                    "confidence": va.get("confidence"), "movement": va.get("movement", 0.0),
                    "caption_zone": va.get("caption_zone"),
                    "tracking_points": len(va.get("focus_path") or []),
                }
        return {
            "project":{"name":self.project.get("name"),"video":deepcopy(self.project.get("video")),"duration":timeline.get("duration",0),"project_hash":hash_obj(self.project)},
            "facts":deepcopy(self.project.get("facts",{})),
            "cast":deepcopy(self.project.get("cast",{})),
            "scenes":scenes,
            "rhythm": rhythm,
            "visual": visual,
            "libraries":deepcopy(CAPABILITIES.get("libraries",{})),
        }

    def add_asset(self, path: str | Path, *, asset_id: str | None = None, copy: bool = True, tags: dict | None = None) -> dict:
        src = Path(path).expanduser().resolve()
        if not src.exists() or not src.is_file():
            raise AgentCutError("FILE_NOT_FOUND", "Asset source does not exist", path=str(src))
        asset_id = asset_id or f"asset_{uuid.uuid4().hex[:8]}"
        if asset_id in self.project["assets"]:
            raise AgentCutError("ASSET_EXISTS", "Asset ID already exists", asset_id=asset_id)

        mime, _ = mimetypes.guess_type(src.name)
        if mime and mime.startswith("image/"):
            kind, subdir = "image", "images"
        elif mime and mime.startswith("video/"):
            kind, subdir = "video", "video"
        elif mime and mime.startswith("audio/"):
            kind, subdir = "audio", "audio"
        elif src.suffix.lower() in {".srt", ".ass", ".vtt"}:
            kind, subdir = "subtitle", "subtitles"
        elif src.suffix.lower() in {".ttf", ".otf", ".ttc"}:
            kind, subdir = "font", "fonts"
        else:
            raise AgentCutError("UNSUPPORTED_ASSET", "Unsupported asset type", path=str(src), suffix=src.suffix)

        if copy:
            dst = self.root / "assets" / subdir / f"{asset_id}{src.suffix.lower()}"
            shutil.copy2(src, dst)
        else:
            dst = src

        metadata: dict = {}
        if kind in {"video", "audio"}:
            try:
                metadata = probe(dst)
            except Exception:
                metadata = {}
        elif kind == "image":
            try:
                from PIL import Image
                with Image.open(dst) as im:
                    metadata = {"width": int(im.width), "height": int(im.height), "mode": im.mode, "format": im.format}
            except Exception:
                metadata = {}

        asset = {
            "id": asset_id,
            "name": src.name,
            "type": kind,
            "path": str(dst.relative_to(self.root)) if dst.is_relative_to(self.root) else str(dst),
            "sha256": file_sha256(dst),
            "tags": tags or {},
            "metadata": metadata,
        }
        self.project["assets"][asset_id] = asset
        self._commit(f"add_asset:{asset_id}")
        return deepcopy(asset)

    def tag_asset(self, asset_id: str, **tags) -> dict:
        asset = self._asset(asset_id)
        asset.setdefault("tags", {}).update(tags)
        self._commit(f"tag_asset:{asset_id}")
        return deepcopy(asset)

    def find_assets(self, **tags) -> list[dict]:
        out = []
        for asset in self.project["assets"].values():
            atags = asset.get("tags", {})
            if all(atags.get(k) == v for k, v in tags.items()):
                out.append(deepcopy(asset))
        return out

    def add_scene(
        self,
        asset_id: str,
        duration: float,
        *,
        scene_id: str | None = None,
        after: str | None = None,
        source_in: float = 0.0,
        playback_rate: float = 1.0,
    ) -> dict:
        asset = self._asset(asset_id)
        if asset["type"] not in {"image", "video"}:
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene asset must be image or video", asset_id=asset_id, type=asset["type"])
        duration = _finite(duration, field="duration")
        source_in = _finite(source_in, field="source_in")
        playback_rate = _finite(playback_rate, field="playback_rate")
        if duration <= 0:
            raise AgentCutError("INVALID_DURATION", "Duration must be > 0", duration=duration)
        if source_in < 0:
            raise AgentCutError("INVALID_SOURCE_IN", "source_in must be >= 0", source_in=source_in)
        if playback_rate <= 0 or playback_rate > 8:
            raise AgentCutError("INVALID_PLAYBACK_RATE", "playback_rate must be in (0, 8]", playback_rate=playback_rate)
        if asset["type"] == "image" and (source_in != 0 or playback_rate != 1):
            raise AgentCutError("INVALID_SOURCE_CONTROL", "source_in/playback_rate apply only to video scenes", asset_id=asset_id)

        scene_id = scene_id or self._next_scene_id()
        if any(s["id"] == scene_id for s in self.project["scenes"]):
            raise AgentCutError("SCENE_EXISTS", "Scene ID already exists", scene=scene_id)
        scene = {
            "id": scene_id,
            "asset_id": asset_id,
            "duration": duration,
            "source_in": source_in,
            "playback_rate": playback_rate,
            "camera": {"type": "static", "amount": 0.0, "easing": "linear", "anchor": "center"},
            "composition": {"mode": "cover", "background": "black", "frame_scale": 1.0, "crop_zoom": 1.0, "focus_x": 0.5, "focus_y": 0.5, "caption_zone": "bottom"},
            "effects": [],
            "filters": [],
            "layers": [],
            "audio": [],
            "transition_out": {"type": "cut", "duration": 0.0},
        }
        if after is None:
            self.project["scenes"].append(scene)
        else:
            idx = next((i for i, s in enumerate(self.project["scenes"]) if s["id"] == after), None)
            if idx is None:
                raise AgentCutError("SCENE_NOT_FOUND", "after scene not found", scene=after)
            self.project["scenes"].insert(idx + 1, scene)
        self._commit(f"add_scene:{scene_id}")
        return deepcopy(scene)

    def _next_scene_id(self) -> str:
        used = {s["id"] for s in self.project.get("scenes", [])}
        i = 1
        while f"scene_{i:02d}" in used:
            i += 1
        return f"scene_{i:02d}"

    def delete_scene(self, scene_id: str) -> dict:
        scene = self._scene(scene_id)
        self.project["scenes"].remove(scene)
        self._commit(f"delete_scene:{scene_id}")
        return {"deleted": scene_id}

    def set_scene_asset(self, scene_id: str, asset_id: str) -> dict:
        asset = self._asset(asset_id)
        if asset["type"] not in {"image", "video"}:
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene asset must be image or video", asset_id=asset_id, type=asset["type"])
        scene = self._scene(scene_id)
        if asset["type"] == "image":
            scene["source_in"] = 0.0
            scene["playback_rate"] = 1.0
        scene["asset_id"] = asset_id
        self._commit(f"set_scene_asset:{scene_id}:{asset_id}")
        return deepcopy(scene)

    def move_scene(self, scene_id: str, *, after: str | None = None, index: int | None = None) -> list[str]:
        if after is not None and index is not None:
            raise AgentCutError("INVALID_OPERATION", "Provide either after or index, not both")
        if after == scene_id:
            raise AgentCutError("INVALID_OPERATION", "A scene cannot be moved after itself", scene=scene_id)
        scene = self._scene(scene_id)
        scenes = self.project["scenes"]
        scenes.remove(scene)
        if index is not None:
            if index < 0 or index > len(scenes):
                raise AgentCutError("INVALID_INDEX", "Scene index out of range", index=index)
            scenes.insert(index, scene)
        elif after is not None:
            idx = next((i for i, s in enumerate(scenes) if s["id"] == after), None)
            if idx is None:
                raise AgentCutError("SCENE_NOT_FOUND", "after scene not found", scene=after)
            scenes.insert(idx + 1, scene)
        else:
            scenes.insert(0, scene)
        self._commit(f"move_scene:{scene_id}")
        return [s["id"] for s in scenes]

    def set_duration(self, scene_id: str, duration: float) -> dict:
        duration = _finite(duration, field="duration")
        if duration <= 0:
            raise AgentCutError("INVALID_DURATION", "Duration must be > 0", scene=scene_id, duration=duration)
        scene = self._scene(scene_id)
        scene["duration"] = duration
        self._commit(f"set_duration:{scene_id}")
        return deepcopy(scene)

    def set_source(self, scene_id: str, *, source_in: float | None = None, playback_rate: float | None = None) -> dict:
        scene = self._scene(scene_id)
        asset = self._asset(scene["asset_id"])
        if asset["type"] != "video":
            raise AgentCutError("INVALID_SOURCE_CONTROL", "Source trim/speed controls require a video scene", scene=scene_id)
        if source_in is not None:
            source_in = _finite(source_in, field="source_in")
            if source_in < 0:
                raise AgentCutError("INVALID_SOURCE_IN", "source_in must be >= 0", source_in=source_in)
            scene["source_in"] = source_in
        if playback_rate is not None:
            playback_rate = _finite(playback_rate, field="playback_rate")
            if playback_rate <= 0 or playback_rate > 8:
                raise AgentCutError("INVALID_PLAYBACK_RATE", "playback_rate must be in (0, 8]", playback_rate=playback_rate)
            scene["playback_rate"] = playback_rate
        self._commit(f"set_source:{scene_id}")
        return {"source_in": scene.get("source_in", 0.0), "playback_rate": scene.get("playback_rate", 1.0)}

    def add_layer(self, scene_id: str, layer_type: str, *, layer_id: str | None = None, start: float = 0.0, duration: float | None = None, shared_id: str | None = None, **props) -> dict:
        if layer_type not in {"text","rect","image"}:
            raise AgentCutError("UNSUPPORTED_LAYER", "Unsupported layer type", layer_type=layer_type)
        scene=self._scene(scene_id); layer_id=layer_id or f"layer_{uuid.uuid4().hex[:8]}"
        if any(x.get("id")==layer_id for x in scene.setdefault("layers",[])):
            raise AgentCutError("LAYER_EXISTS", "Layer id already exists", scene=scene_id, layer_id=layer_id)
        start=_finite(start,field="layer.start"); duration=float(scene["duration"]-start if duration is None else duration)
        if start<0 or duration<=0 or start+duration>float(scene["duration"])+1e-6:
            raise AgentCutError("INVALID_LAYER_TIME", "Layer timing must fit inside scene", scene=scene_id, start=start, duration=duration)
        layer={"id":layer_id,"type":layer_type,"start":start,"duration":duration,"x":float(props.pop("x",0)),"y":float(props.pop("y",0)),"scale":float(props.pop("scale",1)),"opacity":float(props.pop("opacity",1)),"rotation":float(props.pop("rotation",0)),"z":int(props.pop("z",0)),"keyframes":props.pop("keyframes",[])}
        if shared_id: layer["shared_id"]=shared_id
        layer.update(props)
        if layer_type=="image":
            aid=layer.get("asset_id"); asset=self._asset(aid)
            if asset["type"]!="image": raise AgentCutError("INVALID_ASSET_TYPE","Image layer requires image asset",asset_id=aid)
        scene["layers"].append(layer); self._commit(f"add_layer:{scene_id}:{layer_id}"); return deepcopy(layer)

    def update_layer(self, scene_id: str, layer_id: str, **changes) -> dict:
        scene=self._scene(scene_id); layer=next((x for x in scene.setdefault("layers",[]) if x.get("id")==layer_id),None)
        if layer is None: raise AgentCutError("LAYER_NOT_FOUND","Unknown layer",scene=scene_id,layer_id=layer_id)
        layer.update(changes); self._commit(f"update_layer:{scene_id}:{layer_id}"); return deepcopy(layer)

    def remove_layer(self, scene_id: str, layer_id: str) -> dict:
        scene=self._scene(scene_id); idx=next((i for i,x in enumerate(scene.setdefault("layers",[])) if x.get("id")==layer_id),None)
        if idx is None: raise AgentCutError("LAYER_NOT_FOUND","Unknown layer",scene=scene_id,layer_id=layer_id)
        removed=scene["layers"].pop(idx); self._commit(f"remove_layer:{scene_id}:{layer_id}"); return deepcopy(removed)

    def apply_layer_motion(self, scene_id: str, layer_id: str, preset_id: str, *, start: float | None = None, duration: float | None = None) -> dict:
        preset=library_get_item("layer_motions",preset_id); scene=self._scene(scene_id); layer=next((x for x in scene.setdefault("layers",[]) if x.get("id")==layer_id),None)
        if layer is None: raise AgentCutError("LAYER_NOT_FOUND","Unknown layer",scene=scene_id,layer_id=layer_id)
        spec=deepcopy(preset.get("defaults",{})); layer["motion"]={"preset_id":preset_id,"start":float(layer.get("start",0) if start is None else start),"duration":float(spec.get("duration",0.4) if duration is None else duration),"from":spec.get("from",{}),"to":spec.get("to",{})}
        self._commit(f"apply_layer_motion:{scene_id}:{layer_id}:{preset_id}"); return deepcopy(layer["motion"])

    def shared_element_plan(self, from_scene: str, to_scene: str) -> list[dict]:
        a={x.get("shared_id"):x for x in self._scene(from_scene).get("layers",[]) if x.get("shared_id")}; b={x.get("shared_id"):x for x in self._scene(to_scene).get("layers",[]) if x.get("shared_id")}; out=[]
        for sid in sorted(set(a)|set(b)):
            if sid in a and sid in b: out.append({"shared_id":sid,"mode":"morph","from":{k:a[sid].get(k) for k in ("x","y","scale","opacity","rotation")},"to":{k:b[sid].get(k) for k in ("x","y","scale","opacity","rotation")}})
            elif sid in a: out.append({"shared_id":sid,"mode":"fade_out"})
            else: out.append({"shared_id":sid,"mode":"fade_in"})
        return out

    def set_camera(self, scene_id: str, *, motion: str, amount: float = 0.035, easing: str = "linear", anchor: str = "center") -> dict:
        allowed = set(CAPABILITIES["camera"])
        if motion not in allowed:
            raise AgentCutError("UNSUPPORTED_CAMERA", "Unsupported camera motion", motion=motion, allowed=sorted(allowed))
        amount = _finite(amount, field="camera.amount")
        if amount < 0 or amount > 0.5:
            raise AgentCutError("INVALID_CAMERA_AMOUNT", "Camera amount must be in [0, 0.5]", amount=amount)
        if easing not in EASINGS:
            raise AgentCutError("UNSUPPORTED_EASING", "Unsupported easing", easing=easing, allowed=sorted(EASINGS))
        if anchor not in ANCHORS:
            raise AgentCutError("UNSUPPORTED_ANCHOR", "Unsupported camera anchor", anchor=anchor, allowed=sorted(ANCHORS))
        if motion == "static":
            amount = 0.0
        scene = self._scene(scene_id)
        scene["camera"] = {"type": motion, "amount": amount, "easing": easing, "anchor": anchor}
        self._commit(f"set_camera:{scene_id}:{motion}")
        return deepcopy(scene["camera"])

    def _asset_path(self, asset_id: str) -> Path:
        asset = self._asset(asset_id)
        path = Path(asset["path"])
        return path if path.is_absolute() else self.root / path

    @staticmethod
    def _asset_duration(asset: dict) -> float | None:
        meta = asset.get("metadata") or {}
        try:
            fmt = meta.get("format") or {}
            if isinstance(fmt, dict):
                value = fmt.get("duration")
                if value is not None:
                    return float(value)
            streams = meta.get("streams") or []
            for stream in streams:
                if isinstance(stream, dict) and stream.get("codec_type") == "video" and stream.get("duration") is not None:
                    return float(stream["duration"])
        except (TypeError, ValueError):
            return None
        return None

    def analyze_visual(self, asset_id: str, *, sample_count: int = 3) -> dict:
        """Analyze an image/video once and persist compact visual focus metadata on the asset.

        This is intentionally deterministic and lightweight: it estimates saliency/focus and safe
        text regions without requiring a heavyweight vision model. Explicit focus tags still win.
        """
        asset = self._asset(asset_id)
        if asset["type"] not in {"image", "video"}:
            raise AgentCutError("INVALID_ASSET_TYPE", "Visual analysis requires image or video asset", asset_id=asset_id, type=asset["type"])
        path = self._asset_path(asset_id)
        if asset["type"] == "image":
            analysis = analyze_image_path(path)
        else:
            analysis = analyze_video_path(path, duration=self._asset_duration(asset), sample_count=sample_count)
        asset.setdefault("metadata", {})["visual"] = deepcopy(analysis)
        self._commit(f"analyze_visual:{asset_id}")
        return deepcopy(analysis)

    def analyze_scene_visual(self, scene_id: str, *, sample_count: int = 3) -> dict:
        """Analyze the actual source segment used by a scene, suitable for auto-reframing video."""
        scene = self._scene(scene_id)
        asset = self._asset(scene["asset_id"])
        path = self._asset_path(scene["asset_id"])
        if asset["type"] == "image":
            cached = (asset.get("metadata") or {}).get("visual")
            return deepcopy(cached) if cached else analyze_image_path(path)
        if asset["type"] != "video":
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene visual analysis requires image or video", scene=scene_id, type=asset["type"])
        source_span = float(scene.get("duration", 0.0)) * float(scene.get("playback_rate", 1.0))
        return analyze_video_path(
            path, source_in=float(scene.get("source_in", 0.0)), source_span=source_span,
            duration=self._asset_duration(asset), sample_count=sample_count,
        )

    def suggest_composition(self, scene_id: str, *, text_hint: str = "", visual: dict | None = None) -> dict:
        scene = self._scene(scene_id)
        asset = self._asset(scene["asset_id"])
        video = self.project["video"]
        return plan_composition(asset, int(video["width"]), int(video["height"]), text_hint=text_hint, visual=visual)

    def set_composition(
        self, scene_id: str, *, mode: str = "cover", background: str = "black",
        frame_scale: float = 1.0, crop_zoom: float = 1.0, focus_x: float = 0.5, focus_y: float = 0.5,
        caption_zone: str = "bottom", focus_path: list[dict] | None = None,
        subject_bbox: list[float] | None = None, safe_zones: list[str] | None = None,
        visual_confidence: float | None = None, analysis_source: str | None = None,
    ) -> dict:
        raw = {
            "mode": mode, "background": background, "frame_scale": frame_scale, "crop_zoom": crop_zoom,
            "focus_x": focus_x, "focus_y": focus_y, "caption_zone": caption_zone,
            "focus_path": focus_path or [],
        }
        if subject_bbox is not None:
            raw["subject_bbox"] = subject_bbox
        if safe_zones is not None:
            raw["safe_zones"] = safe_zones
        if visual_confidence is not None:
            raw["visual_confidence"] = visual_confidence
        if analysis_source is not None:
            raw["analysis_source"] = analysis_source
        spec = validate_composition(raw)
        scene = self._scene(scene_id)
        scene["composition"] = spec
        self._commit(f"set_composition:{scene_id}:{mode}")
        return deepcopy(spec)

    @staticmethod
    def _composition_args_from_plan(plan: dict) -> dict:
        keys = {
            "mode", "background", "frame_scale", "crop_zoom", "focus_x", "focus_y", "caption_zone",
            "focus_path", "subject_bbox", "safe_zones", "visual_confidence", "analysis_source",
        }
        return {k: deepcopy(v) for k, v in plan.items() if k in keys}

    def apply_auto_composition(self, scene_id: str, *, text_hint: str = "") -> dict:
        plan = self.suggest_composition(scene_id, text_hint=text_hint)
        result = self.set_composition(scene_id, **self._composition_args_from_plan(plan))
        result["reason"] = plan.get("reason")
        return result

    def apply_visual_composition(self, scene_id: str, *, text_hint: str = "", sample_count: int = 3) -> dict:
        """Analyze the real scene content, then apply a focus-aware composition in one semantic edit."""
        visual = self.analyze_scene_visual(scene_id, sample_count=sample_count)
        plan = self.suggest_composition(scene_id, text_hint=text_hint, visual=visual)
        result = self.set_composition(scene_id, **self._composition_args_from_plan(plan))
        result["reason"] = plan.get("reason")
        result["visual"] = {
            "confidence": visual.get("confidence"), "movement": visual.get("movement", 0.0),
            "focus_x": visual.get("focus_x"), "focus_y": visual.get("focus_y"),
            "tracking_points": len(visual.get("focus_path") or []),
        }
        return result

    def auto_compose_scenes(
        self, scene_ids: list[str] | None = None, *, text_hints: dict[str, str] | None = None, sample_count: int = 3,
    ) -> dict:
        """Bulk practical workflow: analyze/reframe selected scenes and commit once."""
        ids = scene_ids or [s["id"] for s in self.project.get("scenes", [])]
        text_hints = text_hints or {}
        # Validate IDs before mutating anything.
        for sid in ids:
            self._scene(sid)
        was_batch = self._batch_mode
        self._batch_mode = True
        results = []
        try:
            for sid in ids:
                results.append({"scene_id": sid, "composition": self.apply_visual_composition(
                    sid, text_hint=str(text_hints.get(sid, "")), sample_count=sample_count
                )})
        finally:
            self._batch_mode = was_batch
        if not was_batch:
            validate_project(self.project)
            self._commit(f"auto_compose_scenes:{len(ids)}")
        return {"applied": len(results), "results": results}

    def set_cinematic_frame(
        self, scene_id: str, *, preset: str | None = None, frame_path: list[dict] | None = None,
        frame_easing: str = "smooth", treatment: str | None = None,
    ) -> dict:
        """Animate the visible cinematic frame without changing project canvas dimensions.

        The renderer moves physical black bars, so the image itself remains stable while the
        perceived aspect ratio can lock, reveal, or pulse within a shot.
        """
        scene = self._scene(scene_id)
        video = self.project["video"]
        canvas_aspect = float(video["width"]) / float(video["height"])
        if preset is not None and frame_path is not None:
            raise AgentCutError("INVALID_CINEMATIC_FRAME", "Provide either preset or frame_path, not both")
        if preset is not None:
            frame_path = preset_frame_path(str(preset), canvas_aspect=canvas_aspect)
            treatment = treatment or str(preset)
        spec = validate_cinematic({
            "frame_path": frame_path or [], "frame_easing": frame_easing,
            "treatment": treatment or (scene.get("cinematic") or {}).get("treatment"),
        }, canvas_aspect=canvas_aspect)
        scene["cinematic"] = spec
        self._commit(f"set_cinematic_frame:{scene_id}:{treatment or preset or 'custom'}")
        return deepcopy(spec)

    def clear_cinematic_frame(self, scene_id: str) -> dict:
        scene = self._scene(scene_id)
        removed = deepcopy(scene.pop("cinematic", None))
        self._commit(f"clear_cinematic_frame:{scene_id}")
        return {"scene_id": scene_id, "removed": removed}

    @staticmethod
    def _clamp_focus(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _unique_scene_id(self, base: str) -> str:
        used = {s.get("id") for s in self.project.get("scenes", [])}
        if base not in used:
            return base
        i = 2
        while f"{base}_{i}" in used:
            i += 1
        return f"{base}_{i}"

    def suggest_cinematic_treatment(self, scene_id: str, *, intent: str = "auto") -> dict:
        scene = self._scene(scene_id)
        if intent != "auto":
            allowed = set(FRAME_PRESETS) | set(FRAGMENT_STYLES)
            if intent not in allowed:
                raise AgentCutError("CINEMATIC_PRESET_NOT_FOUND", "Unknown cinematic intent", intent=intent, allowed=sorted(allowed))
            return {"scene_id": scene_id, "treatment": intent, "reason": "explicit_intent"}
        comp = scene.get("composition") or {}
        path = comp.get("focus_path") or []
        movement = 0.0
        if len(path) >= 2:
            xs = [float(x.get("x", comp.get("focus_x", 0.5))) for x in path]
            ys = [float(x.get("y", comp.get("focus_y", 0.5))) for x in path]
            movement = max(max(xs) - min(xs), max(ys) - min(ys))
        duration = float(scene.get("duration", 0.0))
        zoom = float(comp.get("crop_zoom", 1.0))
        if movement >= 0.16 and duration >= 0.9:
            return {"scene_id": scene_id, "treatment": "impact_cluster", "reason": "strong_subject_motion", "movement": round(movement, 4)}
        if zoom >= 1.18 or (comp.get("subject_bbox") and duration >= 0.8):
            return {"scene_id": scene_id, "treatment": "detail_burst", "reason": "detail_or_subject_emphasis"}
        if duration >= 3.0:
            return {"scene_id": scene_id, "treatment": "scope_lock", "reason": "long_shot_can_absorb_frame_change"}
        return {"scene_id": scene_id, "treatment": "impact_pulse", "reason": "short_shot_frame_pulse"}

    def fragment_scene(
        self, scene_id: str, *, style: str = "impact_cluster", count: int = 5,
        intensity: float = 0.75,
    ) -> dict:
        """Replace one visual scene with a duration-preserving micro-cut cluster.

        The first fragment keeps the original scene id. Interior fragments are hard cuts; the
        last fragment inherits the original outgoing transition. Complex scene-bound audio,
        layers, and dialogue are rejected rather than silently damaged.
        """
        scene = self._scene(scene_id)
        linked_dialogue = [x for x in self.project.get("dialogue_segments", []) if x.get("scene_id") == scene_id]
        if scene.get("audio") or scene.get("layers") or linked_dialogue:
            raise AgentCutError(
                "FRAGMENT_COMPLEX_SCENE",
                "Fragmentation currently requires a visual-only scene; move scene-bound audio/layers/dialogue first",
                scene=scene_id,
                scene_audio=len(scene.get("audio") or []), layers=len(scene.get("layers") or []), dialogue=len(linked_dialogue),
            )
        recipe = fragment_recipe(style, count=count, intensity=intensity)
        total_duration = float(scene["duration"])
        if total_duration < max(0.45, 0.08 * len(recipe)):
            raise AgentCutError("SCENE_TOO_SHORT_FOR_FRAGMENTATION", "Scene is too short for requested fragment cluster", scene=scene_id, duration=total_duration, count=len(recipe))
        video = self.project["video"]
        canvas_aspect = float(video["width"]) / float(video["height"])
        asset = self._asset(scene["asset_id"])
        asset_duration = self._asset_duration(asset)
        original = deepcopy(scene)
        original_transition = deepcopy(original.get("transition_out") or {"type": "cut", "duration": 0.0})
        base_comp = validate_composition(original.get("composition") or {})
        fx = float(base_comp.get("focus_x", 0.5)); fy = float(base_comp.get("focus_y", 0.5))
        rate = float(original.get("playback_rate", 1.0))
        original_source_in = float(original.get("source_in", 0.0))
        source_span = total_duration * rate
        group = f"{scene_id}:{uuid.uuid4().hex[:6]}"

        durations = [total_duration * float(row["duration_ratio"]) for row in recipe]
        durations[-1] += total_duration - sum(durations)
        fragments = []
        linear_source_cursor = 0.0
        for i, (row, duration) in enumerate(zip(recipe, durations)):
            frag = deepcopy(original)
            frag["id"] = scene_id if i == 0 else self._unique_scene_id(f"{scene_id}_f{i+1:02d}")
            frag["duration"] = round(float(duration), 6)
            comp = deepcopy(base_comp)
            comp["mode"] = "cover"
            comp["background"] = "black"
            comp["frame_scale"] = 1.0
            comp["focus_x"] = self._clamp_focus(fx + float(row.get("focus_dx", 0.0)))
            comp["focus_y"] = self._clamp_focus(fy + float(row.get("focus_dy", 0.0)))
            comp["crop_zoom"] = float(row.get("crop_zoom", 1.0))
            comp["focus_path"] = []
            frag["composition"] = validate_composition(comp)
            aspect = max(canvas_aspect, float(row.get("aspect", canvas_aspect)))
            frag["cinematic"] = validate_cinematic({
                "frame_path": [{"t": 0.0, "aspect": aspect}, {"t": 1.0, "aspect": aspect}],
                "frame_easing": "snap", "treatment": style,
                "fragment_group": group, "fragment_index": i + 1, "fragment_count": len(recipe),
            }, canvas_aspect=canvas_aspect)
            if i not in {0, len(recipe)-1}:
                frag["camera"] = {"type": "static", "amount": 0.0, "easing": "linear", "anchor": "center"}
            if asset.get("type") == "video":
                if style == "memory_shards":
                    desired = original_source_in + float(row.get("source_pos", 0.0)) * max(0.0, source_span - frag["duration"] * rate)
                else:
                    desired = original_source_in + linear_source_cursor
                    linear_source_cursor += frag["duration"] * rate
                if asset_duration is not None:
                    desired = min(desired, max(0.0, float(asset_duration) - frag["duration"] * rate))
                frag["source_in"] = max(0.0, round(desired, 6))
            frag["transition_out"] = original_transition if i == len(recipe)-1 else {"type": "cut", "duration": 0.0}
            fragments.append(frag)

        idx = next(i for i, row in enumerate(self.project["scenes"]) if row["id"] == scene_id)
        self.project["scenes"][idx:idx+1] = fragments
        validate_project(self.project)
        self._commit(f"fragment_scene:{scene_id}:{style}:{len(fragments)}")
        return {
            "scene_id": scene_id, "style": style, "fragment_group": group,
            "fragment_ids": [x["id"] for x in fragments],
            "durations": [x["duration"] for x in fragments],
            "total_duration": round(sum(float(x["duration"]) for x in fragments), 6),
        }

    def apply_cinematic_treatment(
        self, scene_id: str, *, style: str = "auto", intensity: float = 0.75, count: int = 5,
    ) -> dict:
        plan = self.suggest_cinematic_treatment(scene_id, intent=style)
        treatment = plan["treatment"]
        if treatment in FRAGMENT_STYLES:
            result = self.fragment_scene(scene_id, style=treatment, count=count, intensity=intensity)
        else:
            result = self.set_cinematic_frame(scene_id, preset=treatment, treatment=treatment)
        return {"plan": plan, "result": result}

    def suggest_caption_zone(self, scene_id: str, *, text: str = "") -> str:
        scene = self._scene(scene_id)
        comp = scene.get("composition") or {}
        # If visual analysis supplied multiple safe zones, recalculate with text length so long
        # dialogue favors broad top/bottom regions while short titles can use corners.
        asset = self._asset(scene["asset_id"])
        visual = (asset.get("metadata") or {}).get("visual") or {}
        if visual:
            return choose_caption_zone(visual, text_length=len(text))
        if comp.get("caption_zone") in CAPTION_POSITIONS:
            return str(comp["caption_zone"])
        tags = asset.get("tags") or {}
        try:
            fx, fy = float(tags.get("focus_x", 0.5)), float(tags.get("focus_y", 0.5))
        except (TypeError, ValueError):
            fx, fy = 0.5, 0.5
        return caption_zone_for_focus(fx, fy, text_length=len(text))

    def analyze_audio_rhythm(self, asset_id: str) -> dict:
        asset = self._asset(asset_id)
        if asset["type"] != "audio":
            raise AgentCutError("INVALID_ASSET_TYPE", "Rhythm analysis requires audio asset", asset_id=asset_id, type=asset["type"])
        path = Path(asset["path"])
        path = path if path.is_absolute() else self.root / path
        analysis = analyze_audio_rhythm_file(path)
        asset.setdefault("metadata", {})["rhythm"] = deepcopy(analysis)
        self._commit(f"analyze_audio_rhythm:{asset_id}")
        return deepcopy(analysis)

    def _rhythm_analysis(self, asset_id: str) -> dict:
        asset = self._asset(asset_id)
        if asset["type"] != "audio":
            raise AgentCutError("INVALID_ASSET_TYPE", "Rhythm planning requires audio asset", asset_id=asset_id, type=asset["type"])
        analysis = (asset.get("metadata") or {}).get("rhythm")
        return deepcopy(analysis) if analysis else self.analyze_audio_rhythm(asset_id)

    def suggest_rhythm_cuts(self, asset_id: str, *, include_onsets: bool = True, min_gap: float = 0.16) -> list[float]:
        return suggest_cut_points(self._rhythm_analysis(asset_id), include_onsets=include_onsets, min_gap=min_gap)

    def rhythm_plan(
        self, scene_ids: list[str], asset_id: str, *, minimum_scene_duration: float = 0.35,
        snap_window: float = 0.22,
    ) -> dict:
        if not scene_ids:
            raise AgentCutError("INVALID_RHYTHM_PLAN", "scene_ids cannot be empty")
        scenes = [self._scene(sid) for sid in scene_ids]
        cuts = self.suggest_rhythm_cuts(asset_id)
        starts = [0.0]
        cursor = 0.0
        for i, scene in enumerate(scenes[:-1]):
            cursor += float(scene["duration"])
            tr = scene.get("transition_out") or {"type": "cut", "duration": 0.0}
            if tr.get("type") != "cut":
                cursor -= max(0.0, float(tr.get("duration", 0.0)))
            candidates = [c for c in cuts if abs(c - cursor) <= snap_window and c - starts[-1] >= minimum_scene_duration]
            snapped = min(candidates, key=lambda c: abs(c - cursor)) if candidates else cursor
            starts.append(round(float(snapped), 6))
        durations = []
        for i, scene in enumerate(scenes):
            if i + 1 < len(scenes):
                tr = scene.get("transition_out") or {"type": "cut", "duration": 0.0}
                overlap = 0.0 if tr.get("type") == "cut" else max(0.0, float(tr.get("duration", 0.0)))
                duration = (starts[i + 1] - starts[i]) + overlap
            else:
                duration = float(scene["duration"])
            durations.append(max(minimum_scene_duration, round(float(duration), 6)))
        return {
            "audio_asset_id": asset_id, "scene_ids": list(scene_ids), "starts": starts,
            "durations": durations, "minimum_scene_duration": minimum_scene_duration,
            "snap_window": snap_window,
        }

    def apply_rhythm_plan(self, plan: dict) -> dict:
        scene_ids = list(plan.get("scene_ids") or [])
        durations = list(plan.get("durations") or [])
        if len(scene_ids) != len(durations) or not scene_ids:
            raise AgentCutError("INVALID_RHYTHM_PLAN", "Plan must contain equally sized scene_ids and durations")
        before = deepcopy(self.project)
        self._batch_mode = True
        try:
            for sid, dur in zip(scene_ids, durations):
                self.set_duration(sid, float(dur))
            validate_project(self.project)
            self._batch_mode = False
            save_project(self.root, self.project)
            self.history.commit(f"apply_rhythm_plan:{len(scene_ids)}", self.project)
        except Exception:
            self._batch_mode = False
            self.project = before
            save_project(self.root, self.project)
            raise
        return {"applied": len(scene_ids), "durations": durations, "timeline": self.get_timeline()}

    def add_effect(self, scene_id: str, effect: str, *, intensity: float = 0.2, speed: float = 1.0, direction: str = "auto", opacity: float = 0.6, depth: str = "foreground", seed: int = 1) -> dict:
        allowed = set(CAPABILITIES["environment"])
        preset_id = None
        if effect not in allowed:
            try:
                preset = library_get_item("effects", effect)
            except AgentCutError:
                raise AgentCutError("UNSUPPORTED_EFFECT", "Unsupported environment effect", effect=effect, allowed=sorted(allowed), recovery="Use a backend effect name or any effect Library preset ID.")
            preset_id = str(effect)
            defaults = deepcopy(preset.get("defaults", {}))
            effect = str(preset.get("backend"))
            if effect not in allowed:
                raise AgentCutError("UNSUPPORTED_EFFECT", "Effect preset resolves to an unsupported backend", preset_id=preset_id, backend=effect, allowed=sorted(allowed))
            # Caller defaults mean 'use preset' when omitted; explicit non-default values still win.
            if intensity == 0.2: intensity = float(defaults.get("intensity", intensity))
            if speed == 1.0: speed = float(defaults.get("speed", speed))
            if direction == "auto": direction = str(defaults.get("direction", direction))
            if opacity == 0.6: opacity = float(defaults.get("opacity", opacity))
            if depth == "foreground": depth = str(defaults.get("depth", depth))
        intensity = _finite(intensity, field="effect.intensity")
        speed = _finite(speed, field="effect.speed")
        opacity = _finite(opacity, field="effect.opacity")
        if not (0 <= intensity <= 1) or not (0 <= opacity <= 1):
            raise AgentCutError("INVALID_EFFECT", "intensity and opacity must be in [0,1]", intensity=intensity, opacity=opacity)
        if speed <= 0 or speed > 8:
            raise AgentCutError("INVALID_EFFECT_SPEED", "effect speed must be in (0, 8]", speed=speed)
        if direction not in DIRECTIONS:
            raise AgentCutError("UNSUPPORTED_DIRECTION", "Unsupported effect direction", direction=direction, allowed=sorted(DIRECTIONS))
        if depth not in DEPTHS:
            raise AgentCutError("UNSUPPORTED_DEPTH", "Unsupported depth hint", depth=depth, allowed=sorted(DEPTHS))
        scene = self._scene(scene_id)
        entry = {
            "type": effect,
            "intensity": intensity,
            "speed": speed,
            "direction": direction,
            "opacity": opacity,
            "depth": depth,
            "seed": int(seed),
        }
        if preset_id:
            entry["preset_id"] = preset_id
        scene["effects"].append(entry)
        self._commit(f"add_effect:{scene_id}:{preset_id or effect}")
        return deepcopy(entry)

    def apply_effect_preset(self, scene_id: str, preset_id: str, *, overrides: dict | None = None, seed: int | None = None) -> dict:
        preset = library_get_item("effects", preset_id)
        defaults = deepcopy(preset.get("defaults", {}))
        if overrides:
            defaults.update(overrides)
        backend = str(preset.get("backend"))
        material = defaults.pop("material", None)
        entry = self.add_effect(
            scene_id, backend,
            intensity=float(defaults.pop("intensity", 0.2)),
            speed=float(defaults.pop("speed", 1.0)),
            direction=str(defaults.pop("direction", "auto")),
            opacity=float(defaults.pop("opacity", 0.6)),
            depth=str(defaults.pop("depth", "foreground")),
            seed=int(seed if seed is not None else defaults.pop("seed", 1)),
        )
        scene = self._scene(scene_id)
        scene["effects"][-1]["preset_id"] = preset_id
        if material:
            scene["effects"][-1]["material"] = material
        for key, value in defaults.items():
            scene["effects"][-1][key] = value
        self._commit(f"apply_effect_preset:{scene_id}:{preset_id}")
        return deepcopy(scene["effects"][-1])

    def add_filter(self, scene_id: str, filter_id: str) -> list[str]:
        library_get_item("filters", filter_id)
        scene = self._scene(scene_id)
        scene.setdefault("filters", []).append(filter_id)
        self._commit(f"add_filter:{scene_id}:{filter_id}")
        return deepcopy(scene["filters"])

    def clear_filters(self, scene_id: str) -> dict:
        scene = self._scene(scene_id)
        scene["filters"] = []
        self._commit(f"clear_filters:{scene_id}")
        return {"scene_id": scene_id, "filters": []}

    def apply_motion_preset(self, scene_id: str, preset_id: str, *, overrides: dict | None = None) -> dict:
        preset = library_get_item("motions", preset_id)
        params = deepcopy(preset.get("defaults", {}))
        if overrides:
            params.update(overrides)
        if not params:
            return self.set_camera(scene_id, motion="static", amount=0.0)
        return self.set_camera(
            scene_id,
            motion=str(params.get("motion", "static")),
            amount=float(params.get("amount", 0.0)),
            easing=str(params.get("easing", "linear")),
            anchor=str(params.get("anchor", "center")),
        )

    def apply_transition_preset(self, scene_id: str, preset_id: str, *, duration: float | None = None) -> dict:
        preset = library_get_item("transitions", preset_id)
        defaults = preset.get("defaults", {})
        dur = float(defaults.get("duration", 0.35) if duration is None else duration)
        return self.set_transition(scene_id, preset_id, dur)

    def remove_effect(self, scene_id: str, index: int) -> dict:
        scene = self._scene(scene_id)
        try:
            removed = scene["effects"].pop(index)
        except IndexError as exc:
            raise AgentCutError("INVALID_INDEX", "Effect index out of range", scene=scene_id, index=index) from exc
        self._commit(f"remove_effect:{scene_id}:{index}")
        return deepcopy(removed)

    def clear_effects(self, scene_id: str) -> dict:
        self._scene(scene_id)["effects"] = []
        self._commit(f"clear_effects:{scene_id}")
        return {"scene_id": scene_id, "effects": []}

    def set_transition(self, scene_id: str, transition: str, duration: float = 0.35) -> dict:
        allowed = set(CAPABILITIES["transitions"])
        if transition not in allowed:
            raise AgentCutError("UNSUPPORTED_TRANSITION", "Unsupported transition", transition=transition, allowed=sorted(allowed))
        duration = _finite(duration, field="transition.duration")
        if transition == "cut":
            duration = 0.0
        elif duration <= 0:
            raise AgentCutError("INVALID_TRANSITION", "Non-cut transition duration must be > 0", duration=duration)
        scene = self._scene(scene_id)
        existing_sfx = (scene.get("transition_out") or {}).get("sfx")
        scene["transition_out"] = {"type": transition, "duration": duration}
        if existing_sfx is not None:
            scene["transition_out"]["sfx"] = existing_sfx
        self._commit(f"set_transition:{scene_id}:{transition}")
        return deepcopy(scene["transition_out"])

    def set_transition_event(
        self,
        scene_id: str,
        transition: str,
        duration: float = 0.35,
        *,
        sfx_asset_id: str | None = None,
        sfx_volume_db: float = -12.0,
        sfx_offset: float = 0.0,
        sfx_fade_in: float = 0.0,
        sfx_fade_out: float = 0.08,
    ) -> dict:
        """Bind the visual transition and its whoosh/impact as one semantic event."""
        allowed = set(CAPABILITIES["transitions"])
        if transition not in allowed:
            raise AgentCutError("UNSUPPORTED_TRANSITION", "Unsupported transition", transition=transition, allowed=sorted(allowed))
        duration = _finite(duration, field="transition.duration")
        if transition == "cut":
            duration = 0.0
        elif duration <= 0:
            raise AgentCutError("INVALID_TRANSITION", "Non-cut transition duration must be > 0", duration=duration)
        event = {"type": transition, "duration": duration}
        if sfx_asset_id is not None:
            asset = self._asset(sfx_asset_id)
            if asset["type"] != "audio":
                raise AgentCutError("INVALID_ASSET_TYPE", "Transition SFX requires audio asset", asset_id=sfx_asset_id, type=asset["type"])
            sfx_volume_db = _finite(sfx_volume_db, field="transition.sfx.volume_db")
            sfx_offset = _finite(sfx_offset, field="transition.sfx.offset")
            sfx_fade_in = _finite(sfx_fade_in, field="transition.sfx.fade_in")
            sfx_fade_out = _finite(sfx_fade_out, field="transition.sfx.fade_out")
            if sfx_fade_in < 0 or sfx_fade_out < 0:
                raise AgentCutError("INVALID_AUDIO_TIME", "Transition SFX fades must be >= 0")
            event["sfx"] = {
                "asset_id": sfx_asset_id,
                "volume_db": sfx_volume_db,
                "offset": sfx_offset,
                "fade_in": sfx_fade_in,
                "fade_out": sfx_fade_out,
            }
        scene = self._scene(scene_id)
        scene["transition_out"] = event
        self._commit(f"set_transition_event:{scene_id}:{transition}")
        return deepcopy(event)

    def clear_transition_sfx(self, scene_id: str) -> dict:
        scene = self._scene(scene_id)
        tr = scene.get("transition_out") or {"type": "cut", "duration": 0.0}
        tr.pop("sfx", None)
        scene["transition_out"] = tr
        self._commit(f"clear_transition_sfx:{scene_id}")
        return deepcopy(tr)

    def _validate_audio(self, *, kind: str, volume_db: float, start: float, duration: float | None, fade_in: float, fade_out: float) -> tuple:
        if kind not in AUDIO_KINDS:
            raise AgentCutError("INVALID_AUDIO_KIND", "Unsupported audio kind", kind=kind, allowed=sorted(AUDIO_KINDS))
        volume_db = _finite(volume_db, field="audio.volume_db")
        start = _finite(start, field="audio.start")
        fade_in = _finite(fade_in, field="audio.fade_in")
        fade_out = _finite(fade_out, field="audio.fade_out")
        if start < 0 or fade_in < 0 or fade_out < 0:
            raise AgentCutError("INVALID_AUDIO_TIME", "Audio start/fades must be >= 0", start=start, fade_in=fade_in, fade_out=fade_out)
        if volume_db < -120 or volume_db > 24:
            raise AgentCutError("INVALID_AUDIO_VOLUME", "volume_db must be in [-120, 24]", volume_db=volume_db)
        if duration is not None:
            duration = _finite(duration, field="audio.duration")
            if duration <= 0:
                raise AgentCutError("INVALID_AUDIO_DURATION", "Audio duration must be > 0", duration=duration)
        return kind, volume_db, start, duration, fade_in, fade_out

    def add_scene_audio(self, scene_id: str, asset_id: str, *, kind="ambience", volume_db=-18.0, start=0.0, duration: float | None = None, fade_in=0.2, fade_out=0.2, loop=False) -> dict:
        asset = self._asset(asset_id)
        if asset["type"] != "audio":
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene audio requires audio asset", asset_id=asset_id, type=asset["type"])
        kind, volume_db, start, duration, fade_in, fade_out = self._validate_audio(kind=kind, volume_db=volume_db, start=start, duration=duration, fade_in=fade_in, fade_out=fade_out)
        scene = self._scene(scene_id)
        if start >= float(scene["duration"]):
            raise AgentCutError("AUDIO_OUTSIDE_SCENE", "Scene audio must start before the scene ends", scene=scene_id, start=start)
        if duration is not None and start + duration > float(scene["duration"]) + 1e-9:
            raise AgentCutError("AUDIO_OUTSIDE_SCENE", "Explicit scene audio duration extends past scene end", scene=scene_id, start=start, duration=duration)
        track = {
            "id": f"scene_track_{uuid.uuid4().hex[:8]}",
            "asset_id": asset_id, "kind": kind, "volume_db": volume_db, "start": start,
            "duration": duration, "fade_in": fade_in, "fade_out": fade_out, "loop": bool(loop)
        }
        scene["audio"].append(track)
        self._commit(f"add_scene_audio:{scene_id}:{track['id']}")
        return deepcopy(track)

    def remove_scene_audio(self, scene_id: str, track_id: str) -> dict:
        scene = self._scene(scene_id)
        idx = next((i for i, t in enumerate(scene.get("audio", [])) if t.get("id") == track_id), None)
        if idx is None:
            raise AgentCutError("AUDIO_TRACK_NOT_FOUND", "Unknown scene audio track", scene=scene_id, track_id=track_id)
        removed = scene["audio"].pop(idx)
        self._commit(f"remove_scene_audio:{scene_id}:{track_id}")
        return deepcopy(removed)

    def update_scene_audio(self, scene_id: str, track_id: str, **changes) -> dict:
        scene = self._scene(scene_id)
        track = next((t for t in scene.get("audio", []) if t.get("id") == track_id), None)
        if track is None:
            raise AgentCutError("AUDIO_TRACK_NOT_FOUND", "Unknown scene audio track", scene=scene_id, track_id=track_id)
        allowed = {"asset_id", "kind", "volume_db", "start", "duration", "fade_in", "fade_out", "loop"}
        unknown = set(changes) - allowed
        if unknown:
            raise AgentCutError("INVALID_OPERATION", "Unsupported scene audio fields", fields=sorted(unknown), allowed=sorted(allowed))
        candidate = dict(track); candidate.update(changes)
        asset = self._asset(candidate["asset_id"])
        if asset["type"] != "audio":
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene audio requires audio asset", asset_id=candidate["asset_id"], type=asset["type"])
        kind, volume_db, start, duration, fade_in, fade_out = self._validate_audio(
            kind=candidate.get("kind", "ambience"), volume_db=candidate.get("volume_db", -18),
            start=candidate.get("start", 0), duration=candidate.get("duration"),
            fade_in=candidate.get("fade_in", 0.2), fade_out=candidate.get("fade_out", 0.2))
        if start >= float(scene["duration"]) or (duration is not None and start + duration > float(scene["duration"]) + 1e-9):
            raise AgentCutError("AUDIO_OUTSIDE_SCENE", "Updated scene audio extends outside scene", scene=scene_id, start=start, duration=duration)
        candidate.update({"kind": kind, "volume_db": volume_db, "start": start, "duration": duration, "fade_in": fade_in, "fade_out": fade_out, "loop": bool(candidate.get("loop", False))})
        track.clear(); track.update(candidate)
        self._commit(f"update_scene_audio:{scene_id}:{track_id}")
        return deepcopy(track)

    def add_audio_track(self, asset_id: str, *, kind="bgm", volume_db=-20.0, start=0.0, duration: float | None = None, fade_in=0.5, fade_out=0.5, loop=False) -> dict:
        asset = self._asset(asset_id)
        if asset["type"] != "audio":
            raise AgentCutError("INVALID_ASSET_TYPE", "Global audio track requires audio asset", asset_id=asset_id, type=asset["type"])
        kind, volume_db, start, duration, fade_in, fade_out = self._validate_audio(kind=kind, volume_db=volume_db, start=start, duration=duration, fade_in=fade_in, fade_out=fade_out)
        track = {
            "id": f"track_{uuid.uuid4().hex[:8]}", "asset_id": asset_id, "kind": kind,
            "volume_db": volume_db, "start": start, "duration": duration,
            "fade_in": fade_in, "fade_out": fade_out, "loop": bool(loop)
        }
        self.project["audio_tracks"].append(track)
        self._commit(f"add_audio_track:{track['id']}")
        return deepcopy(track)

    def remove_audio_track(self, track_id: str) -> dict:
        idx = next((i for i, t in enumerate(self.project.get("audio_tracks", [])) if t.get("id") == track_id), None)
        if idx is None:
            raise AgentCutError("AUDIO_TRACK_NOT_FOUND", "Unknown global audio track", track_id=track_id)
        removed = self.project["audio_tracks"].pop(idx)
        self._commit(f"remove_audio_track:{track_id}")
        return deepcopy(removed)

    def update_audio_track(self, track_id: str, **changes) -> dict:
        track = next((t for t in self.project.get("audio_tracks", []) if t.get("id") == track_id), None)
        if track is None:
            raise AgentCutError("AUDIO_TRACK_NOT_FOUND", "Unknown global audio track", track_id=track_id)
        allowed = {"asset_id", "kind", "volume_db", "start", "duration", "fade_in", "fade_out", "loop"}
        unknown = set(changes) - allowed
        if unknown:
            raise AgentCutError("INVALID_OPERATION", "Unsupported global audio fields", fields=sorted(unknown), allowed=sorted(allowed))
        candidate = dict(track); candidate.update(changes)
        asset = self._asset(candidate["asset_id"])
        if asset["type"] != "audio":
            raise AgentCutError("INVALID_ASSET_TYPE", "Global audio track requires audio asset", asset_id=candidate["asset_id"], type=asset["type"])
        kind, volume_db, start, duration, fade_in, fade_out = self._validate_audio(
            kind=candidate.get("kind", "bgm"), volume_db=candidate.get("volume_db", -20),
            start=candidate.get("start", 0), duration=candidate.get("duration"),
            fade_in=candidate.get("fade_in", 0.5), fade_out=candidate.get("fade_out", 0.5))
        candidate.update({"kind": kind, "volume_db": volume_db, "start": start, "duration": duration, "fade_in": fade_in, "fade_out": fade_out, "loop": bool(candidate.get("loop", False))})
        track.clear(); track.update(candidate)
        self._commit(f"update_audio_track:{track_id}")
        return deepcopy(track)

    def add_caption(
        self, text: str, start: float, end: float, *, speaker: str | None = None, position="bottom",
        font_size=54, outline=3, subtitle_style: str = "default", secondary_text: str | None = None,
        secondary_language: str = "en", secondary_font_scale: float = 0.72,
        max_line_chars: int | None = None, secondary_max_line_chars: int | None = None, auto_fit: bool = True,
    ) -> dict:
        start = _finite(start, field="caption.start")
        end = _finite(end, field="caption.end")
        text = str(text)
        if not text.strip():
            raise AgentCutError("INVALID_CAPTION", "Caption text cannot be empty")
        if start < 0 or end <= start:
            raise AgentCutError("INVALID_CAPTION_TIME", "Caption must satisfy 0 <= start < end", start=start, end=end)
        if position not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_CAPTION_POSITION", "Unsupported caption position", position=position, allowed=sorted(CAPTION_POSITIONS))
        if int(font_size) <= 0 or int(outline) < 0:
            raise AgentCutError("INVALID_CAPTION_STYLE", "font_size must be > 0 and outline >= 0", font_size=font_size, outline=outline)
        subtitle_style = str(subtitle_style or "default").strip().lower()
        if subtitle_style not in DIALOGUE_STYLES:
            raise AgentCutError("INVALID_CAPTION_STYLE", "Unknown subtitle style", style=subtitle_style, allowed=sorted(DIALOGUE_STYLES))
        scale = _finite(secondary_font_scale, field="caption.secondary_font_scale")
        if scale <= 0 or scale > 1.5:
            raise AgentCutError("INVALID_CAPTION_STYLE", "secondary_font_scale must be in (0,1.5]", secondary_font_scale=scale)
        secondary = str(secondary_text).strip() if secondary_text is not None else None
        if secondary_text is not None and not secondary:
            raise AgentCutError("INVALID_CAPTION", "secondary_text cannot be blank when provided")
        layout = fit_subtitle_layout(text, secondary, end - start, font_size=int(font_size), secondary_font_scale=scale) if auto_fit else {}
        caption = {
            "id": f"caption_{uuid.uuid4().hex[:8]}", "text": text, "start": start, "end": end,
            "speaker": speaker, "position": position, "font_size": int(layout.get("font_size", font_size)), "outline": int(outline),
            "subtitle_style": subtitle_style, "secondary_text": secondary,
            "secondary_language": str(secondary_language or "en"), "secondary_font_scale": float(layout.get("secondary_font_scale", scale)),
            "max_line_chars": int(max_line_chars) if max_line_chars is not None else layout.get("max_line_chars"),
            "secondary_max_line_chars": int(secondary_max_line_chars) if secondary_max_line_chars is not None else layout.get("secondary_max_line_chars"),
            "layout_auto_fit": bool(auto_fit), "layout_density": layout.get("layout_density"), "layout_level": layout.get("layout_level"),
        }
        self.project["captions"].append(caption)
        self._commit(f"add_caption:{caption['id']}")
        return deepcopy(caption)

    def update_caption(self, caption_id: str, **changes) -> dict:
        cap = next((c for c in self.project.get("captions", []) if c.get("id") == caption_id), None)
        if cap is None:
            raise AgentCutError("CAPTION_NOT_FOUND", "Unknown caption", caption_id=caption_id)
        allowed = {"text", "start", "end", "speaker", "position", "font_size", "outline", "subtitle_style", "secondary_text", "secondary_language", "secondary_font_scale", "max_line_chars", "secondary_max_line_chars", "layout_auto_fit", "layout_density", "layout_level"}
        unknown = set(changes) - allowed
        if unknown:
            raise AgentCutError("INVALID_OPERATION", "Unsupported caption fields", fields=sorted(unknown), allowed=sorted(allowed))
        candidate = dict(cap)
        candidate.update(changes)
        text = str(candidate.get("text", ""))
        start = _finite(candidate.get("start", 0), field="caption.start")
        end = _finite(candidate.get("end", 0), field="caption.end")
        if not text.strip() or start < 0 or end <= start:
            raise AgentCutError("INVALID_CAPTION", "Caption text/time is invalid", caption_id=caption_id)
        if candidate.get("position", "bottom") not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_CAPTION_POSITION", "Unsupported caption position", position=candidate.get("position"))
        if int(candidate.get("font_size", 54)) <= 0 or int(candidate.get("outline", 3)) < 0:
            raise AgentCutError("INVALID_CAPTION_STYLE", "Invalid caption style", caption_id=caption_id)
        style = str(candidate.get("subtitle_style", "default")).strip().lower()
        if style not in DIALOGUE_STYLES:
            raise AgentCutError("INVALID_CAPTION_STYLE", "Unknown subtitle style", style=style, allowed=sorted(DIALOGUE_STYLES))
        candidate["subtitle_style"] = style
        scale = _finite(candidate.get("secondary_font_scale", 0.72), field="caption.secondary_font_scale")
        if scale <= 0 or scale > 1.5:
            raise AgentCutError("INVALID_CAPTION_STYLE", "secondary_font_scale must be in (0,1.5]", secondary_font_scale=scale)
        candidate["secondary_font_scale"] = scale
        for field_name in ("max_line_chars", "secondary_max_line_chars"):
            value = candidate.get(field_name)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 8 or value > 100):
                raise AgentCutError("INVALID_CAPTION_STYLE", f"{field_name} must be an integer in [8,100]", field=field_name, value=value)
        if candidate.get("secondary_text") is not None:
            candidate["secondary_text"] = str(candidate.get("secondary_text")).strip()
            if not candidate["secondary_text"]:
                raise AgentCutError("INVALID_CAPTION", "secondary_text cannot be blank when provided")
        cap.update(candidate)
        cap["text"], cap["start"], cap["end"] = text, start, end
        cap["font_size"], cap["outline"] = int(cap.get("font_size", 54)), int(cap.get("outline", 3))
        self._commit(f"update_caption:{caption_id}")
        return deepcopy(cap)

    def remove_caption(self, caption_id: str) -> dict:
        idx = next((i for i, c in enumerate(self.project.get("captions", [])) if c.get("id") == caption_id), None)
        if idx is None:
            raise AgentCutError("CAPTION_NOT_FOUND", "Unknown caption", caption_id=caption_id)
        removed = self.project["captions"].pop(idx)
        self._commit(f"remove_caption:{caption_id}")
        return deepcopy(removed)

    def subtitle_status(self) -> dict:
        return {"styles": sorted(DIALOGUE_STYLES), "asr": asr_status(), "bilingual": True}

    def import_subtitle_file(
        self, path: str | Path, *, subtitle_style: str = "default", position: str = "bottom",
        speaker: str | None = None, offset: float = 0.0, secondary_language: str = "en",
        parse_speakers: bool = True, strip_speaker_prefix: bool = True, infer_styles: bool = True,
        secondary_path: str | Path | None = None, smart_position: bool = True, auto_fit: bool = True,
    ) -> dict:
        """Import SRT with optional Cast-aware speaker parsing and bilingual alignment.

        A prefix is only treated as a speaker when it resolves to an existing Cast entry,
        so ordinary prose containing a colon remains untouched.
        """
        src = Path(path).expanduser().resolve()
        if src.suffix.lower() != ".srt":
            raise AgentCutError("SUBTITLE_FORMAT_UNSUPPORTED", "3.2 subtitle import currently accepts SRT", path=str(src), supported=["srt"])
        rows = parse_srt(src)
        secondary_rows = []
        secondary_src = None
        if secondary_path is not None:
            secondary_src = Path(secondary_path).expanduser().resolve()
            if secondary_src.suffix.lower() != ".srt":
                raise AgentCutError("SUBTITLE_FORMAT_UNSUPPORTED", "Secondary subtitle file must be SRT", path=str(secondary_src), supported=["srt"])
            secondary_rows = parse_srt(secondary_src)
        secondary_texts = align_secondary(rows, secondary_rows) if secondary_rows else [None] * len(rows)
        timeline = build_timeline(self.project)
        scene_windows = [(x["scene_id"], float(x["start"]), float(x["end"])) for x in timeline.get("scenes", [])]
        cast = self.project.get("cast", {})
        old_batch = self._batch_mode
        old = deepcopy(self.project)
        created = []; recognized = 0; styled = 0; bilingual_count = 0
        try:
            self._batch_mode = True
            for row, secondary in zip(rows, secondary_texts):
                raw_text = row["text"]
                chosen_speaker = speaker
                character_id = None
                body = raw_text
                if parse_speakers and speaker is None:
                    candidate, candidate_body = split_speaker_prefix(raw_text)
                    if candidate:
                        cid, character = resolve_character(cast, speaker=candidate)
                        if character:
                            character_id = cid
                            chosen_speaker = character.get("display_name") or candidate
                            if strip_speaker_prefix:
                                body = candidate_body
                            recognized += 1
                chosen_style = str(subtitle_style or "default")
                if infer_styles and chosen_style == "default":
                    inferred = infer_subtitle_style(body, has_speaker=bool(chosen_speaker))
                    if inferred != chosen_style:
                        styled += 1
                    chosen_style = inferred
                chosen_position = position
                if smart_position and chosen_speaker and position == "bottom":
                    absolute_start = float(row["start"]) + float(offset)
                    scene_id = next((sid for sid, a, b in scene_windows if a - 1e-6 <= absolute_start < b + 1e-6), None)
                    if scene_id and character_id:
                        scene_cast = self._effective_cast(scene_id)
                        char = scene_cast.get(character_id) or {}
                        pref = char.get("subtitle_position", "auto")
                        if pref != "auto":
                            chosen_position = pref
                        else:
                            chosen_position = caption_zone_for_focus(float(char.get("focus_x", .5)), float(char.get("focus_y", .5)), text_length=len(body))
                cap = self.add_caption(
                    body, row["start"] + float(offset), row["end"] + float(offset),
                    speaker=chosen_speaker, position=chosen_position, subtitle_style=chosen_style,
                    secondary_text=secondary, secondary_language=secondary_language, auto_fit=auto_fit,
                )
                stored = next(c for c in self.project["captions"] if c.get("id") == cap["id"])
                if character_id:
                    stored["character_id"] = character_id
                if secondary:
                    bilingual_count += 1
                    if subtitle_style == "bilingual":
                        stored["subtitle_style"] = "bilingual"
                created.append(cap["id"])
            validate_project(self.project)
        except Exception:
            self.project = old; self._batch_mode = old_batch; raise
        self._batch_mode = old_batch
        self._commit(f"import_subtitle_file:{len(created)}")
        return {
            "count": len(created), "caption_ids": created, "source": str(src),
            "recognized_speakers": recognized, "inferred_styles": styled,
            "bilingual_count": bilingual_count, "secondary_source": str(secondary_src) if secondary_src else None,
        }

    def auto_subtitles(
        self, asset_id: str, *, language: str = "auto", model: str | None = None, bilingual: bool = False,
        translate_to: str = "en", subtitle_style: str = "bilingual", position: str = "bottom",
        speaker: str | None = None, offset: float = 0.0, max_segments: int | None = None,
        replace_existing: bool = True, use_cache: bool = True, auto_fit: bool = True,
    ) -> dict:
        asset = self._asset(asset_id)
        if asset.get("type") not in {"audio", "video"}:
            raise AgentCutError("INVALID_ASSET_TYPE", "Automatic subtitles require an audio or video asset", asset_id=asset_id, type=asset.get("type"))
        if max_segments is not None and int(max_segments) <= 0:
            raise AgentCutError("INVALID_ASR_LIMIT", "max_segments must be > 0 when provided", max_segments=max_segments)
        source = self._asset_path(asset_id)
        status = asr_status()
        asr_fingerprint = {
            "asset_sha256": asset.get("sha256"), "language": language, "model": str(model or status.get("model")),
            "executable": str(status.get("executable")),
        }
        def run_cached(*, translated: bool):
            key = hash_obj({**asr_fingerprint, "translated_to_english": translated})[:20]
            cache_path = self.root / "cache" / f"asr_{key}.json"
            if use_cache and cache_path.exists():
                try:
                    value = json_load(cache_path)
                    if isinstance(value, dict) and value.get("segments"):
                        return value, True
                except Exception:
                    pass
            value = transcribe_media(source, model=model, language=language, translate_to_english=translated)
            if use_cache:
                json_dump(cache_path, value)
            return value, False

        primary, primary_cache_hit = run_cached(translated=False)
        segments = primary["segments"][: int(max_segments)] if max_segments is not None else primary["segments"]
        secondary = [None] * len(segments)
        translation_result = None; translation_cache_hit = False
        if bilingual:
            target = str(translate_to or "en").lower()
            if target not in {"en", "english"}:
                raise AgentCutError("ASR_TRANSLATION_UNSUPPORTED", "whisper.cpp automatic translation currently targets English only", requested=translate_to)
            translation_result, translation_cache_hit = run_cached(translated=True)
            secondary = align_secondary(segments, translation_result["segments"])
        old = deepcopy(self.project); old_batch = self._batch_mode; created = []
        try:
            self._batch_mode = True
            if replace_existing:
                self.project["captions"] = [c for c in self.project.get("captions", []) if not (c.get("generated_by") == "asr" and c.get("source_asset_id") == asset_id)]
            for row, translation in zip(segments, secondary):
                cap = self.add_caption(
                    row["text"], float(row["start"]) + float(offset), float(row["end"]) + float(offset),
                    speaker=speaker, position=position, subtitle_style=(subtitle_style if bilingual else ("default" if subtitle_style == "bilingual" else subtitle_style)),
                    secondary_text=translation, secondary_language="en", secondary_font_scale=0.70, auto_fit=auto_fit,
                )
                # Provenance makes repeated low-cognition recipes idempotent without changing manual captions.
                stored = next(c for c in self.project["captions"] if c.get("id") == cap["id"])
                stored["generated_by"] = "asr"; stored["source_asset_id"] = asset_id
                created.append(cap["id"])
            validate_project(self.project)
        except Exception:
            self.project = old; self._batch_mode = old_batch; raise
        self._batch_mode = old_batch
        self._commit(f"auto_subtitles:{asset_id}:{len(created)}")
        return {
            "asset_id": asset_id, "backend": primary.get("backend"), "language": primary.get("language"),
            "bilingual": bool(bilingual), "translation_backend": translation_result.get("backend") if translation_result else None,
            "caption_ids": created, "count": len(created), "replaced_previous": bool(replace_existing),
            "cache": {"primary_hit": primary_cache_hit, "translation_hit": translation_cache_hit if bilingual else None},
        }

    def optimize_subtitle_layout(self, caption_ids: list[str] | None = None, *, include_dialogue: bool = True) -> dict:
        """Re-fit existing subtitle metadata without rewriting text or changing cue timing."""
        wanted = set(caption_ids or [])
        changed = []; before = deepcopy(self.project); old_batch = self._batch_mode
        try:
            self._batch_mode = True
            for cap in self.project.get("captions", []):
                if wanted and cap.get("id") not in wanted:
                    continue
                layout = fit_subtitle_layout(cap.get("text", ""), cap.get("secondary_text"), float(cap.get("end",0))-float(cap.get("start",0)), font_size=int(cap.get("font_size",54)), secondary_font_scale=float(cap.get("secondary_font_scale",0.72)))
                cap.update({
                    "font_size": layout["font_size"], "max_line_chars": layout["max_line_chars"],
                    "secondary_max_line_chars": layout.get("secondary_max_line_chars"), "secondary_font_scale": layout["secondary_font_scale"],
                    "layout_auto_fit": True, "layout_density": layout["layout_density"], "layout_level": layout["layout_level"],
                }); changed.append(cap.get("id"))
            if include_dialogue:
                for seg in self.project.get("dialogue_segments", []):
                    dur = float(seg.get("duration") or max(0.25, float(self._scene(seg["scene_id"])["duration"]) - float(seg.get("start",0))))
                    layout = fit_subtitle_layout(seg.get("text", ""), seg.get("secondary_text"), dur, font_size=int(seg.get("font_size",54)), secondary_font_scale=float(seg.get("secondary_font_scale",0.72)))
                    seg.update({
                        "font_size": layout["font_size"], "max_line_chars": layout["max_line_chars"],
                        "secondary_max_line_chars": layout.get("secondary_max_line_chars"), "secondary_font_scale": layout["secondary_font_scale"],
                        "layout_auto_fit": True, "layout_density": layout["layout_density"], "layout_level": layout["layout_level"],
                    }); changed.append(seg.get("id"))
            validate_project(self.project)
        except Exception:
            self.project = before; self._batch_mode = old_batch; raise
        self._batch_mode = old_batch
        self._commit(f"optimize_subtitle_layout:{len(changed)}")
        return {"changed": changed, "count": len(changed), "policy": "layout_only_no_text_or_timing_rewrite"}

    def suggest_scene_staging(self, scene_id: str, *, count: int | None = None) -> dict:
        """Return visual anchor candidates only; character identity is intentionally not guessed."""
        scene = self._scene(scene_id); asset = self._asset(scene["asset_id"]); source = self._asset_path(scene["asset_id"])
        if asset.get("type") == "image":
            result = suggest_visual_anchors(source, count=count)
        elif asset.get("type") == "video":
            # Use a representative frame for staging suggestions; dynamic tracking remains a separate concern.
            import tempfile
            from .visual import _extract_video_frame
            with tempfile.TemporaryDirectory(prefix="agentcut_stage_") as td:
                frame = Path(td) / "frame.png"
                when = float(scene.get("source_in",0.0)) + max(0.0, float(scene.get("duration",1.0)) / max(float(scene.get("playback_rate",1.0)), 1e-6)) * 0.5
                _extract_video_frame(source, frame, when)
                result = suggest_visual_anchors(frame, count=count)
        else:
            raise AgentCutError("INVALID_ASSET_TYPE", "Scene staging suggestions require image/video assets", scene_id=scene_id, asset_type=asset.get("type"))
        return {"scene_id": scene_id, **result, "identity_policy": "anchors_only_no_character_guess"}

    def stage_scene_by_order(self, scene_id: str, character_ids: list[str], *, minimum_confidence: float = 0.18) -> dict:
        """Assign explicit character order to detected anchors. The caller supplies identity/order; vision supplies coordinates."""
        ids = [str(x) for x in character_ids or []]
        if not ids:
            raise AgentCutError("EMPTY_STAGING_ORDER", "character_ids must contain at least one known Cast member")
        cast = self.project.get("cast", {}) or {}
        unknown = [x for x in ids if x not in cast]
        if unknown:
            raise AgentCutError("CHARACTER_NOT_FOUND", "Staging order contains unknown Cast members", unknown=unknown, known=sorted(cast))
        suggestion = self.suggest_scene_staging(scene_id, count=len(ids))
        anchors = suggestion.get("anchors", [])
        if len(anchors) < len(ids):
            raise AgentCutError("STAGING_ANCHORS_INSUFFICIENT", "Visual analysis found too few distinct anchors", requested=len(ids), found=len(anchors), suggestion=suggestion)
        confidence = float(suggestion.get("confidence",0.0))
        if confidence < float(minimum_confidence):
            raise AgentCutError("STAGING_CONFIDENCE_LOW", "Visual anchors are too weak for automatic staging", confidence=confidence, minimum_confidence=minimum_confidence, recovery="Use stage_character manually or lower the threshold explicitly after inspection.")
        old = deepcopy(self.project); old_batch = self._batch_mode; staged=[]
        try:
            self._batch_mode = True
            for cid, anchor in zip(ids, anchors):
                staged.append(self.stage_character(scene_id, cid, focus_x=float(anchor["x"]), focus_y=float(anchor["y"])))
            validate_project(self.project)
        except Exception:
            self.project = old; self._batch_mode = old_batch; raise
        self._batch_mode = old_batch
        self._commit(f"stage_scene_by_order:{scene_id}:{len(staged)}")
        return {"scene_id": scene_id, "staged": staged, "visual_confidence": confidence, "identity_source": "explicit_character_order"}

    def define_character(
        self, character_id: str, *, display_name: str | None = None, focus_x: float = 0.5,
        focus_y: float = 0.5, subtitle_position: str = "auto", color: str = "#FFFFFF",
        role: str = "member", aliases: list[str] | None = None,
    ) -> dict:
        """Persist a lightweight cast entry used by dialogue direction and performance recipes."""
        cid = str(character_id).strip()
        if not cid:
            raise AgentCutError("INVALID_CHARACTER", "character_id must be non-empty")
        if cid in self.project.setdefault("cast", {}):
            raise AgentCutError("CHARACTER_EXISTS", "Character already exists", character_id=cid)
        fx = _finite(focus_x, field="character.focus_x"); fy = _finite(focus_y, field="character.focus_y")
        if not 0 <= fx <= 1 or not 0 <= fy <= 1:
            raise AgentCutError("INVALID_CHARACTER_FOCUS", "Character focus coordinates must be in [0,1]", focus_x=fx, focus_y=fy)
        if subtitle_position != "auto" and subtitle_position not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_CAPTION_POSITION", "Unsupported character subtitle position", position=subtitle_position)
        row = {
            "id": cid, "display_name": str(display_name or cid), "focus_x": fx, "focus_y": fy,
            "subtitle_position": subtitle_position, "color": normalize_color(color),
            "role": str(role or "member"), "aliases": [str(x) for x in (aliases or []) if str(x).strip()],
        }
        self.project["cast"][cid] = row
        validate_project(self.project)
        self._commit(f"define_character:{cid}")
        return deepcopy(row)

    def update_character(self, character_id: str, **changes) -> dict:
        cast = self.project.setdefault("cast", {})
        if character_id not in cast:
            raise AgentCutError("CHARACTER_NOT_FOUND", "Unknown character", character_id=character_id)
        allowed = {"display_name", "focus_x", "focus_y", "subtitle_position", "color", "role", "aliases"}
        unknown = set(changes) - allowed
        if unknown:
            raise AgentCutError("INVALID_OPERATION", "Unsupported character fields", fields=sorted(unknown), allowed=sorted(allowed))
        row = dict(cast[character_id]); row.update(changes)
        row["focus_x"] = _finite(row.get("focus_x", .5), field="character.focus_x")
        row["focus_y"] = _finite(row.get("focus_y", .5), field="character.focus_y")
        if not 0 <= row["focus_x"] <= 1 or not 0 <= row["focus_y"] <= 1:
            raise AgentCutError("INVALID_CHARACTER_FOCUS", "Character focus coordinates must be in [0,1]")
        pos = row.get("subtitle_position", "auto")
        if pos != "auto" and pos not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_CAPTION_POSITION", "Unsupported character subtitle position", position=pos)
        row["color"] = normalize_color(row.get("color"))
        row["display_name"] = str(row.get("display_name") or character_id)
        row["role"] = str(row.get("role") or "member")
        row["aliases"] = [str(x) for x in (row.get("aliases") or []) if str(x).strip()]
        cast[character_id] = row
        validate_project(self.project)
        self._commit(f"update_character:{character_id}")
        return deepcopy(row)

    def _effective_cast(self, scene_id: str | None = None) -> dict:
        cast = deepcopy(self.project.get("cast", {}) or {})
        if scene_id is None:
            return cast
        scene = self._scene(scene_id)
        for cid, staged in (scene.get("staging") or {}).items():
            if cid not in cast or not isinstance(staged, dict):
                continue
            cast[cid].update({k: staged[k] for k in ("focus_x", "focus_y", "visible") if k in staged})
        return cast

    def stage_character(
        self, scene_id: str, character_id: str, *, focus_x: float, focus_y: float, visible: bool = True,
    ) -> dict:
        """Override a Cast member's location for one scene without mutating global identity metadata."""
        scene = self._scene(scene_id)
        cast = self.project.get("cast", {})
        if str(character_id) in cast:
            cid, character = resolve_character(cast, character_id=str(character_id))
        else:
            cid, character = resolve_character(cast, speaker=str(character_id))
        if not character:
            raise AgentCutError("CHARACTER_NOT_FOUND", "Scene staging needs a known cast character", character_id=character_id)
        fx = _finite(focus_x, field="staging.focus_x"); fy = _finite(focus_y, field="staging.focus_y")
        if not 0 <= fx <= 1 or not 0 <= fy <= 1:
            raise AgentCutError("INVALID_CHARACTER_FOCUS", "Scene staging coordinates must be in [0,1]", focus_x=fx, focus_y=fy)
        scene.setdefault("staging", {})[cid] = {"focus_x": fx, "focus_y": fy, "visible": bool(visible)}
        validate_project(self.project)
        self._commit(f"stage_character:{scene_id}:{cid}")
        return {"scene_id": scene_id, "character_id": cid, **deepcopy(scene["staging"][cid])}

    def clear_scene_staging(self, scene_id: str) -> dict:
        scene = self._scene(scene_id)
        removed = len(scene.get("staging") or {})
        scene.pop("staging", None)
        self._commit(f"clear_scene_staging:{scene_id}")
        return {"scene_id": scene_id, "removed": removed}

    def remove_character(self, character_id: str) -> dict:
        cast = self.project.setdefault("cast", {})
        if character_id not in cast:
            raise AgentCutError("CHARACTER_NOT_FOUND", "Unknown character", character_id=character_id)
        linked = [d.get("id") for d in self.project.get("dialogue_segments", []) if d.get("character_id") == character_id]
        if linked:
            raise AgentCutError("CHARACTER_IN_USE", "Character is referenced by dialogue; update/remove those lines first", character_id=character_id, dialogue_ids=linked)
        row = cast.pop(character_id)
        self._commit(f"remove_character:{character_id}")
        return deepcopy(row)

    def _audio_asset_duration(self, asset_id: str) -> float | None:
        asset = self._asset(asset_id)
        if asset["type"] != "audio":
            raise AgentCutError("INVALID_ASSET_TYPE", "Dialogue requires audio asset", asset_id=asset_id, type=asset["type"])
        meta = asset.get("metadata") or {}
        try:
            return float((meta.get("format") or {}).get("duration"))
        except (TypeError, ValueError):
            return None

    def add_dialogue_segment(
        self,
        scene_id: str,
        text: str,
        *,
        audio_asset_id: str | None = None,
        start: float = 0.0,
        duration: float | None = None,
        fit_scene: bool = False,
        padding: float = 0.25,
        speaker: str | None = None,
        position: str = "bottom",
        font_size: int = 54,
        outline: int = 3,
        dialogue_id: str | None = None,
        volume_db: float = 0.0,
        character_id: str | None = None,
        emotion: str = "neutral",
        subtitle_style: str = "default",
        max_line_chars: int | None = None, secondary_max_line_chars: int | None = None,
        secondary_text: str | None = None, secondary_language: str = "en", secondary_font_scale: float = 0.72, auto_fit: bool = True,
    ) -> dict:
        """Create one source-of-truth dialogue item for text, audio and subtitles."""
        scene = self._scene(scene_id)
        text = str(text).strip()
        if not text:
            raise AgentCutError("INVALID_DIALOGUE", "Dialogue text cannot be empty")
        start = _finite(start, field="dialogue.start")
        padding = _finite(padding, field="dialogue.padding")
        volume_db = _finite(volume_db, field="dialogue.volume_db")
        if start < 0 or padding < 0:
            raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue start/padding must be >= 0")
        character_id, character = resolve_character(self.project.get("cast", {}), character_id=character_id, speaker=speaker)
        if character is not None and not speaker:
            speaker = character.get("display_name") or character_id
        subtitle_style = str(subtitle_style).strip().lower()
        if subtitle_style not in DIALOGUE_STYLES:
            raise AgentCutError("INVALID_DIALOGUE_STYLE", "Unknown dialogue subtitle style", style=subtitle_style, allowed=sorted(DIALOGUE_STYLES))
        if position == "auto":
            if character is not None and character.get("subtitle_position") not in (None, "auto"):
                position = character["subtitle_position"]
            elif character is not None:
                position = caption_zone_for_focus(float(character.get("focus_x", .5)), float(character.get("focus_y", .5)), text_length=len(text))
            else:
                position = self.suggest_caption_zone(scene_id, text=text)
        if position not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_CAPTION_POSITION", "Unsupported dialogue position", position=position)
        if audio_asset_id is not None:
            audio_dur = self._audio_asset_duration(audio_asset_id)
            if duration is None and audio_dur is not None:
                duration = audio_dur
        if duration is not None:
            duration = _finite(duration, field="dialogue.duration")
            if duration <= 0:
                raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue duration must be > 0", duration=duration)
        elif fit_scene:
            duration = max(0.01, float(scene["duration"]) - start)
        dialogue_id = dialogue_id or f"dialogue_{uuid.uuid4().hex[:8]}"
        if any(d.get("id") == dialogue_id for d in self.project.setdefault("dialogue_segments", [])):
            raise AgentCutError("DIALOGUE_EXISTS", "Dialogue ID already exists", dialogue_id=dialogue_id)
        clean_secondary = str(secondary_text).strip() if secondary_text is not None else None
        layout_duration = float(duration) if duration is not None else max(0.25, float(scene["duration"]) - start)
        layout = fit_subtitle_layout(text, clean_secondary, layout_duration, font_size=int(font_size), secondary_font_scale=float(secondary_font_scale)) if auto_fit else {}
        seg = {
            "id": dialogue_id, "scene_id": scene_id, "text": text,
            "audio_asset_id": audio_asset_id, "start": start, "duration": duration,
            "speaker": speaker, "position": position, "font_size": int(layout.get("font_size", font_size)),
            "outline": int(outline), "volume_db": volume_db, "character_id": character_id,
            "emotion": str(emotion or "neutral").lower(), "subtitle_style": subtitle_style,
            "max_line_chars": int(max_line_chars) if max_line_chars is not None else layout.get("max_line_chars"),
            "secondary_max_line_chars": int(secondary_max_line_chars) if secondary_max_line_chars is not None else layout.get("secondary_max_line_chars"),
            "secondary_text": clean_secondary,
            "secondary_language": str(secondary_language or "en"),
            "secondary_font_scale": float(layout.get("secondary_font_scale", _finite(secondary_font_scale, field="dialogue.secondary_font_scale"))),
            "layout_auto_fit": bool(auto_fit), "layout_density": layout.get("layout_density"), "layout_level": layout.get("layout_level"),
        }
        if seg["secondary_text"] is not None and not seg["secondary_text"]:
            raise AgentCutError("INVALID_DIALOGUE", "secondary_text cannot be blank when provided")
        if seg["secondary_font_scale"] <= 0 or seg["secondary_font_scale"] > 1.5:
            raise AgentCutError("INVALID_DIALOGUE_STYLE", "secondary_font_scale must be in (0,1.5]", value=seg["secondary_font_scale"])
        self.project["dialogue_segments"].append(seg)
        if fit_scene and duration is not None:
            scene["duration"] = max(0.01, start + duration + padding)
        self._commit(f"add_dialogue_segment:{dialogue_id}")
        return deepcopy(seg)

    def update_dialogue_segment(self, dialogue_id: str, **changes) -> dict:
        seg = next((d for d in self.project.get("dialogue_segments", []) if d.get("id") == dialogue_id), None)
        if seg is None:
            raise AgentCutError("DIALOGUE_NOT_FOUND", "Unknown dialogue segment", dialogue_id=dialogue_id)
        allowed = {"text", "audio_asset_id", "start", "duration", "speaker", "position", "font_size", "outline", "volume_db", "character_id", "emotion", "subtitle_style", "max_line_chars", "secondary_max_line_chars", "secondary_text", "secondary_language", "secondary_font_scale", "layout_auto_fit", "layout_density", "layout_level"}
        unknown = set(changes) - allowed
        if unknown:
            raise AgentCutError("INVALID_OPERATION", "Unsupported dialogue fields", fields=sorted(unknown), allowed=sorted(allowed))
        candidate = dict(seg); candidate.update(changes)
        text = str(candidate.get("text", "")).strip()
        if not text:
            raise AgentCutError("INVALID_DIALOGUE", "Dialogue text cannot be empty")
        start = _finite(candidate.get("start", 0.0), field="dialogue.start")
        if start < 0:
            raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue start must be >= 0")
        aid = candidate.get("audio_asset_id")
        if aid is not None:
            self._audio_asset_duration(aid)
        duration = candidate.get("duration")
        if duration is not None:
            duration = _finite(duration, field="dialogue.duration")
            if duration <= 0:
                raise AgentCutError("INVALID_DIALOGUE_TIME", "Dialogue duration must be > 0")
        cid, character = resolve_character(self.project.get("cast", {}), character_id=candidate.get("character_id"), speaker=candidate.get("speaker"))
        candidate["character_id"] = cid
        style = str(candidate.get("subtitle_style", "default")).lower()
        if style not in DIALOGUE_STYLES:
            raise AgentCutError("INVALID_DIALOGUE_STYLE", "Unknown dialogue subtitle style", style=style, allowed=sorted(DIALOGUE_STYLES))
        candidate["subtitle_style"] = style
        scale = _finite(candidate.get("secondary_font_scale", 0.72), field="dialogue.secondary_font_scale")
        if scale <= 0 or scale > 1.5:
            raise AgentCutError("INVALID_DIALOGUE_STYLE", "secondary_font_scale must be in (0,1.5]", value=scale)
        candidate["secondary_font_scale"] = scale
        if candidate.get("secondary_text") is not None:
            candidate["secondary_text"] = str(candidate.get("secondary_text")).strip()
            if not candidate["secondary_text"]:
                raise AgentCutError("INVALID_DIALOGUE", "secondary_text cannot be blank when provided")
        if candidate.get("position", "bottom") == "auto":
            if character is not None and character.get("subtitle_position") not in (None, "auto"):
                candidate["position"] = character["subtitle_position"]
            elif character is not None:
                candidate["position"] = caption_zone_for_focus(float(character.get("focus_x", .5)), float(character.get("focus_y", .5)), text_length=len(text))
            else:
                candidate["position"] = self.suggest_caption_zone(str(seg.get("scene_id")), text=text)
        if candidate.get("position", "bottom") not in CAPTION_POSITIONS:
            raise AgentCutError("INVALID_CAPTION_POSITION", "Unsupported dialogue position", position=candidate.get("position"))
        candidate.update({"text": text, "start": start, "duration": duration})
        seg.clear(); seg.update(candidate)
        self._commit(f"update_dialogue_segment:{dialogue_id}")
        return deepcopy(seg)

    def remove_dialogue_segment(self, dialogue_id: str) -> dict:
        idx = next((i for i, d in enumerate(self.project.get("dialogue_segments", [])) if d.get("id") == dialogue_id), None)
        if idx is None:
            raise AgentCutError("DIALOGUE_NOT_FOUND", "Unknown dialogue segment", dialogue_id=dialogue_id)
        removed = self.project["dialogue_segments"].pop(idx)
        self._commit(f"remove_dialogue_segment:{dialogue_id}")
        return deepcopy(removed)

    def compose_dialogue_scene(
        self, scene_id: str, lines: list, *, start: float = 0.0, gap: float = 0.10, pace: str = "normal",
        fit_scene: bool = True, padding: float = 0.30, direction: str = "auto",
        subtitle_style: str = "band", motion_strength: float = 0.35, replace_existing: bool = False,
    ) -> dict:
        """High-level dynamic-manga dialogue recipe: timing + subtitles + speaker-aware reframing in one undoable edit."""
        scene = self._scene(scene_id)
        cast = self._effective_cast(scene_id)
        prepared_lines = deepcopy(lines)
        for row in prepared_lines:
            if isinstance(row, dict) and row.get("duration") is None:
                aid = row.get("audio_asset_id", row.get("audio"))
                if aid:
                    audio_dur = self._audio_asset_duration(str(aid))
                    if audio_dur is not None:
                        row["duration"] = round(audio_dur, 3)
        sequence = plan_dialogue_sequence(prepared_lines, cast=cast, start=start, gap=gap, pace=pace, default_style=subtitle_style)
        required_end = float(sequence["end"]) + max(0.0, float(padding))
        old = deepcopy(self.project)
        old_batch = self._batch_mode
        try:
            self._batch_mode = True
            if replace_existing:
                self.project["dialogue_segments"] = [d for d in self.project.get("dialogue_segments", []) if d.get("scene_id") != scene_id]
            if fit_scene and required_end > float(scene["duration"]):
                scene["duration"] = round(required_end, 3)
            for row in sequence["lines"]:
                self.add_dialogue_segment(
                    scene_id, row["text"], audio_asset_id=row.get("audio_asset_id"), start=row["start"],
                    duration=row["duration"], speaker=row.get("speaker"), position=row.get("position", "bottom"),
                    font_size=row.get("font_size", 54), outline=row.get("outline", 3), volume_db=row.get("volume_db", 0.0),
                    character_id=row.get("character_id"), emotion=row.get("emotion", "neutral"),
                    subtitle_style=row.get("subtitle_style", subtitle_style), max_line_chars=row.get("max_line_chars", 18),
                    secondary_text=row.get("secondary_text"), secondary_language=row.get("secondary_language", "en"),
                    secondary_font_scale=row.get("secondary_font_scale", 0.72),
                )
            directed = False
            focus_path = []
            coverage_result = None
            direction_key = str(direction).strip().lower()
            if direction_key not in {"auto", "off", "none", "speaker", "speaker_tracking", "coverage", "shot_coverage"}:
                raise AgentCutError("INVALID_DIALOGUE_DIRECTION", "Unknown dialogue direction mode", direction=direction)
            known_lines = sum(1 for row in sequence["lines"] if row.get("character_id"))
            use_coverage = direction_key in {"coverage", "shot_coverage"} or (
                direction_key == "auto" and known_lines >= 2 and float(scene["duration"]) >= 4.0
            )
            if use_coverage:
                coverage_result = self.direct_dialogue_coverage(
                    scene_id, intensity=max(.35, min(1.0, float(motion_strength) + .24)),
                    reset_gap=max(.65, float(gap) + .55), max_shots=min(10, max(3, known_lines + 2)),
                )
                directed = True
            elif direction_key not in {"off", "none"}:
                comp = validate_composition(scene.get("composition") or {})
                focus_path = dialogue_focus_path(
                    sequence, scene_duration=float(scene["duration"]),
                    default_focus=(comp.get("focus_x", .5), comp.get("focus_y", .5)),
                )
                if len(focus_path) >= 2 and known_lines:
                    comp["mode"] = "cover"
                    comp["crop_zoom"] = max(float(comp.get("crop_zoom", 1.0)), round(1.04 + .10 * _finite(motion_strength, field="motion_strength"), 4))
                    comp["focus_path"] = focus_path
                    scene["composition"] = validate_composition(comp)
                    strength = max(0.0, min(1.0, float(motion_strength)))
                    scene["camera"] = {"type": "slow_push", "amount": round(0.006 + 0.012 * strength, 4), "easing": "ease_in_out", "anchor": "center"}
                    directed = True
            validate_project(self.project)
        except Exception:
            self.project = old
            self._batch_mode = old_batch
            raise
        self._batch_mode = old_batch
        self._commit(f"compose_dialogue_scene:{scene_id}:{len(sequence['lines'])}")
        ids = [d["id"] for d in self.project.get("dialogue_segments", []) if d.get("scene_id") == scene_id][-len(sequence["lines"]):]
        return {
            "scene_id": scene_id, "dialogue_ids": ids, "line_count": len(sequence["lines"]),
            "sequence_duration": sequence["duration"], "scene_duration": scene["duration"],
            "speaker_tracking": directed, "focus_points": len(focus_path),
            "direction_mode": "coverage" if coverage_result else ("speaker_tracking" if directed else "off"),
            "coverage_shots": (coverage_result or {}).get("shot_count", 0),
        }

    def direct_dialogue_coverage(
        self, scene_id: str, *, intensity: float = 0.62, reset_gap: float = 0.85,
        max_shots: int = 9, include_secondary: bool = True,
    ) -> dict:
        """Turn a long static dialogue image into restrained editorial coverage.

        The method reads existing global captions that overlap the scene. Known Cast speakers
        become medium/close reframes; long pauses reset to a group shot. The source scene,
        subtitle timings and text remain unchanged. A per-frame ``camera.shot_path`` gives
        genuine discrete reframes without fragmenting the canonical timeline.
        """
        scene = self._scene(scene_id)
        duration = float(scene.get("duration", 0.0))
        if duration <= 0:
            raise AgentCutError("INVALID_DURATION", "Dialogue coverage requires a positive scene duration", scene=scene_id)
        intensity = max(0.0, min(1.0, _finite(intensity, field="coverage.intensity")))
        reset_gap = max(0.35, min(3.0, _finite(reset_gap, field="coverage.reset_gap")))
        max_shots = int(max_shots)
        if max_shots < 2 or max_shots > 16:
            raise AgentCutError("INVALID_COVERAGE", "max_shots must be in [2,16]", max_shots=max_shots)

        timeline = build_timeline(self.project)
        row = next((x for x in timeline.get("scenes", []) if x.get("scene_id") == scene_id), None)
        if row is None:
            raise AgentCutError("SCENE_NOT_FOUND", "Scene is missing from timeline", scene=scene_id)
        scene_start, scene_end = float(row["start"]), float(row["end"])
        cast = self._effective_cast(scene_id)
        captions = []
        seen_entries = set()
        for cap in sorted(self.project.get("captions", []), key=lambda x: float(x.get("start", 0))):
            cs, ce = float(cap.get("start", 0)), float(cap.get("end", 0))
            midpoint = (cs + ce) * .5
            # A caption may visually linger over a hard cut. Direct it from the scene that
            # owns most of the utterance instead of creating a duplicate 1-frame reaction
            # in the following scene.
            if midpoint < scene_start - 1e-6 or midpoint >= scene_end - 1e-6:
                continue
            cid = cap.get("character_id")
            character = cast.get(str(cid)) if cid else None
            if character is None and cap.get("speaker"):
                try:
                    cid, character = resolve_character(cast, speaker=cap.get("speaker"))
                except AgentCutError:
                    cid, character = None, None
            if not character:
                continue
            entry = dict(cap); entry["start"], entry["end"] = cs, ce
            key = (str(cid), round(cs, 2), str(entry.get("text", "")))
            seen_entries.add(key)
            captions.append((entry, str(cid), character))
        # Native dialogue segments use scene-local time. Include them so high-level dialogue
        # recipes can receive coverage without first materializing duplicate global captions.
        for seg in self.project.get("dialogue_segments", []):
            if seg.get("scene_id") != scene_id:
                continue
            cs = scene_start + float(seg.get("start", 0.0))
            ce = cs + float(seg.get("duration", 0.0))
            cid = seg.get("character_id")
            character = cast.get(str(cid)) if cid else None
            if character is None and seg.get("speaker"):
                try:
                    cid, character = resolve_character(cast, speaker=seg.get("speaker"))
                except AgentCutError:
                    cid, character = None, None
            if not character:
                continue
            entry = dict(seg); entry["start"], entry["end"] = cs, ce
            key = (str(cid), round(cs, 2), str(entry.get("text", "")))
            if key in seen_entries:
                continue
            captions.append((entry, str(cid), character)); seen_entries.add(key)
        captions.sort(key=lambda x: float(x[0].get("start", 0)))
        if not captions:
            raise AgentCutError("NO_SPEAKER_CAPTIONS", "Dialogue coverage needs at least one caption/dialogue line resolved to Cast in this scene", scene=scene_id)

        points: list[dict] = [{"t": 0.0, "x": 0.5, "y": 0.5, "zoom": 1.0, "cut": False}]
        shots = []
        prev_end = scene_start
        prev_cid = None
        speaker_index = 0
        for cap, cid, character in captions:
            if len(shots) >= max_shots:
                break
            cs = max(scene_start, float(cap.get("start", scene_start)))
            ce = min(scene_end, float(cap.get("end", cs + .5)))
            if shots and cs - prev_end >= reset_gap and cs - scene_start > .35:
                rt = max(0.0, min(1.0, (prev_end + min(.28, (cs-prev_end)*.45) - scene_start) / duration))
                if rt > points[-1]["t"] + .015:
                    points.append({"t": round(rt, 5), "x": .5, "y": .5, "zoom": 1.0, "cut": True})
                    shots.append({"kind": "group_reset", "time": round(rt*duration, 3)})
            st = max(0.0, min(1.0, (cs - scene_start) / duration))
            et = max(st, min(1.0, (ce - scene_start) / duration))
            # Alternate scale for consecutive lines from the same speaker; this avoids a
            # mechanical identical crop while staying far below aggressive punch-in levels.
            style = str(cap.get("subtitle_style", "default"))
            base = 1.105 + .110 * intensity
            if style in {"shout", "manga"}:
                base += .045
            if cid == prev_cid:
                base += .035 if speaker_index % 2 else -.014
            zoom = round(max(1.055, min(1.34, base)), 4)
            tx = max(0.03, min(.97, float(character.get("focus_x", .5))))
            ty = max(0.08, min(.92, float(character.get("focus_y", .5))))
            start_point = {"t": round(st, 5), "x": round(tx, 5), "y": round(ty, 5), "zoom": zoom, "cut": True}
            if start_point["t"] <= points[-1]["t"]:
                start_point["t"] = round(min(1.0, points[-1]["t"] + .001), 5)
            if start_point["t"] < 1.0:
                points.append(start_point)
                # A tiny within-shot drift gives life without turning every line into a zoom effect.
                if et - st >= .018 and len(points) < 23:
                    drift_zoom = round(min(1.26, zoom + .008 + .010 * intensity), 4)
                    end_t = round(min(1.0, max(start_point["t"] + .001, et)), 5)
                    points.append({"t": end_t, "x": round(tx, 5), "y": round(ty, 5), "zoom": drift_zoom, "cut": False})
                shots.append({
                    "kind": "speaker", "character_id": cid, "speaker": cap.get("speaker"),
                    "start": round(cs-scene_start, 3), "end": round(ce-scene_start, 3),
                    "zoom": zoom, "subtitle_style": style,
                })
            prev_end, prev_cid = ce, cid
            speaker_index += 1

        if scene_end - prev_end >= reset_gap * .72 and points[-1]["t"] < .985:
            rt = max(points[-1]["t"] + .001, min(.985, (prev_end + min(.3, (scene_end-prev_end)*.45) - scene_start) / duration))
            points.append({"t": round(rt, 5), "x": .5, "y": .5, "zoom": 1.0, "cut": True})
            shots.append({"kind": "group_reset", "time": round(rt*duration, 3)})
        if points[-1]["t"] < 1.0:
            last = dict(points[-1]); last["t"] = 1.0; last["cut"] = False; points.append(last)

        # Clamp to renderer/validator budget while preserving first + final frames.
        if len(points) > 24:
            middle = points[1:-1]
            wanted = 22
            pick = [middle[round(i*(len(middle)-1)/max(1,wanted-1))] for i in range(wanted)] if middle else []
            points = [points[0], *pick, points[-1]]

        scene["camera"] = {
            "type": "static", "amount": 0.0, "easing": "linear", "anchor": "center",
            "shot_path": points, "coverage_mode": "dialogue",
        }
        # Coverage owns the shot-to-shot motion. Disable the older continuous speaker pan so
        # two independent motion systems do not fight each other.
        comp = validate_composition(scene.get("composition") or {})
        comp["focus_path"] = []
        comp["crop_zoom"] = min(float(comp.get("crop_zoom", 1.0)), 1.035)
        comp["focus_x"], comp["focus_y"] = .5, .5
        scene["composition"] = validate_composition(comp)
        validate_project(self.project)
        self._commit(f"direct_dialogue_coverage:{scene_id}:{len(shots)}")
        return {"scene_id": scene_id, "shots": shots, "shot_count": len(shots), "keyframes": len(points), "camera": deepcopy(scene["camera"])}

    def direct_attention_insert(
        self, scene_id: str, *, start: float, duration: float, focus_x: float, focus_y: float,
        intensity: float = 0.68, return_to: str = "group",
    ) -> dict:
        """Insert a semantic object/action close-up without fragmenting the scene.

        This complements Cast-aware reaction/coverage shots: the focus may be an object,
        projectile, UI element or environmental detail that should not be invented as a
        character. Existing dialogue coverage is preserved as long as the insert does not
        overlap another discrete cut.
        """
        scene = self._scene(scene_id)
        scene_dur = float(scene.get("duration", 0.0))
        start = _finite(start, field="attention.start")
        duration = _finite(duration, field="attention.duration")
        fx = max(0.0, min(1.0, _finite(focus_x, field="attention.focus_x")))
        fy = max(0.0, min(1.0, _finite(focus_y, field="attention.focus_y")))
        intensity = max(0.0, min(1.0, _finite(intensity, field="attention.intensity")))
        if start < 0 or duration <= 0 or start + duration > scene_dur + 1e-6:
            raise AgentCutError("INVALID_ATTENTION_TIME", "Attention insert must fit inside scene", scene=scene_id, start=start, duration=duration, scene_duration=scene_dur)
        return_to = str(return_to).strip().lower()
        if return_to not in {"group", "hold"}:
            raise AgentCutError("INVALID_ATTENTION_RETURN", "return_to must be group or hold", return_to=return_to)

        cam = deepcopy(scene.get("camera") or {"type":"static","amount":0.0,"easing":"linear","anchor":"center"})
        path = deepcopy(cam.get("shot_path") or [])
        if not path:
            path = [
                {"t":0.0,"x":.5,"y":.5,"zoom":1.0,"cut":False},
                {"t":1.0,"x":.5,"y":.5,"zoom":1.0,"cut":False},
            ]
        st = max(0.0, min(1.0, start / scene_dur))
        et = max(st, min(1.0, (start + duration) / scene_dur))
        # Do not silently overwrite another semantic hard reframe. The Agent can shorten or
        # move the insert after inspecting the returned conflict time.
        conflicts = [float(x.get("t",0))*scene_dur for x in path if x.get("cut") and st + 1e-5 < float(x.get("t",0)) < et - 1e-5]
        if conflicts:
            raise AgentCutError("ATTENTION_BEAT_CONFLICT", "Attention insert overlaps an existing discrete shot change", scene=scene_id, conflict_times=[round(x,3) for x in conflicts])
        fps = max(1.0, float(self.project.get("video",{}).get("fps",30)))
        eps = min(.02, 1.0 / max(fps * scene_dur, 1.0))
        z = round(min(1.36, 1.11 + .17 * intensity), 4)
        drift = round(min(1.39, z + .008 + .008*intensity), 4)
        additions = [
            {"t":round(st,5),"x":round(fx,5),"y":round(fy,5),"zoom":z,"cut":True},
            {"t":round(max(st, et-eps),5),"x":round(fx,5),"y":round(fy,5),"zoom":drift,"cut":False},
        ]
        if return_to == "group" and et < 1.0:
            additions.append({"t":round(et,5),"x":.5,"y":.5,"zoom":1.0,"cut":True})
        elif return_to == "hold" and et < 1.0:
            additions.append({"t":round(et,5),"x":round(fx,5),"y":round(fy,5),"zoom":drift,"cut":False})
        path.extend(additions)
        path.sort(key=lambda x: (float(x.get("t",0)), 1 if x.get("cut") else 0))
        # Deterministically resolve same-time points: a cut wins, otherwise the later semantic
        # keyframe wins. Keep within validator/renderer keyframe budget.
        dedup=[]
        for row in path:
            if dedup and abs(float(dedup[-1].get("t",0))-float(row.get("t",0))) < 1e-7:
                if row.get("cut") or not dedup[-1].get("cut"):
                    dedup[-1]=row
            else:
                dedup.append(row)
        if len(dedup) > 24:
            raise AgentCutError("ATTENTION_PATH_TOO_DENSE", "Attention insert would exceed camera shot_path budget", scene=scene_id, points=len(dedup))
        cam.update({"type":"static","amount":0.0,"easing":"linear","anchor":"center","shot_path":dedup})
        scene["camera"] = cam
        comp = validate_composition(scene.get("composition") or {})
        comp["focus_path"] = []
        comp["crop_zoom"] = min(float(comp.get("crop_zoom",1.0)),1.035)
        comp["focus_x"],comp["focus_y"] = .5,.5
        scene["composition"] = validate_composition(comp)
        validate_project(self.project)
        self._commit(f"direct_attention_insert:{scene_id}:{start:.3f}")
        return {"scene_id":scene_id,"start":start,"duration":duration,"focus":{"x":fx,"y":fy},"zoom":z,"return_to":return_to,"keyframes":len(dedup)}

    def direct_performance_scene(
        self, scene_id: str, *, member_ids: list[str] | None = None, energy: float = 0.65,
        style: str = "anime_band", points: int = 7, rhythm_asset_id: str | None = None,
    ) -> dict:
        """Create restrained deterministic motion for a static anime-band/performance image."""
        scene = self._scene(scene_id)
        key = str(style).strip().lower()
        if key not in PERFORMANCE_STYLES:
            raise AgentCutError("INVALID_PERFORMANCE_STYLE", "Unknown performance style", style=style, allowed=sorted(PERFORMANCE_STYLES))
        energy = max(0.0, min(1.0, _finite(energy, field="performance.energy")))
        cast = self._effective_cast(scene_id)
        path = performance_focus_path(cast, member_ids, energy=energy, points=points)
        beat_aligned = False
        if rhythm_asset_id and path:
            asset = self._asset(rhythm_asset_id)
            if asset.get("type") != "audio":
                raise AgentCutError("INVALID_ASSET_TYPE", "Performance rhythm reference must be audio", asset_id=rhythm_asset_id)
            analysis = (asset.get("metadata") or {}).get("rhythm")
            if not analysis:
                ap = Path(asset["path"]); ap = ap if ap.is_absolute() else self.root / ap
                analysis = analyze_audio_rhythm_file(ap)
                asset.setdefault("metadata", {})["rhythm"] = deepcopy(analysis)
            beats = [float(x) for x in (analysis.get("beats") or []) if 0 <= float(x) <= float(scene["duration"])]
            if len(beats) >= 2:
                # Use a deterministic subset of musical beats as attention switches.
                wanted = min(len(path), len(beats), 12)
                chosen = [beats[round(i * (len(beats)-1) / max(1, wanted-1))] for i in range(wanted)]
                chosen[0] = 0.0
                if chosen[-1] < float(scene["duration"]) * .88:
                    chosen[-1] = float(scene["duration"])
                for row, t in zip(path[:wanted], chosen):
                    row["t"] = round(max(0.0, min(1.0, t / float(scene["duration"]))), 4)
                path = path[:wanted]
                beat_aligned = True
        comp = validate_composition(scene.get("composition") or {})
        comp["mode"] = "cover"
        comp["crop_zoom"] = max(float(comp.get("crop_zoom", 1.0)), round(1.04 + 0.12 * energy, 4))
        if path:
            comp["focus_path"] = [{"t": x["t"], "x": x["x"], "y": x["y"]} for x in path]
            comp["focus_x"], comp["focus_y"] = path[0]["x"], path[0]["y"]
        scene["composition"] = validate_composition(comp)
        # Higher-energy performance uses more crop travel, not a huge zoom. This avoids PPT-like constant pushes.
        scene["camera"] = {
            "type": "slow_push" if energy >= .28 else "static",
            "amount": round(0.004 + 0.015 * energy, 4) if energy >= .28 else 0.0,
            "easing": "ease_in_out", "anchor": "center",
        }
        validate_project(self.project)
        self._commit(f"direct_performance_scene:{scene_id}:{key}")
        return {"scene_id": scene_id, "style": key, "energy": energy, "focus_points": len(path), "beat_aligned": beat_aligned, "rhythm_asset_id": rhythm_asset_id, "crop_zoom": scene["composition"]["crop_zoom"], "camera": deepcopy(scene["camera"])}

    def direct_reaction_scene(
        self, scene_id: str, character_id: str, *, intensity: float = 0.62,
    ) -> dict:
        """Anime dialogue reaction shot: focus one known character with a restrained close reframe."""
        scene = self._scene(scene_id)
        cast = self._effective_cast(scene_id)
        if str(character_id) in cast:
            cid, character = resolve_character(cast, character_id=str(character_id))
        else:
            cid, character = resolve_character(cast, speaker=str(character_id))
        if not character:
            raise AgentCutError("CHARACTER_NOT_FOUND", "Reaction shot needs a known cast character", character_id=character_id)
        intensity = max(0.0, min(1.0, _finite(intensity, field="reaction.intensity")))
        comp = validate_composition(scene.get("composition") or {})
        start_x, start_y = float(comp.get("focus_x", .5)), float(comp.get("focus_y", .5))
        tx, ty = float(character.get("focus_x", .5)), float(character.get("focus_y", .5))
        comp["mode"] = "cover"
        comp["crop_zoom"] = max(float(comp.get("crop_zoom", 1.0)), round(1.10 + .16 * intensity, 4))
        comp["focus_x"], comp["focus_y"] = tx, ty
        comp["focus_path"] = [
            {"t": 0.0, "x": start_x, "y": start_y},
            {"t": round(.18 + .12 * (1-intensity), 4), "x": tx, "y": ty},
            {"t": 1.0, "x": tx, "y": ty},
        ]
        scene["composition"] = validate_composition(comp)
        scene["camera"] = {"type": "slow_push", "amount": round(.006 + .014 * intensity, 4), "easing": "ease_out", "anchor": "center"}
        validate_project(self.project)
        self._commit(f"direct_reaction_scene:{scene_id}:{cid}")
        return {
            "scene_id": scene_id, "character_id": cid, "display_name": character.get("display_name"),
            "intensity": intensity, "focus": {"x": tx, "y": ty}, "crop_zoom": scene["composition"]["crop_zoom"],
            "camera": deepcopy(scene["camera"]),
        }

    def direct_band_sequence(
        self, scene_ids: list[str], rhythm_asset_id: str, *, energy: float = 0.72,
        member_ids: list[str] | None = None, snap_window: float = 0.18, minimum_scene_duration: float = 0.30,
    ) -> dict:
        """Beat-aware high-level direction for an anime-band montage across multiple scenes."""
        ids = [str(x) for x in (scene_ids or [])]
        if not ids:
            raise AgentCutError("INVALID_BAND_SEQUENCE", "scene_ids cannot be empty")
        for sid in ids:
            self._scene(sid)
        old = deepcopy(self.project); old_batch = self._batch_mode
        self._batch_mode = True
        try:
            plan = self.rhythm_plan(ids, rhythm_asset_id, minimum_scene_duration=minimum_scene_duration, snap_window=snap_window)
            for sid, dur in zip(ids, plan["durations"]):
                self.set_duration(sid, float(dur))
            directions = []
            members = [str(x) for x in (member_ids or [])]
            for i, sid in enumerate(ids):
                rotated = members[i % len(members):] + members[:i % len(members)] if members else None
                directions.append(self.direct_performance_scene(
                    sid, member_ids=rotated, energy=energy, style="anime_band",
                    points=max(4, min(9, 4 + int(round(float(energy) * 5)))), rhythm_asset_id=rhythm_asset_id,
                ))
            validate_project(self.project)
        except Exception:
            self.project = old; self._batch_mode = old_batch
            raise
        self._batch_mode = old_batch
        self._commit(f"direct_band_sequence:{len(ids)}:{rhythm_asset_id}")
        return {
            "scene_ids": ids, "rhythm_asset_id": rhythm_asset_id, "energy": float(energy),
            "durations": plan["durations"], "directions": directions, "timeline": self.get_timeline(),
        }

    def apply_scene_recipe(self, scene_id: str, recipe: str, *, payload: dict | None = None) -> dict:
        """Low-cognition Agent macro: one semantic action expands into a safe high-level edit."""
        payload = deepcopy(payload or {})
        key = str(recipe).strip().lower().replace("-", "_").replace(" ", "_")
        if key in {"dialogue", "anime_dialogue", "band_dialogue", "conversation"}:
            lines = payload.pop("lines", payload.pop("dialogue", None))
            if not isinstance(lines, list) or not lines:
                raise AgentCutError("RECIPE_NEEDS_LINES", "Dialogue recipe requires payload.lines", recipe=key)
            payload.setdefault("replace_existing", True)
            return {"recipe": key, "result": self.compose_dialogue_scene(scene_id, lines, **payload)}
        if key in {"band", "anime_band", "performance", "band_performance"}:
            return {"recipe": key, "result": self.direct_performance_scene(scene_id, **payload)}
        if key in {"reaction", "reaction_shot", "close_reaction"}:
            cid = payload.pop("character_id", payload.pop("character", payload.pop("speaker", None)))
            if not cid:
                raise AgentCutError("RECIPE_NEEDS_CHARACTER", "Reaction recipe requires payload.character", recipe=key)
            resolved, _ = resolve_character(self.project.get("cast", {}), character_id=None, speaker=str(cid))
            if resolved is None and str(cid) in self.project.get("cast", {}):
                resolved = str(cid)
            if resolved is None:
                raise AgentCutError("CHARACTER_NOT_FOUND", "Reaction character is not in cast", character=cid, available=sorted(self.project.get("cast", {})))
            return {"recipe": key, "result": self.direct_reaction_scene(scene_id, resolved, **payload)}
        if key in {"calm", "calm_hold"}:
            scene = self._scene(scene_id)
            scene["camera"] = {"type": "slow_push", "amount": 0.006, "easing": "ease_in_out", "anchor": "center"}
            self._commit(f"scene_recipe:{scene_id}:calm")
            return {"recipe": key, "result": {"scene_id": scene_id, "camera": deepcopy(scene["camera"])}}
        raise AgentCutError("RECIPE_NOT_FOUND", "Unknown scene recipe", recipe=recipe, allowed=["dialogue", "band_performance", "reaction", "calm"])

    def rebuild_plan(self, scene_ids: list[str] | tuple[str, ...]) -> dict:
        """Return the minimal scene/transition neighborhood affected by local edits."""
        ids = [str(x) for x in scene_ids]
        order = [s["id"] for s in self.project.get("scenes", [])]
        missing = [sid for sid in ids if sid not in order]
        if missing:
            raise AgentCutError("SCENE_NOT_FOUND", "Unknown scene in rebuild plan", scenes=missing)
        affected = set(ids)
        transition_boundaries = set()
        for sid in ids:
            i = order.index(sid)
            if i > 0:
                affected.add(order[i - 1])
                transition_boundaries.add((order[i - 1], sid))
            if i + 1 < len(order):
                affected.add(order[i + 1])
                transition_boundaries.add((sid, order[i + 1]))
        ordered = [sid for sid in order if sid in affected]
        span = {"start_scene": ordered[0], "end_scene": ordered[-1]} if ordered else None
        return {
            "requested_scenes": ids,
            "render_scenes": ordered,
            "transition_boundaries": [{"from_scene": a, "to_scene": b} for a, b in sorted(transition_boundaries, key=lambda x: order.index(x[0]))],
            "recommended_span": span,
            "reason": "Local edits invalidate the scene plus adjacent transition boundaries only.",
        }

    def undo(self) -> dict:
        self.project = self.history.undo()
        save_project(self.root, self.project)
        return self.get_project()

    def redo(self) -> dict:
        self.project = self.history.redo()
        save_project(self.root, self.project)
        return self.get_project()

    def versions(self) -> list[dict]:
        return self.history.list_versions()

    def diff(self, version_a: int, version_b: int) -> str:
        return self.history.diff(version_a, version_b)

    def create_checkpoint(self, name: str, *, note: str | None = None) -> dict:
        """Create a named immutable project snapshot for non-destructive revision work."""
        return self.history.create_checkpoint(name, deepcopy(self.project), note=note)

    def checkpoints(self) -> list[dict]:
        return self.history.list_checkpoints()

    def restore_checkpoint(self, name: str) -> dict:
        """Restore the entire project from a named checkpoint and record that restore."""
        restored = deepcopy(self.history.get_checkpoint(name))
        validate_project(restored)
        self.project = restored
        save_project(self.root, self.project)
        self.history.commit(f"restore_checkpoint:{name}", self.project)
        return self.get_project()

    @staticmethod
    def _scene_from_project(project: dict, scene_id: str) -> dict:
        for scene in project.get("scenes", []):
            if scene.get("id") == scene_id:
                return scene
        raise AgentCutError("SCENE_NOT_FOUND", "Scene does not exist in requested historical state", scene=scene_id)

    def restore_scene(
        self,
        scene_id: str,
        *,
        version: int | None = None,
        checkpoint: str | None = None,
        components: list[str] | None = None,
    ) -> dict:
        """Restore one semantic scene without rolling back unrelated edits.

        `components` allows layer-scoped restoration: camera/effects/transition can be
        reverted while timing/source edits remain intact. This is the preferred primitive
        for iterative motion-design work. Omitting components restores the entire scene.
        """
        if (version is None) == (checkpoint is None):
            raise AgentCutError("INVALID_OPERATION", "Provide exactly one of version or checkpoint")
        source = self.history.get(version) if version is not None else self.history.get_checkpoint(checkpoint or "")
        historical = deepcopy(self._scene_from_project(source, scene_id))
        current_index = next((i for i, scene in enumerate(self.project.get("scenes", [])) if scene.get("id") == scene_id), None)
        if current_index is None:
            raise AgentCutError("SCENE_NOT_FOUND", "Cannot restore a scene that is absent from the current project", scene=scene_id)

        if components is None:
            restored = historical
        else:
            allowed = {"asset", "timing", "camera", "effects", "audio", "transition"}
            unknown = set(components) - allowed
            if unknown or not components:
                raise AgentCutError("INVALID_RESTORE_COMPONENT", "Unsupported or empty restore component list", components=components, allowed=sorted(allowed))
            restored = deepcopy(self.project["scenes"][current_index])
            for component in components:
                if component == "asset":
                    restored["asset_id"] = historical["asset_id"]
                elif component == "timing":
                    for key in ("duration", "source_in", "playback_rate"):
                        restored[key] = deepcopy(historical.get(key))
                elif component == "camera":
                    restored["camera"] = deepcopy(historical.get("camera", {}))
                elif component == "effects":
                    restored["effects"] = deepcopy(historical.get("effects", []))
                elif component == "audio":
                    restored["audio"] = deepcopy(historical.get("audio", []))
                elif component == "transition":
                    restored["transition_out"] = deepcopy(historical.get("transition_out", {"type": "cut", "duration": 0.0}))

        self.project["scenes"][current_index] = restored
        validate_project(self.project)
        suffix = f"v{version}" if version is not None else f"checkpoint:{checkpoint}"
        layer = "all" if components is None else "+".join(components)
        self._commit(f"restore_scene:{scene_id}:{layer}:{suffix}")
        return deepcopy(restored)

    def scene_history(self, scene_id: str) -> list[dict]:
        """Return only versions where this scene changed, with the historical scene snapshot."""
        out = []
        previous = object()
        for row in self.history.list_versions():
            project = self.history.get(row["version"])
            scene = next((deepcopy(s) for s in project.get("scenes", []) if s.get("id") == scene_id), None)
            if scene != previous:
                out.append({
                    "version": row["version"],
                    "label": row["label"],
                    "created_at": row.get("created_at"),
                    "current": row.get("current", False),
                    "scene": scene,
                })
                previous = deepcopy(scene)
        return out

    def _operation_map(self) -> dict:
        return {
            "add_scene": self.add_scene,
            "delete_scene": self.delete_scene,
            "set_scene_asset": self.set_scene_asset,
            "set_video_mode": self.set_video_mode,
            "configure_gen3": self.configure_gen3,
            "set_gen3_scene": self.set_gen3_scene,
            "set_gen3_card": self.set_gen3_card,
            "register_gen3_actor_card": self.register_gen3_actor_card,
            "place_gen3_actor": self.place_gen3_actor,
            "compile_gen3": self.compile_gen3,
            "move_scene": self.move_scene,
            "set_duration": self.set_duration,
            "set_source": self.set_source,
            "set_camera": self.set_camera,
            "set_composition": self.set_composition,
            "apply_auto_composition": self.apply_auto_composition,
            "apply_visual_composition": self.apply_visual_composition,
            "auto_compose_scenes": self.auto_compose_scenes,
            "set_cinematic_frame": self.set_cinematic_frame,
            "clear_cinematic_frame": self.clear_cinematic_frame,
            "fragment_scene": self.fragment_scene,
            "apply_cinematic_treatment": self.apply_cinematic_treatment,
            "analyze_visual": self.analyze_visual,
            "add_layer": self.add_layer,
            "update_layer": self.update_layer,
            "remove_layer": self.remove_layer,
            "apply_layer_motion": self.apply_layer_motion,
            "set_fact": self.set_fact,
            "remove_fact": self.remove_fact,
            "add_effect": self.add_effect,
            "apply_effect_preset": self.apply_effect_preset,
            "remove_effect": self.remove_effect,
            "clear_effects": self.clear_effects,
            "add_filter": self.add_filter,
            "clear_filters": self.clear_filters,
            "apply_motion_preset": self.apply_motion_preset,
            "set_transition": self.set_transition,
            "apply_transition_preset": self.apply_transition_preset,
            "set_transition_event": self.set_transition_event,
            "clear_transition_sfx": self.clear_transition_sfx,
            "add_scene_audio": self.add_scene_audio,
            "remove_scene_audio": self.remove_scene_audio,
            "update_scene_audio": self.update_scene_audio,
            "add_audio_track": self.add_audio_track,
            "remove_audio_track": self.remove_audio_track,
            "update_audio_track": self.update_audio_track,
            "define_character": self.define_character,
            "update_character": self.update_character,
            "stage_character": self.stage_character,
            "stage_scene_by_order": self.stage_scene_by_order,
            "clear_scene_staging": self.clear_scene_staging,
            "remove_character": self.remove_character,
            "compose_dialogue_scene": self.compose_dialogue_scene,
            "direct_dialogue_coverage": self.direct_dialogue_coverage,
            "direct_attention_insert": self.direct_attention_insert,
            "direct_performance_scene": self.direct_performance_scene,
            "direct_reaction_scene": self.direct_reaction_scene,
            "direct_band_sequence": self.direct_band_sequence,
            "apply_scene_recipe": self.apply_scene_recipe,
            "add_caption": self.add_caption,
            "update_caption": self.update_caption,
            "remove_caption": self.remove_caption,
            "import_subtitle_file": self.import_subtitle_file,
            "auto_subtitles": self.auto_subtitles,
            "optimize_subtitle_layout": self.optimize_subtitle_layout,
            "add_dialogue_segment": self.add_dialogue_segment,
            "update_dialogue_segment": self.update_dialogue_segment,
            "remove_dialogue_segment": self.remove_dialogue_segment,
            "tag_asset": self.tag_asset,
            "restore_scene": self.restore_scene,
        }

    def operation_schema(self, *, domains: list[str] | None = None, actions: list[str] | None = None) -> dict:
        from .agent_reliability import operation_schema
        return operation_schema(self, domains=domains, actions=actions)

    def agent_context(self, *, scene_ids: list[str] | None = None, domains: list[str] | None = None, include_schema: bool = True) -> dict:
        from .agent_reliability import agent_context
        return agent_context(self, scene_ids=scene_ids, domains=domains, include_schema=include_schema)

    def agent_bootstrap(self, *, task: str | None = None, scene_ids: list[str] | None = None, domains: list[str] | None = None, write: bool = True) -> dict:
        from .runtime import compact_bootstrap
        from . import __version__
        return compact_bootstrap(self, package_version=__version__, task=task, scene_ids=scene_ids, domains=domains, write=write)

    def setup_runtime(self) -> dict:
        from .runtime import setup_runtime
        from . import __version__
        return setup_runtime(self, package_version=__version__)

    def agent_checkpoint(self, *, goal: str | None = None, active_scene_ids: list[str] | None = None, domains: list[str] | None = None, decisions: list[str] | None = None) -> dict:
        from .runtime import save_agent_checkpoint
        return save_agent_checkpoint(self.root, goal=goal, active_scene_ids=active_scene_ids, domains=domains, decisions=decisions)

    def preflight_operations(self, operations, *, expected_project_hash: str | None = None, include_projected_state: bool = False) -> dict:
        from .agent_reliability import preflight_operations
        return preflight_operations(self, operations, expected_project_hash=expected_project_hash, include_projected_state=include_projected_state)

    def apply_agent_operations(self, operations, *, expected_project_hash: str | None = None, dry_run: bool = False, include_project: bool = False) -> dict:
        from .agent_reliability import apply_agent_operations
        return apply_agent_operations(self, operations, expected_project_hash=expected_project_hash, dry_run=dry_run, include_project=include_project)

    @staticmethod
    def _validate_operation_signature(action: str, fn, args: dict) -> None:
        import inspect
        try:
            inspect.signature(fn).bind(**args)
        except TypeError as exc:
            sig = inspect.signature(fn)
            required = [name for name, param in sig.parameters.items() if name != "self" and param.default is inspect._empty and param.kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}]
            accepted = [name for name, param in sig.parameters.items() if name != "self" and param.kind not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}]
            raise AgentCutError(
                "INVALID_OPERATION_ARGS", "Operation arguments do not match the semantic API signature",
                action=action, required=required, accepted=accepted, detail=str(exc),
            ) from exc

    def apply_operation(self, action: str, args: dict | None = None):
        fn = self._operation_map().get(action)
        if fn is None:
            raise AgentCutError("UNSUPPORTED_OPERATION", "Unsupported operation", action=action, allowed=sorted(self._operation_map()))
        payload = args or {}
        if not isinstance(payload, dict):
            raise AgentCutError("INVALID_OPERATION_ARGS", "Operation args must be an object", action=action, value_type=type(payload).__name__)
        self._validate_operation_signature(action, fn, payload)
        return fn(**payload)

    def apply_operations(self, operations: list[dict], *, expected_project_hash: str | None = None, dry_run: bool = False) -> dict:
        """Apply semantic edits atomically.

        `expected_project_hash` provides optimistic concurrency control for agents.
        `dry_run` validates and returns the projected state without writing history/project.json.
        """
        before = deepcopy(self.project)
        before_hash = hash_obj(before)
        if expected_project_hash is not None and expected_project_hash != before_hash:
            raise AgentCutError("STATE_CONFLICT", "Project changed since the agent last read it", expected=expected_project_hash, actual=before_hash)
        if not operations:
            return {"applied": 0, "dry_run": dry_run, "project_hash": before_hash, "project": deepcopy(before), "results": []}

        results = []
        self._batch_mode = True
        try:
            for index, op in enumerate(operations):
                action = op.get("action")
                args = op.get("args", {})
                fn = self._operation_map().get(action)
                if fn is None:
                    raise AgentCutError("UNSUPPORTED_OPERATION", "Unsupported batch operation", index=index, action=action, allowed=sorted(self._operation_map()))
                try:
                    if not isinstance(args, dict):
                        raise AgentCutError("INVALID_OPERATION_ARGS", "Operation args must be an object", index=index, action=action, value_type=type(args).__name__)
                    self._validate_operation_signature(action, fn, args)
                    results.append(fn(**args))
                except AgentCutError as exc:
                    exc.context.setdefault("operation_index", index)
                    exc.context.setdefault("action", action)
                    raise
            validate_project(self.project)
            projected = deepcopy(self.project)
            projected_hash = hash_obj(projected)
            self._batch_mode = False
            if dry_run:
                self.project = before
                return {"applied": len(operations), "dry_run": True, "project_hash": projected_hash, "project": projected, "results": results}
            save_project(self.root, self.project)
            self.history.commit(f"batch:{len(operations)}", self.project)
            return {"applied": len(operations), "dry_run": False, "project_hash": projected_hash, "project": deepcopy(self.project), "results": results}
        except Exception:
            self._batch_mode = False
            self.project = before
            if not dry_run:
                save_project(self.root, self.project)
            raise

    def cache_info(self) -> dict:
        cache = self.root / "cache"
        files = [p for p in cache.glob("**/*") if p.is_file()] if cache.exists() else []
        return {"files": len(files), "bytes": sum(p.stat().st_size for p in files), "path": str(cache)}

    def clear_cache(self) -> dict:
        cache = self.root / "cache"
        removed = self.cache_info()
        if cache.exists():
            shutil.rmtree(cache)
        cache.mkdir(parents=True, exist_ok=True)
        return {"removed_files": removed["files"], "removed_bytes": removed["bytes"], "path": str(cache)}

    def enhancement_status(self) -> dict:
        from .enhance import enhancement_status
        return enhancement_status()

    def install_ai_backend(self, backend: str, *, accept_third_party: bool = False) -> dict:
        from .enhance import install_backend
        return install_backend(backend, accept_third_party=accept_third_party)

    def plan_export(self, *, width: int, height: int, fps: float, container: str = "mp4", codec: str = "h264",
                    encoder: str = "auto", quality: int = 18, upscale: str = "auto", interpolate: str = "auto",
                    content: str = "anime") -> dict:
        from .export import ExportSpec, plan_export
        from .enhance import plan_enhancement
        spec = ExportSpec.normalized(width=width, height=height, fps=fps, container=container, codec=codec, encoder=encoder, quality=quality)
        pv = self.project["video"]
        enhancement = plan_enhancement(
            source_width=int(pv["width"]), source_height=int(pv["height"]), source_fps=float(pv["fps"]),
            target_width=spec.width, target_height=spec.height, target_fps=spec.fps,
            upscale=upscale, interpolate=interpolate, content=content,
        )
        return plan_export(spec, project_video=pv, enhancement_plan=enhancement)

    def export_video(self, *, width: int, height: int, fps: float, container: str = "mp4", codec: str = "h264",
                     encoder: str = "auto", quality: int = 18, upscale: str = "auto", interpolate: str = "auto",
                     content: str = "anime", output: str | Path | None = None, keep_intermediate: bool = False) -> dict:
        """Render and export with independent target format/resolution/fps and optional enhancement.

        `upscale` / `interpolate`: auto | off | ai, or explicit realesrgan / rife.
        Auto uses AI when the optional backend is installed and deterministic FFmpeg fallbacks otherwise.
        """
        import tempfile
        from .enhance import interpolate_video, upscale_video
        from .export import ExportSpec, plan_export, probe_export, transcode_video
        from .render import Renderer

        spec = ExportSpec.normalized(width=width, height=height, fps=fps, container=container, codec=codec, encoder=encoder, quality=quality)
        plan = self.plan_export(width=spec.width, height=spec.height, fps=spec.fps, container=spec.container, codec=spec.codec,
                                encoder=spec.encoder, quality=spec.quality, upscale=upscale, interpolate=interpolate, content=content)
        if output is None:
            output = self.root / "output" / f"AgentCut_{spec.width}x{spec.height}_{spec.fps:g}fps_{spec.codec}.{spec.container}"
        output = Path(output)
        if not output.is_absolute():
            output = self.root / output
        if output.suffix.lower() != f".{spec.container}":
            output = output.with_suffix(f".{spec.container}")
        output.parent.mkdir(parents=True, exist_ok=True)

        pv = self.project["video"]
        need_ai_upscale_stage = spec.width > int(pv["width"]) or spec.height > int(pv["height"])
        need_interp_stage = spec.fps > float(pv["fps"]) + 1e-6
        use_upscale_stage = need_ai_upscale_stage and upscale != "off"
        use_interp_stage = need_interp_stage and interpolate != "off"

        # If an enhancement stage will create the extra pixels/frames, do not make the renderer
        # synthesize them first. Otherwise render directly at the requested export geometry.
        base_w = min(spec.width, int(pv["width"])) if use_upscale_stage else spec.width
        base_h = min(spec.height, int(pv["height"])) if use_upscale_stage else spec.height
        base_fps = min(spec.fps, float(pv["fps"])) if use_interp_stage else spec.fps
        supersample = 1 if base_w >= 3000 or base_h >= 1700 else 2
        hard_cuts = [float(t["start"]) for t in build_timeline(self.project).get("transitions", []) if t.get("type") == "cut"]
        stages = []
        expected_duration = float(build_timeline(self.project).get("duration") or 0.0)

        def duration_guard(path: Path, stage: str, fps_value: float) -> float:
            from .probe import probe_media
            info = probe_media(path)
            actual_duration = float(info.get("duration") or 0.0)
            tolerance = max(0.05, 2.0 / max(float(fps_value), 1.0))
            if expected_duration > 0 and abs(actual_duration - expected_duration) > tolerance:
                raise AgentCutError(
                    "EXPORT_DURATION_DRIFT", "Export stage changed timeline duration beyond tolerance",
                    stage=stage, expected_duration=expected_duration, actual_duration=actual_duration, tolerance=tolerance, path=str(path),
                )
            return actual_duration

        temp_ctx = tempfile.TemporaryDirectory(prefix="agentcut_export_", dir=str(self.root / "cache"))
        work = Path(temp_ctx.name)
        try:
            master = work / "master.mp4"
            Renderer(self.root, deepcopy(self.project)).render(
                profile="final", output=master,
                profile_override={"width": base_w, "height": base_h, "fps": base_fps, "crf": 12, "preset": "fast", "camera_supersample": supersample, "allow_canvas_upscale": True},
            )
            current = master
            master_duration = duration_guard(master, "semantic_render", base_fps)
            stages.append({"stage": "semantic_render", "output": str(master), "width": base_w, "height": base_h, "fps": base_fps, "duration": master_duration})

            if use_interp_stage:
                nxt = work / "interpolated.mp4"
                result = interpolate_video(current, nxt, target_fps=spec.fps, backend=interpolate, hard_cut_times=hard_cuts, uhd=(base_w >= 3000))
                result["duration"] = duration_guard(nxt, "frame_interpolation", spec.fps)
                stages.append({"stage": "frame_interpolation", **result})
                current = nxt

            if use_upscale_stage:
                nxt = work / "upscaled.mp4"
                model = "anime" if content == "anime" else "general"
                result = upscale_video(current, nxt, width=spec.width, height=spec.height, backend=upscale, model=model)
                result["duration"] = duration_guard(nxt, "super_resolution", spec.fps if use_interp_stage else base_fps)
                stages.append({"stage": "super_resolution", **result})
                current = nxt

            transcode_video(current, output, spec)
            actual = probe_export(output)
            duration_guard(output, "final_encode", spec.fps)
            if int(actual.get("width") or 0) != spec.width or int(actual.get("height") or 0) != spec.height or abs(float(actual.get("fps") or 0) - spec.fps) > 1e-3:
                raise AgentCutError("EXPORT_SPEC_MISMATCH", "Final export does not match requested geometry/frame rate", requested=spec.as_dict(), actual=actual)
            stages.append({"stage": "encode", "encoder": plan["encoder"], "output": str(output)})
            manifest = output.with_suffix(output.suffix + ".agentcut-export.json")
            from . import __version__
            payload = {"version": __version__, "output": str(output), "plan": plan, "stages": stages, "actual": actual}
            manifest.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            if keep_intermediate:
                saved = self.root / "output" / (output.stem + "_intermediates")
                if saved.exists():
                    shutil.rmtree(saved)
                shutil.copytree(work, saved)
                payload["intermediates"] = str(saved)
            return payload
        finally:
            temp_ctx.cleanup()

    def render_proxy(self, output: str | Path | None = None) -> Path:
        """Very cheap full-timeline diagnostic render for Agent iteration (640x360/12fps, no supersampling)."""
        from .render import Renderer
        return Renderer(self.root, deepcopy(self.project)).render(profile="proxy", output=output)

    def render_preview(self, output: str | Path | None = None) -> Path:
        from .render import Renderer
        return Renderer(self.root, deepcopy(self.project)).render(profile="preview", output=output)

    def render_final(self, output: str | Path | None = None) -> Path:
        from .render import Renderer
        return Renderer(self.root, deepcopy(self.project)).render(profile="final", output=output)

    def render_4k60(self, output: str | Path | None = None) -> Path:
        from .render import Renderer
        return Renderer(self.root, deepcopy(self.project)).render(profile="uhd_4k60", output=output)

    def render_profile(self, profile: str, output: str | Path | None = None) -> Path:
        from .render import Renderer
        return Renderer(self.root, deepcopy(self.project)).render(profile=profile, output=output)

    def render_showcase(self, output: str | Path | None = None) -> Path:
        from .render import Renderer
        return Renderer(self.root, deepcopy(self.project)).render(profile="showcase", output=output)

    def render_scene(self, scene_id: str, output: str | Path | None = None, profile="preview") -> Path:
        from .render import Renderer
        return Renderer(self.root, deepcopy(self.project)).render_single_scene(scene_id, profile=profile, output=output)

    def render_span(self, start_scene: str, end_scene: str, output: str | Path | None = None, *, profile="preview") -> Path:
        """Render a contiguous scene range for transition/motion QA without touching project state.

        The span is intentionally visual-only in v0.1.3. Global audio/captions are omitted so
        an agent can iterate quickly on a problematic transition without re-rendering the full edit.
        """
        scenes = self.project.get("scenes", [])
        start_idx = next((i for i, s in enumerate(scenes) if s.get("id") == start_scene), None)
        end_idx = next((i for i, s in enumerate(scenes) if s.get("id") == end_scene), None)
        if start_idx is None or end_idx is None:
            raise AgentCutError("SCENE_NOT_FOUND", "Unknown span boundary", start_scene=start_scene, end_scene=end_scene)
        if start_idx > end_idx:
            raise AgentCutError("INVALID_SCENE_SPAN", "start_scene must not come after end_scene", start_scene=start_scene, end_scene=end_scene)
        sub = deepcopy(self.project)
        sub["scenes"] = deepcopy(scenes[start_idx:end_idx + 1])
        # The last scene's outgoing transition points outside the span and must not be rendered.
        if sub["scenes"]:
            sub["scenes"][-1]["transition_out"] = {"type": "cut", "duration": 0.0}
        sub["audio_tracks"] = []
        for scene in sub["scenes"]:
            scene["audio"] = []
        sub["captions"] = []
        from .render import Renderer
        if output is None:
            output = self.root / "preview" / f"span_{start_scene}_to_{end_scene}_{profile}.mp4"
        return Renderer(self.root, sub).render(profile=profile, output=output)

    def extract_frame(self, video: str | Path, output: str | Path, *, time: float) -> Path:
        from .inspect import extract_frame
        return extract_frame(Path(video), Path(output), time=float(time))

    def contact_sheet(self, video: str | Path, output: str | Path, *, interval: float = 2.0) -> Path:
        from .inspect import inspect_contact_sheet
        return inspect_contact_sheet(Path(video), Path(output), interval=float(interval))

    def qa(self, rendered: str | Path | None = None) -> dict:
        from .qa import run_qa
        return run_qa(self.root, deepcopy(self.project), Path(rendered) if rendered else None)
