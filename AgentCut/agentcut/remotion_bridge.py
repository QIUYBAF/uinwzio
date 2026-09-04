from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from .errors import AgentCutError
from .util import file_sha256, hash_obj

MANIFEST_SCHEMA = "agentcut.remotion.manifest.v2"
BRIDGE_VERSION = 2
REMOTION_VERSION = "4.0.506"
REACT_VERSION = "19.2.0"
TYPESCRIPT_VERSION = "5.9.2"
_COMPONENT_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_ALLOWED_PROP_TYPES = {"string", "number", "integer", "boolean", "array", "object"}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _frame(value: float, fps: int) -> int:
    return max(0, int(round(float(value) * fps)))


def normalize_props_schema(value: dict | None) -> dict:
    if value is None:
        return {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    if not isinstance(value, dict) or value.get("type", "object") != "object":
        raise AgentCutError("INVALID_REMOTION_COMPONENT", "props_schema must be a JSON-schema object")
    properties = value.get("properties", {})
    required = value.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise AgentCutError("INVALID_REMOTION_COMPONENT", "Invalid props_schema properties/required")
    normalized: dict[str, dict] = {}
    for name, rule in properties.items():
        if not isinstance(name, str) or not name or not isinstance(rule, dict):
            raise AgentCutError("INVALID_REMOTION_COMPONENT", "Invalid props_schema property", property=name)
        prop_type = rule.get("type")
        if prop_type not in _ALLOWED_PROP_TYPES:
            raise AgentCutError("INVALID_REMOTION_COMPONENT", "Unsupported prop type", property=name, type=prop_type)
        normalized[name] = deepcopy(rule)
    missing = [name for name in required if name not in normalized]
    if missing:
        raise AgentCutError("INVALID_REMOTION_COMPONENT", "Required props missing from properties", missing=missing)
    return {
        "type": "object",
        "properties": normalized,
        "required": list(dict.fromkeys(required)),
        "additionalProperties": bool(value.get("additionalProperties", False)),
    }


def validate_props(props: dict | None, schema: dict) -> dict:
    props = {} if props is None else deepcopy(props)
    if not isinstance(props, dict):
        raise AgentCutError("INVALID_REMOTION_BINDING", "props must be an object")
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    missing = [name for name in required if name not in props]
    if missing:
        raise AgentCutError("INVALID_REMOTION_BINDING", "Required component props are missing", missing=missing)
    if not schema.get("additionalProperties", False):
        extra = sorted(set(props) - set(properties))
        if extra:
            raise AgentCutError("INVALID_REMOTION_BINDING", "Unregistered component props", extra=extra)
    for name, value in props.items():
        rule = properties.get(name)
        if not rule:
            continue
        kind = rule["type"]
        ok = {
            "string": isinstance(value, str),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "array": isinstance(value, list),
            "object": isinstance(value, dict),
        }[kind]
        if not ok:
            raise AgentCutError("INVALID_REMOTION_BINDING", "Component prop has wrong type", property=name, expected=kind)
    return props


def validate_remotion_state(project: dict) -> None:
    state = project.get("remotion")
    if state is None:
        return
    if not isinstance(state, dict):
        raise AgentCutError("INVALID_PROJECT", "remotion must be an object")
    components = state.get("components", {})
    bindings = state.get("bindings", [])
    if not isinstance(components, dict) or not isinstance(bindings, list):
        raise AgentCutError("INVALID_PROJECT", "remotion.components/bindings have invalid types")
    scene_map = {s.get("id"): s for s in project.get("scenes", [])}
    for component_id, row in components.items():
        if not _COMPONENT_ID.fullmatch(str(component_id)) or not isinstance(row, dict):
            raise AgentCutError("INVALID_PROJECT", "Invalid Remotion component", component_id=component_id)
        if row.get("id") != component_id:
            raise AgentCutError("INVALID_PROJECT", "Remotion component id mismatch", component_id=component_id)
        if not isinstance(row.get("source_path"), str) or not row["source_path"]:
            raise AgentCutError("INVALID_PROJECT", "Remotion component needs source_path", component_id=component_id)
        if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("source_sha256", ""))):
            raise AgentCutError("INVALID_PROJECT", "Remotion component needs source_sha256", component_id=component_id)
        normalize_props_schema(row.get("props_schema"))
    seen: set[str] = set()
    for index, row in enumerate(bindings):
        if not isinstance(row, dict):
            raise AgentCutError("INVALID_PROJECT", "Remotion bindings must be objects", index=index)
        binding_id = str(row.get("id", ""))
        if not binding_id or binding_id in seen:
            raise AgentCutError("INVALID_PROJECT", "Remotion binding ids must be unique", binding_id=binding_id)
        seen.add(binding_id)
        component_id = row.get("component_id")
        scene_id = row.get("scene_id")
        if component_id not in components or scene_id not in scene_map:
            raise AgentCutError("INVALID_PROJECT", "Remotion binding references missing scene/component", binding_id=binding_id)
        start, duration = float(row.get("start", 0)), float(row.get("duration", 0))
        if start < 0 or duration <= 0 or start + duration > float(scene_map[scene_id].get("duration", 0)) + 1e-9:
            raise AgentCutError("INVALID_PROJECT", "Remotion binding timing escapes its scene", binding_id=binding_id)
        validate_props(row.get("props"), normalize_props_schema(components[component_id].get("props_schema")))


def register_component(project: dict, project_root: Path, source_path: str | Path, *, component_id: str,
                       export_name: str = "default", props_schema: dict | None = None) -> dict:
    if not _COMPONENT_ID.fullmatch(component_id):
        raise AgentCutError("INVALID_REMOTION_COMPONENT", "Invalid component_id", component_id=component_id)
    src = Path(source_path)
    if not src.is_absolute():
        src = (project_root / src).resolve()
    if not src.exists() or not src.is_file() or src.suffix.lower() not in {".tsx", ".ts", ".jsx", ".js"}:
        raise AgentCutError("INVALID_REMOTION_COMPONENT", "Component source must be an existing TS/JS module", path=str(src))
    if not re.fullmatch(r"default|[A-Za-z_$][A-Za-z0-9_$]*", export_name):
        raise AgentCutError("INVALID_REMOTION_COMPONENT", "Invalid export_name", export_name=export_name)
    dst_dir = project_root / "assets" / "remotion_components"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{component_id}{src.suffix.lower()}"
    shutil.copy2(src, dst)
    row = {
        "id": component_id,
        "source_path": dst.relative_to(project_root).as_posix(),
        "source_sha256": file_sha256(dst),
        "export_name": export_name,
        "props_schema": normalize_props_schema(props_schema),
    }
    project.setdefault("remotion", {}).setdefault("components", {})[component_id] = row
    project["remotion"].setdefault("bindings", [])
    validate_remotion_state(project)
    return deepcopy(row)


def bind_component(project: dict, *, scene_id: str, component_id: str, start: float, duration: float,
                   props: dict | None = None, z: int = 50, binding_id: str | None = None) -> dict:
    state = project.setdefault("remotion", {"components": {}, "bindings": []})
    components = state.setdefault("components", {})
    scene = next((s for s in project.get("scenes", []) if s.get("id") == scene_id), None)
    if scene is None or component_id not in components:
        raise AgentCutError("INVALID_REMOTION_BINDING", "Unknown scene/component", scene_id=scene_id, component_id=component_id)
    start, duration = float(start), float(duration)
    if start < 0 or duration <= 0 or start + duration > float(scene["duration"]) + 1e-9:
        raise AgentCutError("INVALID_REMOTION_BINDING", "Binding timing must remain inside its scene", start=start, duration=duration)
    props = validate_props(props, normalize_props_schema(components[component_id].get("props_schema")))
    binding_id = binding_id or f"rb_{len(state.setdefault('bindings', [])) + 1:04d}"
    if any(row.get("id") == binding_id for row in state["bindings"]):
        raise AgentCutError("INVALID_REMOTION_BINDING", "Duplicate binding id", binding_id=binding_id)
    row = {"id": binding_id, "scene_id": scene_id, "component_id": component_id, "start": start,
           "duration": duration, "props": props, "z": int(z)}
    state["bindings"].append(row)
    validate_remotion_state(project)
    return deepcopy(row)


def remove_binding(project: dict, binding_id: str) -> dict:
    rows = project.setdefault("remotion", {}).setdefault("bindings", [])
    before = len(rows)
    rows[:] = [row for row in rows if row.get("id") != binding_id]
    return {"binding_id": binding_id, "removed": len(rows) != before}


def build_manifest(project: dict, *, package_version: str) -> dict:
    validate_remotion_state(project)
    video = deepcopy(project.get("video") or {})
    fps = int(video.get("fps", 30))
    state = project.get("remotion") or {}
    bindings_by_scene: dict[str, list[dict]] = {}
    for binding in state.get("bindings", []):
        bindings_by_scene.setdefault(binding["scene_id"], []).append(binding)
    scenes: list[dict] = []
    frame_cursor = 0
    for scene in project.get("scenes", []):
        duration_frames = max(1, _frame(scene.get("duration", 0), fps))
        scene_bindings = []
        for binding in sorted(bindings_by_scene.get(scene["id"], []), key=lambda row: (row["start"], row["z"], row["id"])):
            scene_bindings.append({**deepcopy(binding), "from_frame": _frame(binding["start"], fps),
                                   "duration_frames": max(1, _frame(binding["duration"], fps))})
        scenes.append({
            "id": scene.get("id"), "asset_id": scene.get("asset_id"), "duration": float(scene.get("duration", 0)),
            "from_frame": frame_cursor, "duration_frames": duration_frames,
            "camera": deepcopy(scene.get("camera") or {}), "composition": deepcopy(scene.get("composition") or {}),
            "filters": deepcopy(scene.get("filters") or []), "effects": deepcopy(scene.get("effects") or []),
            "layers": deepcopy(scene.get("layers") or []), "transition_out": deepcopy(scene.get("transition_out") or {}),
            "gen3": deepcopy(scene.get("gen3") or {}), "custom_components": scene_bindings,
        })
        frame_cursor += duration_frames
    components = {cid: deepcopy(row) for cid, row in sorted((state.get("components") or {}).items())}
    return {
        "schema": MANIFEST_SCHEMA, "bridge_version": BRIDGE_VERSION, "agentcut_version": package_version,
        "project_hash": hash_obj(project), "video": video,
        "timeline": {"duration_frames": frame_cursor, "duration_seconds": frame_cursor / fps if fps else 0},
        "gen3": deepcopy(project.get("gen3") or {}), "assets": deepcopy(project.get("assets") or {}),
        "components": components, "scenes": scenes, "captions": deepcopy(project.get("captions") or []),
        "dialogue_segments": deepcopy(project.get("dialogue_segments") or []),
        "audio_tracks": deepcopy(project.get("audio_tracks") or []),
    }


def _bridge_files(component_ids: list[str]) -> dict[str, str]:
    package = {
        "name": "agentcut-remotion-bridge", "private": True, "version": "2.0.0",
        "scripts": {"verify": "node scripts/verify-manifest.mjs", "render": "npm run verify && remotion render src/index.ts Gen3 out/gen3.mp4"},
        "dependencies": {"@remotion/cli": REMOTION_VERSION, "remotion": REMOTION_VERSION,
                         "react": REACT_VERSION, "react-dom": REACT_VERSION},
        "devDependencies": {"typescript": TYPESCRIPT_VERSION},
    }
    imports = []
    rows = []
    for idx, cid in enumerate(component_ids):
        var = f"C{idx}"
        imports.append(f'import * as {var}Module from "./custom/{cid}";')
        rows.append(f'  "{cid}": ({var}Module as any).default ?? ({var}Module as any)[manifest.components["{cid}"].export_name],')
    registry = "\n".join([
        'import React from "react";', 'import manifest from "../../public/manifest.json";', *imports,
        'export const customRegistry: Record<string, React.ComponentType<any>> = {', *rows, '};',
    ]) + "\n"
    index = 'import {registerRoot} from "remotion";\nimport {Root} from "./Root";\nregisterRoot(Root);\n'
    root = '''import React from "react";\nimport {Composition} from "remotion";\nimport manifest from "../public/manifest.json";\nimport {Gen3} from "./Gen3";\nexport const Root:React.FC=()=> <Composition id="Gen3" component={Gen3} durationInFrames={Math.max(manifest.timeline.duration_frames,1)} fps={manifest.video.fps||30} width={manifest.video.width} height={manifest.video.height} defaultProps={{manifest}}/>;\n'''
    gen3 = '''import React from "react";\nimport {AbsoluteFill, Img, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";\nimport {customRegistry} from "./customRegistry";\nconst txt=(v:any)=>String(v??"");\nconst Scene:React.FC<{s:any}>=({s})=>{const frame=useCurrentFrame();const {fps,width,height}=useVideoConfig();const g=s.gen3||{};const card=g.card;const bg=s.asset_path?staticFile(s.asset_path):null;const motion=g.motion||"static";let scale=1;if(motion==="slow_push")scale=interpolate(frame,[0,s.duration_frames],[1,1.035],{extrapolateLeft:"clamp",extrapolateRight:"clamp"});if(motion==="slow_pull")scale=interpolate(frame,[0,s.duration_frames],[1.035,1],{extrapolateLeft:"clamp",extrapolateRight:"clamp"});const cardStart=card?Math.round(Number(card.start||0)*fps):0;const cardEnd=card?cardStart+Math.round(Number(card.duration||0)*fps):0;const show=!!card&&frame>=cardStart&&frame<cardEnd;return <AbsoluteFill style={{backgroundColor:"black",overflow:"hidden"}}>{bg&&<Img src={bg} style={{width:"100%",height:"100%",objectFit:"cover",scale,filter:show&&card.blur!==false?"blur(18px) brightness(.72)":"none"}}/>}{(g.actors||[]).map((a:any,i:number)=><Img key={i} src={staticFile(a.asset_path)} style={{position:"absolute",left:`${Number(a.x||0)*100}%`,top:`${Number(a.y||0)*100}%`,translate:"-50% -100%",scale:Number(a.scale||1),opacity:Number(a.opacity??1),transformOrigin:"50% 100%"}}/>)}{g.category&&<div style={{position:"absolute",left:width*.0375,top:height*.054,padding:`${height*.013}px ${width*.012}px`,background:"rgba(17,23,34,.72)",borderRadius:height*.013,color:"#f5f7fa",fontWeight:700,fontSize:height*.026,fontFamily:"sans-serif"}}>{txt(g.category)}</div>}{show&&<div style={{position:"absolute",left:"19.5%",right:"19.5%",bottom:"13.8%",padding:`${height*.035}px ${width*.027}px`,background:"rgba(16,21,30,.88)",border:"1px solid rgba(255,255,255,.12)",borderRadius:height*.02,color:"white",fontFamily:"sans-serif"}}><div style={{fontSize:height*.043,fontWeight:700}}>{txt(card.title)}</div>{card.subtitle&&<div style={{fontSize:height*.023,color:"#aeb7c5",marginTop:height*.008}}>{txt(card.subtitle)}</div>}<div style={{whiteSpace:"pre-line",fontSize:height*.031,color:"#e8ebf0",marginTop:height*.018,lineHeight:1.45}}>{txt(card.body)}</div></div>}{(s.custom_components||[]).map((b:any)=>{const C=customRegistry[b.component_id];return C?<Sequence key={b.id} from={b.from_frame} durationInFrames={b.duration_frames} layout="absolute-fill"><div style={{position:"absolute",inset:0,zIndex:b.z}}><C {...b.props}/></div></Sequence>:null;})}</AbsoluteFill>};\nexport const Gen3:React.FC<{manifest:any}>=({manifest})=><AbsoluteFill>{(manifest.scenes||[]).map((s:any)=><Sequence key={s.id} from={s.from_frame} durationInFrames={s.duration_frames}><Scene s={s}/></Sequence>)}</AbsoluteFill>;\n'''
    verify = '''import fs from "node:fs";import crypto from "node:crypto";import path from "node:path";const root=path.resolve(new URL("..",import.meta.url).pathname);const sha=p=>crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");const canonical=path.join(root,"public/manifest.canonical.json");const expected=fs.readFileSync(path.join(root,"public/manifest.sha256"),"utf8").trim();if(sha(canonical)!==expected)throw new Error("manifest hash mismatch");const m=JSON.parse(fs.readFileSync(canonical,"utf8"));if(m.schema!=="agentcut.remotion.manifest.v2")throw new Error("unsupported manifest schema");if(fs.readFileSync(path.join(root,"public/project.sha256"),"utf8").trim()!==m.project_hash)throw new Error("project hash mismatch");for(const a of Object.values(m.assets||{})){if(a.bundle_path&&a.bundle_sha256&&sha(path.join(root,"public",a.bundle_path))!==a.bundle_sha256)throw new Error(`asset hash mismatch: ${a.id}`)}for(const c of Object.values(m.components||{})){if(c.bundle_path&&sha(path.join(root,"src",c.bundle_path))!==c.source_sha256)throw new Error(`component hash mismatch: ${c.id}`)}console.log(JSON.stringify({ok:true,schema:m.schema,project_hash:m.project_hash,manifest_sha256:expected,frames:m.timeline.duration_frames}));\n'''
    return {"package.json": json.dumps(package, ensure_ascii=False, indent=2) + "\n", "src/index.ts": index,
            "src/Root.tsx": root, "src/Gen3.tsx": gen3, "src/customRegistry.tsx": registry,
            "scripts/verify-manifest.mjs": verify}


def write_bundle(project: dict, project_root: str | Path, output_dir: str | Path, *, package_version: str) -> dict:
    root, out = Path(project_root), Path(output_dir)
    if out.exists():
        shutil.rmtree(out)
    public, assets_out = out / "public", out / "public" / "assets"
    assets_out.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(project, package_version=package_version)
    copied: dict[str, str] = {}
    for aid, asset in manifest["assets"].items():
        if asset.get("type") not in {"image", "video", "audio"}:
            continue
        src = Path(asset.get("path", "")); src = src if src.is_absolute() else root / src
        if not src.exists():
            continue
        safe = f"{aid}_{src.name}".replace(" ", "_")
        dst = assets_out / safe; shutil.copy2(src, dst)
        copied[aid] = f"assets/{safe}"
        asset["bundle_path"] = copied[aid]; asset["bundle_sha256"] = file_sha256(dst)
    for scene in manifest["scenes"]:
        scene["asset_path"] = copied.get(scene.get("asset_id"))
        for actor in (scene.get("gen3") or {}).get("actors", []):
            actor["asset_path"] = copied.get(actor.get("asset_id"))
    component_ids = sorted(manifest["components"])
    for cid in component_ids:
        row = manifest["components"][cid]
        src = root / row["source_path"]
        if not src.exists() or file_sha256(src) != row["source_sha256"]:
            raise AgentCutError("REMOTION_COMPONENT_DRIFT", "Registered component source changed", component_id=cid)
        ext = src.suffix.lower(); dst = out / "src" / "custom" / f"{cid}{ext}"
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
        row["bundle_path"] = f"custom/{cid}{ext}"
    for rel, content in _bridge_files(component_ids).items():
        target = out / rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_text(content, encoding="utf-8")
    canonical = _canonical_bytes(manifest)
    (public / "manifest.canonical.json").write_bytes(canonical)
    (public / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_sha = _sha256_bytes(canonical)
    (public / "manifest.sha256").write_text(manifest_sha + "\n", encoding="utf-8")
    (public / "project.sha256").write_text(manifest["project_hash"] + "\n", encoding="utf-8")
    (out / "out").mkdir(exist_ok=True)
    result = verify_bundle(out)
    return {"path": str(out), "manifest": str(public / "manifest.json"), **result,
            "install": "npm install", "verify": "npm run verify", "render": "npm run render"}


def verify_bundle(output_dir: str | Path) -> dict:
    out = Path(output_dir); public = out / "public"
    canonical_path = public / "manifest.canonical.json"
    manifest = json.loads(canonical_path.read_text(encoding="utf-8"))
    pretty_path = public / "manifest.json"
    expected = (public / "manifest.sha256").read_text(encoding="utf-8").strip()
    actual = file_sha256(canonical_path)
    errors: list[str] = []
    if actual != expected: errors.append("manifest hash mismatch")
    if not pretty_path.exists() or _canonical_bytes(json.loads(pretty_path.read_text(encoding="utf-8"))) != canonical_path.read_bytes():
        errors.append("pretty manifest differs from canonical manifest")
    if manifest.get("schema") != MANIFEST_SCHEMA: errors.append("manifest schema mismatch")
    if (public / "project.sha256").read_text(encoding="utf-8").strip() != manifest.get("project_hash"):
        errors.append("project hash mismatch")
    total = sum(int(s.get("duration_frames", 0)) for s in manifest.get("scenes", []))
    if total != int(manifest.get("timeline", {}).get("duration_frames", -1)):
        errors.append("frame plan mismatch")
    for aid, asset in manifest.get("assets", {}).items():
        if asset.get("bundle_path") and file_sha256(public / asset["bundle_path"]) != asset.get("bundle_sha256"):
            errors.append(f"asset hash mismatch:{aid}")
    for cid, row in manifest.get("components", {}).items():
        if row.get("bundle_path") and file_sha256(out / "src" / row["bundle_path"]) != row.get("source_sha256"):
            errors.append(f"component hash mismatch:{cid}")
    if errors:
        raise AgentCutError("INVALID_REMOTION_BUNDLE", "Remotion bundle verification failed", errors=errors)
    return {"ok": True, "schema": manifest["schema"], "project_hash": manifest["project_hash"],
            "manifest_sha256": actual, "duration_frames": total}
