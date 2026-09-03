from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from .audit import structural_efficiency_audit
from .cutgraph import CutGraphError, load_project, new_project, project_hash, save_project, validate_project
from .diffing import semantic_diff
from .identity import CLI_NAME, VERSION, product_identity
from .migration import migrate_file
from .operations import apply_transaction, preflight, undo_last
from .remotion import export_remotion_bundle, verify_remotion_bundle


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _demo(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    assets = output / "assets"
    assets.mkdir(exist_ok=True)
    svg1 = assets / "scene-a.svg"
    svg2 = assets / "scene-b.svg"
    svg1.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="100%" height="100%" fill="#152034"/><text x="120" y="520" font-size="88" fill="white">AgentCut Director 4</text></svg>', encoding="utf-8")
    svg2.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><rect width="100%" height="100%" fill="#2b2438"/><text x="120" y="520" font-size="72" fill="white">CutGraph → Verified Remotion Bridge</text></svg>', encoding="utf-8")
    project = new_project("Director 4 Demo", fps=30)
    for asset_id, path in (("scene-a", svg1), ("scene-b", svg2)):
        project["assets"][asset_id] = {
            "id": asset_id,
            "kind": "image",
            "path": str(path.relative_to(output)),
            "sha256": _sha(path),
            "metadata": {},
        }
    project["timeline"]["scenes"] = [
        {"id": "s01", "kind": "title", "start_frame": 0, "duration_frames": 90, "asset_id": "scene-a", "motion": {"type": "push", "amount": 0.035}},
        {"id": "s02", "kind": "visual", "start_frame": 90, "duration_frames": 90, "asset_id": "scene-b", "motion": {"type": "static"}},
    ]
    project["timeline"]["captions"] = [
        {"id": "cap-01", "start_frame": 30, "duration_frames": 45, "text": "独立命名，独立状态，确定性桥接。", "speaker": None, "style": {}},
        {"id": "cap-02", "start_frame": 115, "duration_frames": 45, "text": "Classic 3.x 保留；Director 4 向前演进。", "speaker": None, "style": {}},
    ]
    project["project"]["duration_frames"] = 180
    validate_project(project, project_root=output, strict_assets=True)
    project_path = output / "director-project.json"
    save_project(project, project_path)
    receipt = export_remotion_bundle(project, project_root=output, output_dir=output / "remotion")
    return {"project": str(project_path), "project_hash": project_hash(project), "bridge_receipt": receipt}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=CLI_NAME, description="AgentCut Director 4 semantic video control plane")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("identity")

    init = sub.add_parser("init")
    init.add_argument("path")
    init.add_argument("--title", required=True)
    init.add_argument("--fps", type=int, default=30)
    init.add_argument("--width", type=int, default=1920)
    init.add_argument("--height", type=int, default=1080)

    validate = sub.add_parser("validate")
    validate.add_argument("project")
    validate.add_argument("--project-root")
    validate.add_argument("--strict-assets", action="store_true")

    hash_cmd = sub.add_parser("hash")
    hash_cmd.add_argument("project")

    pre = sub.add_parser("preflight")
    pre.add_argument("project")
    pre.add_argument("operations")

    apply_cmd = sub.add_parser("apply")
    apply_cmd.add_argument("project")
    apply_cmd.add_argument("operations")
    apply_cmd.add_argument("--expected-hash")
    apply_cmd.add_argument("--receipt-out")

    undo = sub.add_parser("undo")
    undo.add_argument("project")

    diff = sub.add_parser("diff")
    diff.add_argument("before")
    diff.add_argument("after")

    migrate = sub.add_parser("migrate-classic3")
    migrate.add_argument("source")
    migrate.add_argument("output")
    migrate.add_argument("--overwrite", action="store_true")

    export = sub.add_parser("remotion-export")
    export.add_argument("project")
    export.add_argument("output")
    export.add_argument("--project-root", default=".")

    verify = sub.add_parser("remotion-verify")
    verify.add_argument("bundle")
    verify.add_argument("--expected-project-hash")

    audit = sub.add_parser("efficiency-audit")
    audit.add_argument("project")
    audit.add_argument("operations")

    demo = sub.add_parser("demo")
    demo.add_argument("output")
    sub.add_parser("doctor")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "identity":
            _print(product_identity())
        elif args.command == "init":
            project = new_project(args.title, fps=args.fps, width=args.width, height=args.height)
            save_project(project, args.path)
            _print({"ok": True, "path": args.path, "project_hash": project_hash(project)})
        elif args.command == "validate":
            project = load_project(args.project)
            warnings = validate_project(project, project_root=args.project_root, strict_assets=args.strict_assets)
            _print({"ok": True, "project_hash": project_hash(project), "warnings": warnings})
        elif args.command == "hash":
            _print({"project_hash": project_hash(load_project(args.project))})
        elif args.command == "preflight":
            _print(preflight(load_project(args.project), _read_json(args.operations)))
        elif args.command == "apply":
            project = load_project(args.project)
            updated, receipt = apply_transaction(project, _read_json(args.operations), expected_project_hash=args.expected_hash)
            save_project(updated, args.project)
            if args.receipt_out:
                Path(args.receipt_out).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _print(receipt)
        elif args.command == "undo":
            project = load_project(args.project)
            updated, receipt = undo_last(project)
            save_project(updated, args.project)
            _print(receipt)
        elif args.command == "diff":
            _print({"changes": semantic_diff(_read_json(args.before), _read_json(args.after))})
        elif args.command == "migrate-classic3":
            _print(migrate_file(args.source, args.output, overwrite=args.overwrite))
        elif args.command == "remotion-export":
            project = load_project(args.project)
            _print(export_remotion_bundle(project, project_root=args.project_root, output_dir=args.output))
        elif args.command == "remotion-verify":
            _print(verify_remotion_bundle(args.bundle, expected_project_hash=args.expected_project_hash))
        elif args.command == "efficiency-audit":
            _print(structural_efficiency_audit(load_project(args.project), _read_json(args.operations)))
        elif args.command == "demo":
            _print(_demo(Path(args.output)))
        elif args.command == "doctor":
            with tempfile.TemporaryDirectory(prefix="agentcut-director-doctor-") as temp:
                demo = _demo(Path(temp))
                verified = verify_remotion_bundle(Path(temp) / "remotion", expected_project_hash=demo["project_hash"])
            _print({
                "ok": True,
                "product": product_identity(),
                "python": platform.python_version(),
                "platform": platform.platform(),
                "remotion_bridge": verified,
                "node_available": shutil.which("node") is not None,
                "npm_available": shutil.which("npm") is not None,
            })
        return 0
    except (CutGraphError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
