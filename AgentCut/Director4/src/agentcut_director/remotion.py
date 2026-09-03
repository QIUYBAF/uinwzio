from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .cutgraph import CutGraphError, project_hash, validate_project
from .identity import COMPOSITION_ID, PRODUCT_NAME, REMOTION_SCHEMA, VERSION

PINNED_REMOTION_VERSION = "4.0.506"
PINNED_REACT_VERSION = "19.1.0"


class BridgeVerificationError(CutGraphError):
    pass


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_asset_path(root: Path, relative: str) -> Path:
    full = (root / relative).resolve()
    try:
        full.relative_to(root.resolve())
    except ValueError as exc:
        raise CutGraphError(f"asset path escapes project root: {relative}") from exc
    return full


def _reachable_asset_ids(project: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for scene in project["timeline"]["scenes"]:
        if scene.get("asset_id"):
            ids.add(scene["asset_id"])
    for audio in project["timeline"]["audio"]:
        ids.add(audio["asset_id"])
    return ids


def _runtime_files() -> dict[str, str]:
    return {
        "src/index.ts": 'import {registerRoot} from "remotion";\nimport {DirectorRoot} from "./Root";\nregisterRoot(DirectorRoot);\n',
        "src/Root.tsx": 'import React from "react";\nimport {Composition} from "remotion";\nimport manifest from "../public/director-manifest.json";\nimport {DirectorComposition} from "./DirectorComposition";\n\nexport const DirectorRoot: React.FC = () => (\n  <Composition\n    id="AgentCutDirector4"\n    component={DirectorComposition}\n    durationInFrames={manifest.project.durationFrames}\n    fps={manifest.project.fps}\n    width={manifest.project.width}\n    height={manifest.project.height}\n    defaultProps={{manifest}}\n  />\n);\n',
        "src/DirectorComposition.tsx": '''import React from "react";
import {AbsoluteFill, Img, Sequence, Easing, interpolate, staticFile, useCurrentFrame} from "remotion";
import {Audio, Video} from "@remotion/media";

type Manifest = any;

const VisualScene: React.FC<{scene: any; asset?: any}> = ({scene, asset}) => {
  const frame = useCurrentFrame();
  const local = frame - scene.startFrame;
  const progress = interpolate(local, [0, Math.max(1, scene.durationFrames - 1)], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const motion = scene.motion?.type ?? "static";
  const scale = motion === "push" ? 1 + progress * Number(scene.motion?.amount ?? 0.04) : 1;
  const translate = motion === "pan" ? `${(progress - 0.5) * Number(scene.motion?.amountPx ?? 40)}px 0px` : "0px 0px";
  if (!asset) return <AbsoluteFill style={{backgroundColor: "#111"}} />;
  if (asset.kind === "video") {
    return <Video src={staticFile(asset.publicPath)} style={{width: "100%", height: "100%", objectFit: "cover", scale, translate}} />;
  }
  return <Img src={staticFile(asset.publicPath)} style={{width: "100%", height: "100%", objectFit: "cover", scale, translate}} />;
};

const Captions: React.FC<{items: any[]}> = ({items}) => (<>
  {items.map((caption) => (
    <Sequence key={caption.id} from={caption.startFrame} durationInFrames={caption.durationFrames}>
      <AbsoluteFill style={{justifyContent: "flex-end", alignItems: "center", paddingBottom: 70, pointerEvents: "none"}}>
        <div style={{fontFamily: "sans-serif", fontSize: 44, lineHeight: 1.25, color: "white", background: "rgba(0,0,0,0.58)", borderRadius: 12, padding: "10px 20px", maxWidth: "82%", textAlign: "center"}}>{caption.text}</div>
      </AbsoluteFill>
    </Sequence>
  ))}
</>);

export const DirectorComposition: React.FC<{manifest: Manifest}> = ({manifest}) => {
  const assets = new Map(manifest.assets.map((asset: any) => [asset.id, asset]));
  return <AbsoluteFill style={{backgroundColor: "black"}}>
    {manifest.scenes.map((scene: any) => (
      <Sequence key={scene.id} from={scene.startFrame} durationInFrames={scene.durationFrames}>
        <VisualScene scene={scene} asset={scene.assetId ? assets.get(scene.assetId) : undefined} />
      </Sequence>
    ))}
    {manifest.audio.map((clip: any) => {
      const asset: any = assets.get(clip.assetId);
      return asset ? <Audio key={clip.id} from={clip.startFrame} durationInFrames={clip.durationFrames} src={staticFile(asset.publicPath)} volume={clip.volume ?? 1} /> : null;
    })}
    <Captions items={manifest.captions} />
  </AbsoluteFill>;
};
''',
        "tsconfig.json": json.dumps({
            "compilerOptions": {
                "target": "ES2022", "lib": ["DOM", "ES2022"], "jsx": "react-jsx",
                "module": "ESNext", "moduleResolution": "Bundler", "resolveJsonModule": True,
                "strict": True, "esModuleInterop": True, "skipLibCheck": True, "noEmit": True,
            },
            "include": ["src/**/*.ts", "src/**/*.tsx", "public/director-manifest.json"],
        }, indent=2) + "\n",
    }


def export_remotion_bundle(project: dict[str, Any], *, project_root: str | Path, output_dir: str | Path, clean: bool = True) -> dict[str, Any]:
    root = Path(project_root).resolve()
    output = Path(output_dir).resolve()
    validate_project(project)
    if clean and output.exists():
        shutil.rmtree(output)
    (output / "public" / "assets").mkdir(parents=True, exist_ok=True)
    (output / "src").mkdir(parents=True, exist_ok=True)

    asset_rows: list[dict[str, Any]] = []
    for asset_id in sorted(_reachable_asset_ids(project)):
        asset = project["assets"].get(asset_id)
        if asset is None:
            raise CutGraphError(f"reachable asset missing: {asset_id}")
        source = _safe_asset_path(root, asset["path"])
        if not source.is_file():
            raise CutGraphError(f"asset missing: {asset['path']}")
        source_hash = _sha(source)
        if asset.get("sha256") and asset["sha256"] != source_hash:
            raise CutGraphError(f"asset changed since registration: {asset_id}")
        suffix = source.suffix.lower() or ".bin"
        public_name = f"{asset_id}{suffix}"
        target = output / "public" / "assets" / public_name
        shutil.copyfile(source, target)
        copied_hash = _sha(target)
        if source_hash != copied_hash:
            raise CutGraphError(f"copy hash mismatch: {asset_id}")
        asset_rows.append({
            "id": asset_id,
            "kind": asset["kind"],
            "publicPath": f"assets/{public_name}",
            "sha256": copied_hash,
            "bytes": target.stat().st_size,
            "sourcePath": asset["path"],
        })

    info = project["project"]
    manifest = {
        "schema": REMOTION_SCHEMA,
        "generator": {"name": PRODUCT_NAME, "version": VERSION},
        "compositionId": COMPOSITION_ID,
        "projectHash": project_hash(project),
        "project": {
            "id": info["id"], "title": info["title"], "fps": info["fps"],
            "width": info["width"], "height": info["height"],
            "durationFrames": info["duration_frames"],
        },
        "assets": asset_rows,
        "scenes": [{
            "id": x["id"], "kind": x.get("kind", "visual"),
            "startFrame": x["start_frame"], "durationFrames": x["duration_frames"],
            "assetId": x.get("asset_id"), "motion": x.get("motion", {"type": "static"}),
            "metadata": x.get("metadata", {}),
        } for x in sorted(project["timeline"]["scenes"], key=lambda x: (x["start_frame"], x["id"]))],
        "captions": [{
            "id": x["id"], "startFrame": x["start_frame"], "durationFrames": x["duration_frames"],
            "text": x.get("text", ""), "speaker": x.get("speaker"), "style": x.get("style", {}),
        } for x in project["timeline"]["captions"]],
        "audio": [{
            "id": x["id"], "assetId": x["asset_id"], "startFrame": x["start_frame"],
            "durationFrames": x["duration_frames"], "volume": x.get("volume", 1.0),
        } for x in project["timeline"]["audio"]],
        "delivery": project["delivery"],
    }
    manifest_path = output / "public" / "director-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    package = {
        "name": "agentcut-director-remotion-bridge",
        "private": True,
        "version": "4.0.0",
        "scripts": {
            "studio": "remotion studio src/index.ts --no-open",
            "typecheck": "tsc --noEmit",
            "render": f"remotion render src/index.ts {COMPOSITION_ID} out/director.mp4",
        },
        "dependencies": {
            "@remotion/cli": PINNED_REMOTION_VERSION,
            "@remotion/media": PINNED_REMOTION_VERSION,
            "remotion": PINNED_REMOTION_VERSION,
            "react": PINNED_REACT_VERSION,
            "react-dom": PINNED_REACT_VERSION,
        },
        "devDependencies": {"typescript": "5.9.2", "@types/react": "19.1.10"},
    }
    (output / "package.json").write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for relative, content in _runtime_files().items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")

    tracked = [
        "package.json", "tsconfig.json", "src/index.ts", "src/Root.tsx",
        "src/DirectorComposition.tsx", "public/director-manifest.json",
    ] + [row["publicPath"].replace("assets/", "public/assets/") for row in asset_rows]
    receipt = {
        "schema": "agentcut.director.bridge-receipt.v1",
        "projectHash": project_hash(project),
        "manifestSha256": _sha(manifest_path),
        "files": {relative: _sha(output / relative) for relative in sorted(tracked)},
        "versions": {"director": VERSION, "remotion": PINNED_REMOTION_VERSION, "react": PINNED_REACT_VERSION},
    }
    (output / "bridge-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_remotion_bundle(output, expected_project_hash=project_hash(project))
    return receipt


def verify_remotion_bundle(bundle_dir: str | Path, *, expected_project_hash: str | None = None) -> dict[str, Any]:
    root = Path(bundle_dir).resolve()
    receipt_path = root / "bridge-receipt.json"
    manifest_path = root / "public" / "director-manifest.json"
    if not receipt_path.is_file() or not manifest_path.is_file():
        raise BridgeVerificationError("bridge receipt or manifest missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if receipt.get("schema") != "agentcut.director.bridge-receipt.v1":
        raise BridgeVerificationError("unsupported bridge receipt schema")
    if manifest.get("schema") != REMOTION_SCHEMA:
        raise BridgeVerificationError("unsupported Remotion manifest schema")
    if receipt.get("manifestSha256") != _sha(manifest_path):
        raise BridgeVerificationError("manifest hash mismatch")
    if receipt.get("projectHash") != manifest.get("projectHash"):
        raise BridgeVerificationError("receipt/manifest project hash mismatch")
    if expected_project_hash and receipt.get("projectHash") != expected_project_hash:
        raise BridgeVerificationError("bundle was generated from a different project state")
    checked = 0
    for relative, expected in receipt.get("files", {}).items():
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise BridgeVerificationError(f"receipt path escapes bundle: {relative}") from exc
        if not path.is_file():
            raise BridgeVerificationError(f"bundle file missing: {relative}")
        actual = _sha(path)
        if actual != expected:
            raise BridgeVerificationError(f"bundle file hash mismatch: {relative}")
        checked += 1
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    if package["dependencies"].get("remotion") != PINNED_REMOTION_VERSION:
        raise BridgeVerificationError("Remotion dependency is not pinned to the certified version")
    return {
        "ok": True,
        "project_hash": receipt["projectHash"],
        "files_checked": checked,
        "composition_id": manifest["compositionId"],
        "duration_frames": manifest["project"]["durationFrames"],
    }
