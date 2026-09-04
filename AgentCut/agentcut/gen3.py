from __future__ import annotations

import json
import math
from pathlib import Path
from copy import deepcopy

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .errors import AgentCutError

GEN3_MODULE_VERSION = "1.0"
GEN3_SCENE_KINDS = {"exhibit", "info_card", "return", "montage", "silence", "quote"}

DEFAULT_CONFIG = {
    "enabled": True,
    "module_version": GEN3_MODULE_VERSION,
    "target_profile": "uhd_4k30",
    "default_motion": "static",
    "stillness_first": True,
    "actor_matte_key": "#FF00FF",
    "tile_refinement": {"rows": 2, "cols": 2, "overlap": 0.12},
    "renderer": "remotion_bridge",
    "fallback_renderer": "ffmpeg",
}


def normalize_hex_color(value: str) -> tuple[int, int, int]:
    s = str(value).strip().lstrip("#")
    if len(s) != 6:
        raise AgentCutError("INVALID_COLOR", "Expected #RRGGBB color", value=value)
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise AgentCutError("INVALID_COLOR", "Expected #RRGGBB color", value=value) from exc


def normalize_config(config: dict | None = None) -> dict:
    out = deepcopy(DEFAULT_CONFIG)
    config = config or {}
    if not isinstance(config, dict):
        raise AgentCutError("INVALID_GEN3_CONFIG", "Gen3 config must be an object")
    for key, value in config.items():
        if key == "tile_refinement":
            if not isinstance(value, dict):
                raise AgentCutError("INVALID_GEN3_CONFIG", "tile_refinement must be an object")
            out[key].update(value)
        else:
            out[key] = value
    if out["default_motion"] not in {"static", "slow_push", "slow_pull", "pan_left", "pan_right", "pan_up", "pan_down"}:
        raise AgentCutError("INVALID_GEN3_CONFIG", "Unsupported Gen3 default motion", motion=out["default_motion"])
    normalize_hex_color(out["actor_matte_key"])
    tile = out["tile_refinement"]
    rows, cols, overlap = int(tile.get("rows", 2)), int(tile.get("cols", 2)), float(tile.get("overlap", 0.12))
    if rows < 1 or cols < 1 or rows > 8 or cols > 8 or not 0 <= overlap < 0.5:
        raise AgentCutError("INVALID_GEN3_CONFIG", "Invalid tile refinement geometry", rows=rows, cols=cols, overlap=overlap)
    tile.update({"rows": rows, "cols": cols, "overlap": overlap})
    return out


def wrap_card_text(text: str, max_chars: int = 28, max_lines: int = 2) -> str:
    raw = " ".join(str(text or "").split())
    if not raw:
        return ""
    # CJK-friendly deterministic wrapping by visible characters, while preserving short words.
    lines, current = [], ""
    for ch in raw:
        if ch == "\n":
            if current:
                lines.append(current.rstrip())
                current = ""
            continue
        current += ch
        if len(current) >= max_chars:
            lines.append(current.rstrip())
            current = ""
            if len(lines) >= max_lines:
                break
    if current and len(lines) < max_lines:
        lines.append(current.rstrip())
    if len("".join(lines)) < len(raw) and lines:
        lines[-1] = lines[-1].rstrip("。.!！?？,，;；:： ") + "…"
    return "\n".join(lines[:max_lines])


def category_layers(category: str, *, width: int, height: int, duration: float, z: int = 80) -> list[dict]:
    sx, sy = width / 1920.0, height / 1080.0
    label = str(category).strip()
    return [
        {
            "id": "gen3_category_bg", "type": "rect", "start": 0.0, "duration": float(duration),
            "x": 72 * sx, "y": 58 * sy, "width": int(250 * sx), "height": int(62 * sy),
            "scale": 1.0, "opacity": 1.0, "rotation": 0.0, "z": z,
            "fill": "#111722B8", "radius": int(14 * min(sx, sy)), "keyframes": [],
        },
        {
            "id": "gen3_category_text", "type": "text", "start": 0.0, "duration": float(duration),
            "x": 96 * sx, "y": 72 * sy, "scale": 1.0, "opacity": 1.0, "rotation": 0.0, "z": z + 1,
            "text": label, "font_size": max(22, int(28 * sy)), "bold": True, "color": "#F5F7FA",
            "outline": 0, "keyframes": [],
        },
    ]


def info_card_layers(title: str, subtitle: str | None, body: str, *, width: int, height: int, start: float, duration: float, z: int = 100) -> list[dict]:
    sx, sy = width / 1920.0, height / 1080.0
    card_w, card_h = int(1170 * sx), int(300 * sy)
    x, y = 375 * sx, 630 * sy
    wrapped = wrap_card_text(body, max_chars=30 if width >= 1920 else 24, max_lines=2)
    layers = [
        {
            "id": "gen3_card_bg", "type": "rect", "start": float(start), "duration": float(duration),
            "x": x, "y": y, "width": card_w, "height": card_h, "scale": 1.0,
            "opacity": 1.0, "rotation": 0.0, "z": z, "fill": "#10151EDB",
            "radius": int(22 * min(sx, sy)), "outline_color": "#FFFFFF20", "outline_width": max(1, int(2 * sx)),
            "keyframes": [{"t": 0.0, "opacity": 0.0, "y": y + 18 * sy}, {"t": 0.10, "opacity": 1.0, "y": y, "easing": "ease_out"}, {"t": 0.90, "opacity": 1.0, "y": y}, {"t": 1.0, "opacity": 0.0, "y": y - 10 * sy, "easing": "ease_in"}],
        },
        {
            "id": "gen3_card_title", "type": "text", "start": float(start), "duration": float(duration),
            "x": x + 52 * sx, "y": y + 44 * sy, "scale": 1.0, "opacity": 1.0, "rotation": 0.0, "z": z + 1,
            "text": str(title), "font_size": max(30, int(46 * sy)), "bold": True, "color": "#FFFFFF", "outline": 0,
            "keyframes": [{"t": 0.0, "opacity": 0.0}, {"t": 0.12, "opacity": 1.0, "easing": "ease_out"}, {"t": 0.90, "opacity": 1.0}, {"t": 1.0, "opacity": 0.0}],
        },
        {
            "id": "gen3_card_body", "type": "text", "start": float(start), "duration": float(duration),
            "x": x + 52 * sx, "y": y + 142 * sy, "scale": 1.0, "opacity": 1.0, "rotation": 0.0, "z": z + 1,
            "text": wrapped, "font_size": max(24, int(34 * sy)), "bold": False, "color": "#E8EBF0", "outline": 0, "spacing": max(5, int(8 * sy)),
            "keyframes": [{"t": 0.0, "opacity": 0.0}, {"t": 0.15, "opacity": 1.0, "easing": "ease_out"}, {"t": 0.90, "opacity": 1.0}, {"t": 1.0, "opacity": 0.0}],
        },
    ]
    if subtitle:
        layers.insert(2, {
            "id": "gen3_card_subtitle", "type": "text", "start": float(start), "duration": float(duration),
            "x": x + 54 * sx, "y": y + 100 * sy, "scale": 1.0, "opacity": 1.0, "rotation": 0.0, "z": z + 1,
            "text": str(subtitle), "font_size": max(20, int(25 * sy)), "bold": False, "color": "#AEB7C5", "outline": 0,
            "keyframes": [{"t": 0.0, "opacity": 0.0}, {"t": 0.14, "opacity": 1.0}, {"t": 0.90, "opacity": 1.0}, {"t": 1.0, "opacity": 0.0}],
        })
    return layers


def tile_plan(width: int, height: int, *, rows: int = 2, cols: int = 2, overlap: float = 0.12) -> dict:
    width, height, rows, cols = int(width), int(height), int(rows), int(cols)
    overlap = float(overlap)
    if width < 2 or height < 2 or rows < 1 or cols < 1 or not 0 <= overlap < 0.5:
        raise AgentCutError("INVALID_TILE_PLAN", "Invalid tile plan parameters")
    base_w, base_h = width / cols, height / rows
    pad_x, pad_y = base_w * overlap / 2, base_h * overlap / 2
    tiles = []
    for r in range(rows):
        for c in range(cols):
            x0 = max(0, int(math.floor(c * base_w - pad_x)))
            y0 = max(0, int(math.floor(r * base_h - pad_y)))
            x1 = min(width, int(math.ceil((c + 1) * base_w + pad_x)))
            y1 = min(height, int(math.ceil((r + 1) * base_h + pad_y)))
            tiles.append({"id": f"r{r+1}c{c+1}", "row": r, "col": c, "box": [x0, y0, x1, y1], "size": [x1-x0, y1-y0], "position_hint": ["top" if r == 0 else "bottom", "left" if c == 0 else "right"]})
    return {"canvas": [width, height], "rows": rows, "cols": cols, "overlap": overlap, "tiles": tiles}


def stitch_tiles(tile_paths: list[str | Path], output_path: str | Path, *, rows: int = 2, cols: int = 2, overlap: float = 0.12) -> Path:
    if len(tile_paths) != rows * cols:
        raise AgentCutError("INVALID_TILE_SET", "Tile count does not match rows*cols", count=len(tile_paths), expected=rows*cols)
    images = [Image.open(Path(p)).convert("RGB") for p in tile_paths]
    tw, th = images[0].size
    if any(im.size != (tw, th) for im in images):
        raise AgentCutError("INVALID_TILE_SET", "All tiles must have identical dimensions for deterministic stitch")
    step_x = max(1, int(round(tw * (1 - overlap))))
    step_y = max(1, int(round(th * (1 - overlap))))
    canvas_w, canvas_h = step_x * (cols - 1) + tw, step_y * (rows - 1) + th
    accum = np.zeros((canvas_h, canvas_w, 3), dtype=np.float64)
    weights = np.zeros((canvas_h, canvas_w, 1), dtype=np.float64)
    edge_x = max(1, tw - step_x)
    edge_y = max(1, th - step_y)
    wx = np.ones(tw, dtype=np.float64)
    wy = np.ones(th, dtype=np.float64)
    if edge_x > 1:
        ramp = np.linspace(0.05, 1.0, edge_x, dtype=np.float64)
        wx[:edge_x] = ramp; wx[-edge_x:] = ramp[::-1]
    if edge_y > 1:
        ramp = np.linspace(0.05, 1.0, edge_y, dtype=np.float64)
        wy[:edge_y] = ramp; wy[-edge_y:] = ramp[::-1]
    wmap = (wy[:, None] * wx[None, :])[..., None]
    for i, im in enumerate(images):
        r, c = divmod(i, cols); x, y = c * step_x, r * step_y
        arr = np.asarray(im, dtype=np.float64)
        accum[y:y+th, x:x+tw] += arr * wmap
        weights[y:y+th, x:x+tw] += wmap
    out = np.clip(accum / np.maximum(weights, 1e-9), 0, 255).astype(np.uint8)
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, mode="RGB").save(output)
    return output


def chroma_key_image(input_path: str | Path, output_path: str | Path, *, key_color: str = "#FF00FF", inner: float = 28.0, outer: float = 95.0, despill: float = 0.55) -> Path:
    if not 0 <= inner < outer:
        raise AgentCutError("INVALID_CHROMA_RANGE", "Chroma thresholds must satisfy 0 <= inner < outer", inner=inner, outer=outer)
    if not 0 <= despill <= 1:
        raise AgentCutError("INVALID_CHROMA_DESPILL", "despill must be in [0,1]", despill=despill)
    key = np.asarray(normalize_hex_color(key_color), dtype=np.float32)
    im = Image.open(Path(input_path)).convert("RGBA")
    arr = np.asarray(im, dtype=np.float32)
    rgb = arr[..., :3]
    dist = np.linalg.norm(rgb - key[None, None, :], axis=2)
    alpha = np.clip((dist - inner) / (outer - inner), 0.0, 1.0)
    # Ignore AI-provided alpha by design: Gen3 rebuilds a deterministic matte from the key color.
    key_strength = (1.0 - alpha)[..., None] * float(despill)
    neutral = rgb.mean(axis=2, keepdims=True)
    keyed_channels = key / 255.0
    # Pull key-heavy border pixels slightly toward neutral to reduce magenta/blue spill.
    rgb2 = rgb * (1.0 - key_strength * keyed_channels) + neutral * (key_strength * keyed_channels)
    out = np.dstack([np.clip(rgb2, 0, 255), np.clip(alpha * 255.0, 0, 255)]).astype(np.uint8)
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, mode="RGBA").save(output)
    return output


def remotion_manifest(project: dict) -> dict:
    scenes = []
    for scene in project.get("scenes", []):
        scenes.append({
            "id": scene.get("id"), "asset_id": scene.get("asset_id"), "duration": scene.get("duration"),
            "camera": deepcopy(scene.get("camera") or {}), "composition": deepcopy(scene.get("composition") or {}),
            "filters": deepcopy(scene.get("filters") or []), "effects": deepcopy(scene.get("effects") or []),
            "layers": deepcopy(scene.get("layers") or []), "transition_out": deepcopy(scene.get("transition_out") or {}),
            "gen3": deepcopy(scene.get("gen3") or {}),
        })
    return {
        "schema": "agentcut-gen3-remotion-v1", "video": deepcopy(project.get("video") or {}),
        "gen3": normalize_config(project.get("gen3") or {}), "assets": deepcopy(project.get("assets") or {}),
        "scenes": scenes, "captions": deepcopy(project.get("captions") or []),
        "dialogue_segments": deepcopy(project.get("dialogue_segments") or []), "audio_tracks": deepcopy(project.get("audio_tracks") or []),
    }


def write_remotion_manifest(project: dict, path: str | Path) -> Path:
    output = Path(path); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(remotion_manifest(project), ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def validate_scene_gen3(value: dict | None, *, scene_duration: float | None = None) -> dict:
    """Validate scene-level Gen3/Jane3 semantic metadata."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise AgentCutError("INVALID_GEN3_SCENE", "scene.gen3 must be an object")
    out = deepcopy(value)
    kind = str(out.get("kind", "exhibit"))
    if kind not in GEN3_SCENE_KINDS:
        raise AgentCutError("INVALID_GEN3_SCENE", "Unsupported Gen3 scene kind", kind=kind, allowed=sorted(GEN3_SCENE_KINDS))
    out["kind"] = kind
    for field in ("category", "work_title", "author"):
        if field in out and out[field] is not None and not isinstance(out[field], str):
            raise AgentCutError("INVALID_GEN3_SCENE", f"{field} must be a string", field=field)
    motion = str(out.get("motion", "static"))
    if motion not in {"static", "slow_push", "slow_pull", "pan_left", "pan_right", "pan_up", "pan_down"}:
        raise AgentCutError("INVALID_GEN3_SCENE", "Unsupported Gen3 motion", motion=motion)
    out["motion"] = motion
    card = out.get("card")
    if card is not None:
        if not isinstance(card, dict):
            raise AgentCutError("INVALID_GEN3_SCENE", "scene.gen3.card must be an object")
        title = str(card.get("title", "")).strip()
        body = str(card.get("body", "")).strip()
        if not title or not body:
            raise AgentCutError("INVALID_GEN3_SCENE", "Gen3 card needs non-empty title and body")
        start = float(card.get("start", 0.0)); duration = float(card.get("duration", 3.2))
        if start < 0 or duration <= 0:
            raise AgentCutError("INVALID_GEN3_SCENE", "Invalid Gen3 card timing", start=start, duration=duration)
        if scene_duration is not None and start + duration > float(scene_duration) + 1e-6:
            raise AgentCutError("INVALID_GEN3_SCENE", "Gen3 card extends past scene end", start=start, duration=duration, scene_duration=scene_duration)
        card["start"], card["duration"], card["blur"] = start, duration, bool(card.get("blur", True))
    actors = out.get("actors", [])
    if not isinstance(actors, list):
        raise AgentCutError("INVALID_GEN3_SCENE", "scene.gen3.actors must be an array")
    for i, actor in enumerate(actors):
        if not isinstance(actor, dict):
            raise AgentCutError("INVALID_GEN3_SCENE", "Gen3 actor rows must be objects", index=i)
        if not str(actor.get("asset_id", "")).strip():
            raise AgentCutError("INVALID_GEN3_SCENE", "Gen3 actor needs asset_id", index=i)
        for field, default in (("x", 0.5), ("y", 1.0), ("scale", 1.0), ("opacity", 1.0)):
            value = float(actor.get(field, default))
            if field in {"x", "y", "opacity"} and not 0 <= value <= 1:
                raise AgentCutError("INVALID_GEN3_SCENE", f"Actor {field} must be in [0,1]", index=i, value=value)
            if field == "scale" and not 0.05 <= value <= 8:
                raise AgentCutError("INVALID_GEN3_SCENE", "Actor scale out of range", index=i, value=value)
            actor[field] = value
    return out


def make_blurred_background(input_path: str | Path, output_path: str | Path, *, width: int, height: int, radius: float = 18.0, darken: float = 0.78) -> Path:
    if width <= 0 or height <= 0 or radius < 0 or not 0 < darken <= 1:
        raise AgentCutError("INVALID_GEN3_BLUR", "Invalid blur parameters")
    src = Image.open(Path(input_path)).convert("RGB")
    fit = ImageOps.fit(src, (int(width), int(height)), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    if radius:
        fit = fit.filter(ImageFilter.GaussianBlur(float(radius)))
    if darken < 1:
        arr = np.asarray(fit, dtype=np.float32) * float(darken)
        fit = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True); fit.save(output)
    return output


def make_actor_shadow(input_rgba: str | Path, output_path: str | Path, *, blur_radius: float = 18.0, opacity: float = 0.24, squash: float = 0.16) -> Path:
    if blur_radius < 0 or not 0 <= opacity <= 1 or not 0.03 <= squash <= 1:
        raise AgentCutError("INVALID_GEN3_SHADOW", "Invalid actor shadow parameters")
    src = Image.open(Path(input_rgba)).convert("RGBA")
    alpha = src.getchannel("A")
    h = max(2, int(round(src.height * float(squash))))
    alpha = alpha.resize((src.width, h), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(float(blur_radius)))
    alpha = alpha.point(lambda v: int(v * float(opacity)))
    shadow = Image.new("RGBA", (src.width, h), (0, 0, 0, 0)); shadow.putalpha(alpha)
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True); shadow.save(output)
    return output


def remotion_bridge_files() -> dict[str, str]:
    package = '''{\n  "name": "agentcut-gen3-remotion-bridge",\n  "private": true,\n  "scripts": {"render": "remotion render src/index.ts Gen3 out/gen3.mp4"},\n  "dependencies": {"@remotion/cli": "latest", "remotion": "latest", "react": "latest", "react-dom": "latest"},\n  "devDependencies": {"typescript": "latest"}\n}\n'''
    index = 'import {registerRoot} from "remotion";\nimport {Root} from "./Root";\nregisterRoot(Root);\n'
    root = '''import React from "react";\nimport {Composition} from "remotion";\nimport {Gen3} from "./Gen3";\nconst manifest = require("../public/manifest.json");\nexport const Root: React.FC = () => { const fps=manifest.video.fps||30; const frames=Math.ceil((manifest.scenes||[]).reduce((a:any,s:any)=>a+Number(s.duration||0),0)*fps); return <Composition id="Gen3" component={Gen3} durationInFrames={Math.max(frames,1)} fps={fps} width={manifest.video.width} height={manifest.video.height} defaultProps={{manifest}}/>; };\n'''
    gen3 = '''import React from "react";\nimport {AbsoluteFill, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";\nconst txt=(v:any)=>String(v??"");\nconst Scene:React.FC<{s:any}> = ({s}) => { const frame=useCurrentFrame(); const {fps,width,height}=useVideoConfig(); const g=s.gen3||{}; const card=g.card; const bg=s.asset_path?staticFile(s.asset_path):null; const sceneFrames=Math.max(1,Math.round(Number(s.duration||1)*fps)); const motion=g.motion||"static"; let scale=1; if(motion==="slow_push") scale=interpolate(frame,[0,sceneFrames],[1,1.035]); if(motion==="slow_pull") scale=interpolate(frame,[0,sceneFrames],[1.035,1]); const cardStart=card?Math.round(Number(card.start||0)*fps):0; const cardEnd=card?cardStart+Math.round(Number(card.duration||0)*fps):0; const show=!!card && frame>=cardStart && frame<cardEnd; return <AbsoluteFill style={{backgroundColor:"black",overflow:"hidden"}}>{bg&&<Img src={bg} style={{width:"100%",height:"100%",objectFit:"cover",transform:`scale(${scale})`,filter:show&&card.blur!==false?"blur(18px) brightness(.72)":"none"}}/>}{(g.actors||[]).map((a:any,i:number)=><Img key={i} src={staticFile(a.asset_path)} style={{position:"absolute",left:`${Number(a.x||0)*100}%`,top:`${Number(a.y||0)*100}%`,transform:`translate(-50%,-100%) scale(${Number(a.scale||1)})`,opacity:Number(a.opacity??1),transformOrigin:"50% 100%"}}/>)}{g.category&&<div style={{position:"absolute",left:width*.0375,top:height*.054,padding:`${height*.013}px ${width*.012}px`,background:"rgba(17,23,34,.72)",borderRadius:height*.013,color:"#f5f7fa",fontWeight:700,fontSize:height*.026,fontFamily:"sans-serif"}}>{txt(g.category)}</div>}{show&&<div style={{position:"absolute",left:"19.5%",right:"19.5%",bottom:"13.8%",padding:`${height*.035}px ${width*.027}px`,background:"rgba(16,21,30,.88)",border:"1px solid rgba(255,255,255,.12)",borderRadius:height*.02,color:"white",fontFamily:"sans-serif"}}><div style={{fontSize:height*.043,fontWeight:700}}>{txt(card.title)}</div>{card.subtitle&&<div style={{fontSize:height*.023,color:"#aeb7c5",marginTop:height*.008}}>{txt(card.subtitle)}</div>}<div style={{whiteSpace:"pre-line",fontSize:height*.031,color:"#e8ebf0",marginTop:height*.018,lineHeight:1.45}}>{txt(card.body)}</div></div>}</AbsoluteFill>};\nexport const Gen3:React.FC<{manifest:any}> = ({manifest}) => { const {fps}=useVideoConfig(); let from=0; return <AbsoluteFill>{(manifest.scenes||[]).map((s:any)=>{const n=Math.max(1,Math.round(Number(s.duration||1)*fps)); const seq=<Sequence key={s.id} from={from} durationInFrames={n}><Scene s={s}/></Sequence>; from+=n; return seq;})}</AbsoluteFill>};\n'''
    return {"package.json": package, "src/index.ts": index, "src/Root.tsx": root, "src/Gen3.tsx": gen3}


def write_remotion_bundle(project: dict, project_root: str | Path, output_dir: str | Path) -> Path:
    root = Path(project_root); out = Path(output_dir); public = out / "public"; assets_out = public / "assets"
    assets_out.mkdir(parents=True, exist_ok=True)
    manifest = remotion_manifest(project); copied = {}
    for aid, asset in (project.get("assets") or {}).items():
        if asset.get("type") not in {"image", "video", "audio"}: continue
        src = Path(asset.get("path", "")); src = src if src.is_absolute() else root / src
        if not src.exists(): continue
        safe = f"{aid}_{src.name}".replace(" ", "_"); dst = assets_out / safe
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            import shutil; shutil.copy2(src, dst)
        copied[aid] = f"assets/{safe}"
    for scene in manifest.get("scenes", []):
        aid = scene.get("asset_id"); scene["asset_path"] = copied.get(aid)
        for actor in (scene.get("gen3") or {}).get("actors", []): actor["asset_path"] = copied.get(actor.get("asset_id"))
    (public / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for rel, content in remotion_bridge_files().items():
        target = out / rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content, encoding="utf-8")
    (out / "out").mkdir(exist_ok=True)
    return out


def extract_tiles(input_path: str | Path, output_dir: str | Path, *, rows: int = 2, cols: int = 2, overlap: float = 0.12) -> dict:
    """Extract overlap tiles from a composition master for external AI refinement.

    Returns a machine-readable manifest with positional/continuity hints. Refined outputs
    should preserve each tile's exact pixel size so `stitch_tiles` can blend them deterministically.
    """
    src = Image.open(Path(input_path)).convert("RGB")
    plan = tile_plan(src.width, src.height, rows=rows, cols=cols, overlap=overlap)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    records=[]
    for tile in plan["tiles"]:
        x0,y0,x1,y1=tile["box"]
        crop=src.crop((x0,y0,x1,y1))
        path=out/f'{tile["id"]}.png'; crop.save(path)
        records.append({**tile,"path":path.name,"prompt_hint":f'Refine the {" / ".join(tile["position_hint"])} tile of one continuous image. Preserve geometry, lighting, perspective, road/building/sky continuity across overlap boundaries; add detail only, do not redesign composition.'})
    manifest={**plan,"source":str(Path(input_path)),"tiles":records,"rule":"Refined tiles must keep the exact input tile dimensions and overlap content."}
    (out/'tile_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest
