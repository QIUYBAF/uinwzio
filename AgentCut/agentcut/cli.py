from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .director import choose_backend
from .discovery import discover as discover_environment
from .doctor import run_doctor
from .errors import AgentCutError


def jprint(obj):
    if isinstance(obj, Path):
        obj = {"path": str(obj)}
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentcut", description="Agent-native semantic video editor")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("discover")
    sub.add_parser("modules")

    s = sub.add_parser("roughcut", help="Plan a long-recording rough cut with resumable analysis")
    s.add_argument("source")
    s.add_argument("job")
    s.add_argument("--events", help="External event JSON list; replaces automatic audio detection")
    s.add_argument("--chunk-seconds", type=float, default=300)
    s.add_argument("--before", type=float, default=12)
    s.add_argument("--after", type=float, default=8)
    s.add_argument("--merge-gap", type=float, default=5)
    s.add_argument("--budget", type=float, help="Maximum total seconds; keep complete candidates")
    s.add_argument("--audio-stream", type=int, default=0, help="Zero-based audio stream ordinal")
    s.add_argument("--audio-threshold", type=float, default=-28, help="Audio RMS threshold in dBFS")

    s = sub.add_parser("roughcut-export", help="Export reviewed candidates with original audio")
    s.add_argument("plan")
    s.add_argument("output")

    s = sub.add_parser("roughcut-operations", help="Export visual-only operations for the existing editor")
    s.add_argument("plan")
    s.add_argument("output")
    s.add_argument("--asset-id", default="roughcut_source")

    s = sub.add_parser("doctor")
    s.add_argument("--project-root")
    s.add_argument("--fix", action="store_true", help="Create safe AgentCut runtime directories")

    s = sub.add_parser("backend")
    s.add_argument("--project-root")
    s.add_argument("--needs-react-ui", action="store_true")

    s = sub.add_parser("quickstart")
    s.add_argument("root")
    s.add_argument("--create", action="store_true")
    s.add_argument("--name", default="Untitled AgentCut Project")
    s.add_argument("--width", type=int, default=1920)
    s.add_argument("--height", type=int, default=1080)
    s.add_argument("--fps", type=int, default=30)
    s.add_argument("--task")
    s.add_argument("--scenes", help="Comma-separated scene IDs")
    s.add_argument("--domains", help="Comma-separated operation domains")
    s.add_argument("--no-write", action="store_true")

    s = sub.add_parser("init")
    s.add_argument("root")
    s.add_argument("--name", default="Untitled AgentCut Project")
    s.add_argument("--width", type=int, default=1920)
    s.add_argument("--height", type=int, default=1080)
    s.add_argument("--fps", type=int, default=30)

    for name in ("show", "timeline", "state", "capabilities", "versions", "undo", "redo", "cache-info", "cache-clear"):
        s = sub.add_parser(name)
        s.add_argument("root")

    s = sub.add_parser("diff")
    s.add_argument("root"); s.add_argument("a", type=int); s.add_argument("b", type=int)

    s = sub.add_parser("checkpoint")
    s.add_argument("root"); s.add_argument("name"); s.add_argument("--note")

    s = sub.add_parser("checkpoints")
    s.add_argument("root")

    s = sub.add_parser("restore-checkpoint")
    s.add_argument("root"); s.add_argument("name")

    s = sub.add_parser("scene-history")
    s.add_argument("root"); s.add_argument("scene_id")

    s = sub.add_parser("restore-scene")
    s.add_argument("root"); s.add_argument("scene_id")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--version", type=int); g.add_argument("--checkpoint")
    s.add_argument("--components", help="Comma-separated restore layers: asset,timing,camera,effects,audio,transition")

    s = sub.add_parser("apply")
    s.add_argument("root"); s.add_argument("operations_json", help="JSON file containing a list of {action,args} operations")
    s.add_argument("--expected-project-hash"); s.add_argument("--dry-run", action="store_true")
    s.add_argument("--strict", action="store_true", help="Disable Agent Reliability normalization")
    s.add_argument("--include-project", action="store_true", help="Include full project/results in Agent response")

    s = sub.add_parser("agent-preflight")
    s.add_argument("root"); s.add_argument("operations_json")
    s.add_argument("--expected-project-hash")
    s.add_argument("--include-projected-state", action="store_true")

    s = sub.add_parser("agent-context")
    s.add_argument("root")
    s.add_argument("--scenes", help="Comma-separated scene IDs")
    s.add_argument("--domains", help="Comma-separated operation domains, e.g. visual,cinematic,text")
    s.add_argument("--no-schema", action="store_true")

    s = sub.add_parser("agent-start")
    s.add_argument("root"); s.add_argument("--task"); s.add_argument("--scenes"); s.add_argument("--domains"); s.add_argument("--no-write", action="store_true")

    s = sub.add_parser("setup")
    s.add_argument("root"); s.add_argument("--create", action="store_true"); s.add_argument("--name", default="Untitled AgentCut Project")
    s.add_argument("--width", type=int, default=1920); s.add_argument("--height", type=int, default=1080); s.add_argument("--fps", type=int, default=30)

    s = sub.add_parser("subtitle-status")
    s.add_argument("root")

    s = sub.add_parser("asr-install")
    s.add_argument("--profile", default="tiny-q5_1")
    s.add_argument("--accept-third-party", action="store_true")
    s.add_argument("--model-only", action="store_true")

    s = sub.add_parser("subtitle-optimize")
    s.add_argument("root"); s.add_argument("--captions", help="Comma-separated caption IDs; default is all")
    s.add_argument("--no-dialogue", action="store_true")

    s = sub.add_parser("staging-suggest")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--count", type=int)

    s = sub.add_parser("staging-order")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("characters", help="Comma-separated Cast IDs in left-to-right order")
    s.add_argument("--minimum-confidence", type=float, default=0.18)

    s = sub.add_parser("agent-checkpoint")
    s.add_argument("root"); s.add_argument("--goal"); s.add_argument("--scenes"); s.add_argument("--domains")
    s.add_argument("--decision", action="append", default=[])

    s = sub.add_parser("auto-subtitles")
    s.add_argument("root"); s.add_argument("asset_id"); s.add_argument("--language", default="auto"); s.add_argument("--model")
    s.add_argument("--bilingual", action="store_true"); s.add_argument("--translate-to", default="en"); s.add_argument("--style", default="bilingual")
    s.add_argument("--position", default="bottom"); s.add_argument("--speaker"); s.add_argument("--offset", type=float, default=0.0); s.add_argument("--max-segments", type=int)

    s = sub.add_parser("import-srt")
    s.add_argument("root"); s.add_argument("path"); s.add_argument("--style", default="default"); s.add_argument("--position", default="bottom"); s.add_argument("--speaker"); s.add_argument("--offset", type=float, default=0.0)
    s.add_argument("--secondary-path"); s.add_argument("--secondary-language", default="en")
    s.add_argument("--no-parse-speakers", action="store_true"); s.add_argument("--no-infer-styles", action="store_true"); s.add_argument("--no-smart-position", action="store_true")

    s = sub.add_parser("video-mode")
    s.add_argument("root"); s.add_argument("preset", choices=["1080p30","1080p60","4k30","4k60","uhd_4k30","uhd_4k60"])

    s = sub.add_parser("add-asset")
    s.add_argument("root"); s.add_argument("path"); s.add_argument("--id")
    s.add_argument("--no-copy", action="store_true", help="Reference an existing recording without copying it")

    s = sub.add_parser("add-scene")
    s.add_argument("root"); s.add_argument("asset_id"); s.add_argument("duration", type=float); s.add_argument("--id"); s.add_argument("--after")
    s.add_argument("--source-in", type=float, default=0.0); s.add_argument("--playback-rate", type=float, default=1.0)

    s = sub.add_parser("delete-scene")
    s.add_argument("root"); s.add_argument("scene_id")

    s = sub.add_parser("source")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--source-in", type=float); s.add_argument("--playback-rate", type=float)

    s = sub.add_parser("camera")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("motion")
    s.add_argument("--amount", type=float, default=0.035); s.add_argument("--easing", default="linear"); s.add_argument("--anchor", default="center")

    s = sub.add_parser("analyze-visual")
    s.add_argument("root"); s.add_argument("asset_id"); s.add_argument("--samples", type=int, default=3)

    s = sub.add_parser("composition-plan")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--text", default=""); s.add_argument("--analyze", action="store_true"); s.add_argument("--samples", type=int, default=3)

    s = sub.add_parser("auto-compose")
    s.add_argument("root"); s.add_argument("--scenes", help="Comma-separated scene IDs; default is all scenes"); s.add_argument("--samples", type=int, default=3)


    s = sub.add_parser("cinematic-plan")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--intent", default="auto")

    s = sub.add_parser("cinematic-frame")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--preset", default="scope_lock"); s.add_argument("--easing", default="smooth")

    s = sub.add_parser("fragment")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--style", default="impact_cluster"); s.add_argument("--count", type=int, default=5); s.add_argument("--intensity", type=float, default=.75)

    s = sub.add_parser("cinematic")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--style", default="auto"); s.add_argument("--count", type=int, default=5); s.add_argument("--intensity", type=float, default=.75)

    s = sub.add_parser("effect")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("effect")
    s.add_argument("--intensity", type=float, default=0.2); s.add_argument("--speed", type=float, default=1.0)
    s.add_argument("--direction", default="auto"); s.add_argument("--depth", default="foreground")
    s.add_argument("--opacity", type=float, default=0.6); s.add_argument("--seed", type=int, default=1)

    s = sub.add_parser("remove-effect")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("index", type=int)

    s = sub.add_parser("transition")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("type"); s.add_argument("--duration", type=float, default=0.35)

    s = sub.add_parser("caption")
    s.add_argument("root"); s.add_argument("text"); s.add_argument("start", type=float); s.add_argument("end", type=float)
    s.add_argument("--speaker"); s.add_argument("--position", default="bottom")

    s = sub.add_parser("audio")
    s.add_argument("root"); s.add_argument("asset_id"); s.add_argument("--kind", default="bgm")
    s.add_argument("--volume-db", type=float, default=-20); s.add_argument("--start", type=float, default=0)
    s.add_argument("--duration", type=float); s.add_argument("--fade-in", type=float, default=0.5); s.add_argument("--fade-out", type=float, default=0.5); s.add_argument("--loop", action="store_true")

    s = sub.add_parser("scene-audio")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("asset_id"); s.add_argument("--kind", default="ambience")
    s.add_argument("--volume-db", type=float, default=-18); s.add_argument("--start", type=float, default=0)
    s.add_argument("--duration", type=float); s.add_argument("--fade-in", type=float, default=0.2); s.add_argument("--fade-out", type=float, default=0.2); s.add_argument("--loop", action="store_true")

    sub.add_parser("enhance-status")

    s = sub.add_parser("ai-install")
    s.add_argument("backend", choices=["realesrgan", "rife"]); s.add_argument("--accept-third-party", action="store_true")

    s = sub.add_parser("export-plan")
    s.add_argument("root"); s.add_argument("--width", type=int, required=True); s.add_argument("--height", type=int, required=True); s.add_argument("--fps", type=float, required=True)
    s.add_argument("--container", choices=["mp4", "mov", "mkv", "webm"], default="mp4")
    s.add_argument("--codec", choices=["h264", "hevc", "av1", "vp9", "prores"], default="h264")
    s.add_argument("--encoder", choices=["auto", "cpu", "gpu"], default="auto"); s.add_argument("--quality", type=int, default=18)
    s.add_argument("--upscale", choices=["auto", "off", "ai", "realesrgan"], default="auto")
    s.add_argument("--interpolate", choices=["auto", "off", "ai", "rife"], default="auto")
    s.add_argument("--content", choices=["anime", "general"], default="anime")

    s = sub.add_parser("export")
    s.add_argument("root"); s.add_argument("--width", type=int, required=True); s.add_argument("--height", type=int, required=True); s.add_argument("--fps", type=float, required=True)
    s.add_argument("--container", choices=["mp4", "mov", "mkv", "webm"], default="mp4")
    s.add_argument("--codec", choices=["h264", "hevc", "av1", "vp9", "prores"], default="h264")
    s.add_argument("--encoder", choices=["auto", "cpu", "gpu"], default="auto"); s.add_argument("--quality", type=int, default=18)
    s.add_argument("--upscale", choices=["auto", "off", "ai", "realesrgan"], default="auto")
    s.add_argument("--interpolate", choices=["auto", "off", "ai", "rife"], default="auto")
    s.add_argument("--content", choices=["anime", "general"], default="anime"); s.add_argument("--output"); s.add_argument("--keep-intermediate", action="store_true")

    s = sub.add_parser("gen3-config")
    s.add_argument("root")
    s.add_argument("--target-profile", choices=["uhd_4k30","uhd_4k60","4k30","4k60","1080p30","1080p60"])
    s.add_argument("--matte-key")
    s.add_argument("--renderer")
    s.add_argument("--default-motion", choices=["static","slow_push","slow_pull","pan_left","pan_right","pan_up","pan_down"])
    s.add_argument("--stillness-first", choices=["true","false"])

    s = sub.add_parser("gen3-scene")
    s.add_argument("root"); s.add_argument("scene_id")
    s.add_argument("--kind", default="exhibit", choices=["exhibit","info_card","return","montage","silence","quote"])
    s.add_argument("--category"); s.add_argument("--work-title"); s.add_argument("--author")
    s.add_argument("--motion", default="static", choices=["static","slow_push","slow_pull","pan_left","pan_right","pan_up","pan_down"])

    s = sub.add_parser("gen3-card")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("title"); s.add_argument("body")
    s.add_argument("--subtitle"); s.add_argument("--category"); s.add_argument("--start", type=float, default=3.0); s.add_argument("--duration", type=float, default=3.2)
    s.add_argument("--no-blur", action="store_true")

    s = sub.add_parser("gen3-register-actor")
    s.add_argument("root"); s.add_argument("path"); s.add_argument("--id"); s.add_argument("--key-color"); s.add_argument("--no-shadow", action="store_true")

    s = sub.add_parser("gen3-place-actor")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("asset_id"); s.add_argument("--x", type=float, required=True); s.add_argument("--floor-y", type=float, required=True)
    s.add_argument("--scale", type=float, default=1.0); s.add_argument("--end-x", type=float); s.add_argument("--end-floor-y", type=float); s.add_argument("--shadow-asset-id"); s.add_argument("--z", type=int, default=40); s.add_argument("--opacity", type=float, default=1.0)

    s = sub.add_parser("gen3-compile")
    s.add_argument("root"); s.add_argument("--scenes", help="Comma-separated scene IDs; default all Gen3 scenes")

    s = sub.add_parser("gen3-remotion")
    s.add_argument("root"); s.add_argument("--output-dir")

    s = sub.add_parser("gen3-tile-plan")
    s.add_argument("width", type=int); s.add_argument("height", type=int); s.add_argument("--rows", type=int, default=2); s.add_argument("--cols", type=int, default=2); s.add_argument("--overlap", type=float, default=.12)

    s = sub.add_parser("gen3-extract-tiles")
    s.add_argument("input"); s.add_argument("output_dir"); s.add_argument("--rows", type=int, default=2); s.add_argument("--cols", type=int, default=2); s.add_argument("--overlap", type=float, default=.12)

    s = sub.add_parser("gen3-stitch")
    s.add_argument("output"); s.add_argument("tiles", nargs="+"); s.add_argument("--rows", type=int, default=2); s.add_argument("--cols", type=int, default=2); s.add_argument("--overlap", type=float, default=.12)

    s = sub.add_parser("gen3-chroma")
    s.add_argument("input"); s.add_argument("output"); s.add_argument("--key-color", default="#FF00FF"); s.add_argument("--inner", type=float, default=28.0); s.add_argument("--outer", type=float, default=95.0); s.add_argument("--despill", type=float, default=.55)

    s = sub.add_parser("render")
    s.add_argument("root"); s.add_argument("--profile", choices=["proxy", "preview", "showcase", "final", "uhd_4k30", "uhd_4k60"], default="preview"); s.add_argument("--output")

    s = sub.add_parser("render-scene")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("--profile", choices=["proxy", "preview", "showcase", "final", "uhd_4k30", "uhd_4k60"], default="preview"); s.add_argument("--output")

    s = sub.add_parser("render-span")
    s.add_argument("root"); s.add_argument("start_scene"); s.add_argument("end_scene"); s.add_argument("--profile", choices=["proxy", "preview", "showcase", "final", "uhd_4k30", "uhd_4k60"], default="preview"); s.add_argument("--output")

    s = sub.add_parser("qa")
    s.add_argument("root"); s.add_argument("--rendered")

    s = sub.add_parser("contact-sheet")
    s.add_argument("video"); s.add_argument("output"); s.add_argument("--interval", type=float, default=2.0)

    s = sub.add_parser("serve")
    s.add_argument("root"); s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8765)
    s = sub.add_parser("remotion-register")
    s.add_argument("root"); s.add_argument("source"); s.add_argument("--id", required=True); s.add_argument("--export-name", default="default"); s.add_argument("--props-schema")

    s = sub.add_parser("remotion-bind")
    s.add_argument("root"); s.add_argument("scene_id"); s.add_argument("component_id"); s.add_argument("--start", type=float, required=True); s.add_argument("--duration", type=float, required=True); s.add_argument("--props"); s.add_argument("--z", type=int, default=50); s.add_argument("--binding-id")

    s = sub.add_parser("remotion-verify")
    s.add_argument("root"); s.add_argument("--output-dir")

    s = sub.add_parser("efficiency-start")
    s.add_argument("root"); s.add_argument("--arm", choices=["agentcut", "remotion"], required=True); s.add_argument("--task-id", required=True); s.add_argument("--metadata")

    s = sub.add_parser("efficiency-finish")
    s.add_argument("root"); s.add_argument("session_id"); s.add_argument("--actual-usage"); s.add_argument("--elapsed-seconds", type=float); s.add_argument("--tool-calls", type=int); s.add_argument("--failed-commands", type=int); s.add_argument("--rendered-frames", type=int); s.add_argument("--qa-issues", type=int); s.add_argument("--notes")

    s = sub.add_parser("efficiency-measure")
    s.add_argument("root"); s.add_argument("--operations")

    s = sub.add_parser("efficiency-report")
    s.add_argument("root")

    s = sub.add_parser("release-check")
    s.add_argument("root"); s.add_argument("--strict", action="store_true")

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "modules":
            from .modules import module_status
            jprint(module_status()); return 0
        if args.cmd in {"roughcut", "roughcut-export", "roughcut-operations"}:
            from .roughcut import analyze_recording, export_recording, editor_operations, atomic_json
            def progress(value):
                print(json.dumps({"progress": value}), file=sys.stderr, flush=True)
            if args.cmd == "roughcut":
                events = json.loads(Path(args.events).read_text(encoding="utf-8-sig")) if args.events else None
                if args.events and not isinstance(events, list):
                    raise AgentCutError("INVALID_ROUGHCUT", "External event file must contain a JSON list")
                result = analyze_recording(args.source, args.job, events=events, chunk_seconds=args.chunk_seconds,
                                           before=args.before, after=args.after, merge_gap=args.merge_gap,
                                           budget=args.budget, audio_stream=args.audio_stream,
                                           audio_threshold=args.audio_threshold, progress=progress)
                jprint({"plan": str(Path(args.job).resolve() / "plan.json"), "status": result["status"],
                        "clips": len(result["clips"]), "selected_duration": result["selected_duration"],
                        "chunks": result["chunks"], "warnings": result["warnings"]})
            elif args.cmd == "roughcut-export":
                jprint(export_recording(args.plan, args.output, progress=progress))
            else:
                output = Path(args.output).resolve()
                if output.exists():
                    raise AgentCutError("OUTPUT_EXISTS", "Choose a new operations path", path=str(output))
                atomic_json(output, editor_operations(args.plan, args.asset_id))
                jprint({"output": str(output), "asset_id": args.asset_id,
                        "warning": "Register the plan source with add-asset --no-copy and this asset ID first. Visual-only conform; use roughcut-export to retain source audio."})
            return 0
        if args.cmd == "discover":
            jprint(discover_environment()); return 0
        if args.cmd == "doctor":
            result = run_doctor(args.project_root, fix=args.fix)
            jprint(result); return 2 if result["status"] == "fail" else 0
        if args.cmd == "backend":
            jprint(choose_backend(needs_react_ui=args.needs_react_ui, project_root=args.project_root)); return 0
        if args.cmd == "quickstart":
            from .editor import Editor
            root = Path(args.root)
            created = False
            if not (root / "project.json").exists():
                if not args.create:
                    raise AgentCutError(
                        "PROJECT_NOT_FOUND",
                        "No project.json found. Re-run with --create to initialize this directory.",
                        root=str(root.resolve()),
                    )
                e = Editor.create(root, width=args.width, height=args.height, fps=args.fps, name=args.name)
                created = True
            else:
                e = Editor(root)
            scenes = [x.strip() for x in args.scenes.split(",") if x.strip()] if args.scenes else None
            domains = [x.strip() for x in args.domains.split(",") if x.strip()] if args.domains else None
            setup = e.setup_runtime()
            bootstrap = e.agent_bootstrap(task=args.task, scene_ids=scenes, domains=domains, write=not args.no_write)
            jprint({
                "status": "ready",
                "project": str(e.root),
                "created": created,
                "release": discover_environment(),
                "doctor": run_doctor(e.root),
                "backend": choose_backend(project_root=e.root),
                "setup": setup,
                "bootstrap": bootstrap,
            })
            return 0
        if args.cmd == "init":
            from .editor import Editor
            e = Editor.create(args.root, width=args.width, height=args.height, fps=args.fps, name=args.name)
            jprint(e.get_project()); return 0
        if args.cmd == "contact-sheet":
            from .contact_sheet import make_contact_sheet
            jprint(make_contact_sheet(Path(args.video), Path(args.output), interval=args.interval)); return 0
        if args.cmd == "serve":
            from .api import run_server
            run_server(args.root, args.host, args.port); return 0
        if args.cmd == "enhance-status":
            from .enhance import enhancement_status
            jprint(enhancement_status()); return 0
        if args.cmd == "ai-install":
            from .enhance import install_backend
            jprint(install_backend(args.backend, accept_third_party=args.accept_third_party)); return 0

        if args.cmd == "asr-install":
            from .subtitles import install_whisper_backend
            jprint(install_whisper_backend(profile=args.profile, accept_third_party=args.accept_third_party, model_only=args.model_only)); return 0

        if args.cmd == "gen3-tile-plan":
            from .gen3 import tile_plan
            jprint(tile_plan(args.width, args.height, rows=args.rows, cols=args.cols, overlap=args.overlap)); return 0
        if args.cmd == "gen3-extract-tiles":
            from .gen3 import extract_tiles
            jprint(extract_tiles(args.input, args.output_dir, rows=args.rows, cols=args.cols, overlap=args.overlap)); return 0
        if args.cmd == "gen3-stitch":
            from .gen3 import stitch_tiles
            jprint(stitch_tiles(args.tiles, args.output, rows=args.rows, cols=args.cols, overlap=args.overlap)); return 0
        if args.cmd == "gen3-chroma":
            from .gen3 import chroma_key_image
            jprint(chroma_key_image(args.input, args.output, key_color=args.key_color, inner=args.inner, outer=args.outer, despill=args.despill)); return 0
        if args.cmd == "release-check":
            from .release_check import check_release
            result = check_release(args.root, strict=args.strict); jprint(result); return 0 if result["ok"] else 2

        from .editor import Editor
        if args.cmd == "setup" and args.create and not (Path(args.root) / "project.json").exists():
            e = Editor.create(args.root, width=args.width, height=args.height, fps=args.fps, name=args.name)
        else:
            e = Editor(args.root)
        if args.cmd == "show": jprint(e.get_project())
        elif args.cmd == "timeline": jprint(e.get_timeline())
        elif args.cmd == "state": jprint(e.state_digest())
        elif args.cmd == "capabilities": jprint(e.list_capabilities())
        elif args.cmd == "versions": jprint(e.versions())
        elif args.cmd == "undo": jprint(e.undo())
        elif args.cmd == "redo": jprint(e.redo())
        elif args.cmd == "cache-info": jprint(e.cache_info())
        elif args.cmd == "cache-clear": jprint(e.clear_cache())
        elif args.cmd == "diff": print(e.diff(args.a, args.b))
        elif args.cmd == "checkpoint": jprint(e.create_checkpoint(args.name, note=args.note))
        elif args.cmd == "checkpoints": jprint(e.checkpoints())
        elif args.cmd == "restore-checkpoint": jprint(e.restore_checkpoint(args.name))
        elif args.cmd == "scene-history": jprint(e.scene_history(args.scene_id))
        elif args.cmd == "restore-scene": jprint(e.restore_scene(args.scene_id, version=args.version, checkpoint=args.checkpoint, components=[x.strip() for x in args.components.split(",") if x.strip()] if args.components else None))
        elif args.cmd == "apply":
            ops = json.loads(Path(args.operations_json).read_text(encoding="utf-8"))
            if args.strict:
                if not isinstance(ops, list):
                    raise AgentCutError("INVALID_OPERATIONS_FILE", "Strict operations JSON root must be an array", path=args.operations_json)
                jprint(e.apply_operations(ops, expected_project_hash=args.expected_project_hash, dry_run=args.dry_run))
            else:
                jprint(e.apply_agent_operations(ops, expected_project_hash=args.expected_project_hash, dry_run=args.dry_run, include_project=args.include_project))
        elif args.cmd == "agent-preflight":
            ops = json.loads(Path(args.operations_json).read_text(encoding="utf-8"))
            jprint(e.preflight_operations(ops, expected_project_hash=args.expected_project_hash, include_projected_state=args.include_projected_state))
        elif args.cmd == "agent-context":
            scenes = [x.strip() for x in args.scenes.split(",") if x.strip()] if args.scenes else None
            domains = [x.strip() for x in args.domains.split(",") if x.strip()] if args.domains else None
            jprint(e.agent_context(scene_ids=scenes, domains=domains, include_schema=not args.no_schema))
        elif args.cmd == "agent-start":
            scenes = [x.strip() for x in args.scenes.split(",") if x.strip()] if args.scenes else None
            domains = [x.strip() for x in args.domains.split(",") if x.strip()] if args.domains else None
            jprint(e.agent_bootstrap(task=args.task, scene_ids=scenes, domains=domains, write=not args.no_write))
        elif args.cmd == "setup": jprint(e.setup_runtime())
        elif args.cmd == "subtitle-status": jprint(e.subtitle_status())
        elif args.cmd == "subtitle-optimize":
            ids = [x.strip() for x in args.captions.split(",") if x.strip()] if args.captions else None
            jprint(e.optimize_subtitle_layout(ids, include_dialogue=not args.no_dialogue))
        elif args.cmd == "staging-suggest": jprint(e.suggest_scene_staging(args.scene_id, count=args.count))
        elif args.cmd == "staging-order":
            ids = [x.strip() for x in args.characters.split(",") if x.strip()]
            jprint(e.stage_scene_by_order(args.scene_id, ids, minimum_confidence=args.minimum_confidence))
        elif args.cmd == "agent-checkpoint":
            scenes = [x.strip() for x in args.scenes.split(",") if x.strip()] if args.scenes else None
            domains = [x.strip() for x in args.domains.split(",") if x.strip()] if args.domains else None
            jprint(e.agent_checkpoint(goal=args.goal, active_scene_ids=scenes, domains=domains, decisions=args.decision))
        elif args.cmd == "auto-subtitles": jprint(e.auto_subtitles(args.asset_id, language=args.language, model=args.model, bilingual=args.bilingual, translate_to=args.translate_to, subtitle_style=args.style, position=args.position, speaker=args.speaker, offset=args.offset, max_segments=args.max_segments))
        elif args.cmd == "import-srt": jprint(e.import_subtitle_file(args.path, subtitle_style=args.style, position=args.position, speaker=args.speaker, offset=args.offset, secondary_path=args.secondary_path, secondary_language=args.secondary_language, parse_speakers=not args.no_parse_speakers, infer_styles=not args.no_infer_styles, smart_position=not args.no_smart_position))
        elif args.cmd == "export-plan": jprint(e.plan_export(width=args.width, height=args.height, fps=args.fps, container=args.container, codec=args.codec, encoder=args.encoder, quality=args.quality, upscale=args.upscale, interpolate=args.interpolate, content=args.content))
        elif args.cmd == "export": jprint(e.export_video(width=args.width, height=args.height, fps=args.fps, container=args.container, codec=args.codec, encoder=args.encoder, quality=args.quality, upscale=args.upscale, interpolate=args.interpolate, content=args.content, output=args.output, keep_intermediate=args.keep_intermediate))
        elif args.cmd == "video-mode": jprint(e.set_video_mode(args.preset))
        elif args.cmd == "gen3-config":
            cfg = {}
            if args.target_profile is not None: cfg["target_profile"] = args.target_profile
            if args.matte_key is not None: cfg["actor_matte_key"] = args.matte_key
            if args.renderer is not None: cfg["renderer"] = args.renderer
            if args.default_motion is not None: cfg["default_motion"] = args.default_motion
            if args.stillness_first is not None: cfg["stillness_first"] = args.stillness_first == "true"
            jprint(e.configure_gen3(**cfg))
        elif args.cmd == "gen3-scene": jprint(e.set_gen3_scene(args.scene_id, kind=args.kind, category=args.category, work_title=args.work_title, author=args.author, motion=args.motion))
        elif args.cmd == "gen3-card": jprint(e.set_gen3_card(args.scene_id, title=args.title, body=args.body, subtitle=args.subtitle, start=args.start, duration=args.duration, blur=not args.no_blur, category=args.category))
        elif args.cmd == "gen3-register-actor": jprint(e.register_gen3_actor_card(args.path, asset_id=args.id, key_color=args.key_color, make_shadow=not args.no_shadow))
        elif args.cmd == "gen3-place-actor": jprint(e.place_gen3_actor(args.scene_id, args.asset_id, x=args.x, floor_y=args.floor_y, scale=args.scale, end_x=args.end_x, end_floor_y=args.end_floor_y, shadow_asset_id=args.shadow_asset_id, z=args.z, opacity=args.opacity))
        elif args.cmd == "gen3-compile":
            ids=[x.strip() for x in args.scenes.split(",") if x.strip()] if args.scenes else None
            jprint(e.compile_gen3(ids))
        elif args.cmd == "gen3-remotion": jprint(e.export_gen3_remotion(args.output_dir))
        elif args.cmd == "remotion-register":
            schema = json.loads(Path(args.props_schema).read_text(encoding="utf-8")) if args.props_schema else None
            jprint(e.register_remotion_component(args.source, component_id=args.id, export_name=args.export_name, props_schema=schema))
        elif args.cmd == "remotion-bind":
            props = json.loads(Path(args.props).read_text(encoding="utf-8")) if args.props else None
            jprint(e.bind_remotion_component(args.scene_id, args.component_id, start=args.start, duration=args.duration, props=props, z=args.z, binding_id=args.binding_id))
        elif args.cmd == "remotion-verify": jprint(e.verify_remotion_bundle(args.output_dir))
        elif args.cmd == "efficiency-start":
            metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8")) if args.metadata else None
            jprint(e.efficiency_start(arm=args.arm, task_id=args.task_id, metadata=metadata))
        elif args.cmd == "efficiency-finish":
            usage = json.loads(Path(args.actual_usage).read_text(encoding="utf-8")) if args.actual_usage else None
            jprint(e.efficiency_finish(args.session_id, actual_usage=usage, elapsed_seconds=args.elapsed_seconds, tool_calls=args.tool_calls, failed_commands=args.failed_commands, rendered_frames=args.rendered_frames, qa_issues=args.qa_issues, notes=args.notes))
        elif args.cmd == "efficiency-measure":
            ops = json.loads(Path(args.operations).read_text(encoding="utf-8")) if args.operations else []
            jprint(e.efficiency_measure(ops))
        elif args.cmd == "efficiency-report": jprint(e.efficiency_report())
        elif args.cmd == "add-asset": jprint(e.add_asset(args.path, asset_id=args.id, copy=not args.no_copy))
        elif args.cmd == "add-scene": jprint(e.add_scene(args.asset_id, args.duration, scene_id=args.id, after=args.after, source_in=args.source_in, playback_rate=args.playback_rate))
        elif args.cmd == "delete-scene": jprint(e.delete_scene(args.scene_id))
        elif args.cmd == "source": jprint(e.set_source(args.scene_id, source_in=args.source_in, playback_rate=args.playback_rate))
        elif args.cmd == "camera": jprint(e.set_camera(args.scene_id, motion=args.motion, amount=args.amount, easing=args.easing, anchor=args.anchor))
        elif args.cmd == "analyze-visual": jprint(e.analyze_visual(args.asset_id, sample_count=args.samples))
        elif args.cmd == "composition-plan":
            visual = e.analyze_scene_visual(args.scene_id, sample_count=args.samples) if args.analyze else None
            jprint(e.suggest_composition(args.scene_id, text_hint=args.text, visual=visual))
        elif args.cmd == "auto-compose":
            ids = [x.strip() for x in args.scenes.split(",") if x.strip()] if args.scenes else None
            jprint(e.auto_compose_scenes(ids, sample_count=args.samples))
        elif args.cmd == "cinematic-plan": jprint(e.suggest_cinematic_treatment(args.scene_id, intent=args.intent))
        elif args.cmd == "cinematic-frame": jprint(e.set_cinematic_frame(args.scene_id, preset=args.preset, frame_easing=args.easing))
        elif args.cmd == "fragment": jprint(e.fragment_scene(args.scene_id, style=args.style, count=args.count, intensity=args.intensity))
        elif args.cmd == "cinematic": jprint(e.apply_cinematic_treatment(args.scene_id, style=args.style, count=args.count, intensity=args.intensity))
        elif args.cmd == "effect": jprint(e.add_effect(args.scene_id, args.effect, intensity=args.intensity, speed=args.speed, direction=args.direction, depth=args.depth, opacity=args.opacity, seed=args.seed))
        elif args.cmd == "remove-effect": jprint(e.remove_effect(args.scene_id, args.index))
        elif args.cmd == "transition": jprint(e.set_transition(args.scene_id, args.type, args.duration))
        elif args.cmd == "caption": jprint(e.add_caption(args.text, args.start, args.end, speaker=args.speaker, position=args.position))
        elif args.cmd == "audio": jprint(e.add_audio_track(args.asset_id, kind=args.kind, volume_db=args.volume_db, start=args.start, duration=args.duration, fade_in=args.fade_in, fade_out=args.fade_out, loop=args.loop))
        elif args.cmd == "scene-audio": jprint(e.add_scene_audio(args.scene_id, args.asset_id, kind=args.kind, volume_db=args.volume_db, start=args.start, duration=args.duration, fade_in=args.fade_in, fade_out=args.fade_out, loop=args.loop))
        elif args.cmd == "render": jprint(e.render_profile(args.profile, args.output))
        elif args.cmd == "render-scene": jprint(e.render_scene(args.scene_id, args.output, profile=args.profile))
        elif args.cmd == "render-span": jprint(e.render_span(args.start_scene, args.end_scene, args.output, profile=args.profile))
        elif args.cmd == "qa": jprint(e.qa(args.rendered))
        return 0
    except (AgentCutError, json.JSONDecodeError) as exc:
        if isinstance(exc, AgentCutError):
            print(str(exc), file=sys.stderr)
        else:
            print(json.dumps({"error": "INVALID_JSON", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except ModuleNotFoundError as exc:
        print(json.dumps({
            "error": "MISSING_PYTHON_DEPENDENCY",
            "dependency": exc.name,
            "message": str(exc),
            "fix": "python -m pip install -e './AgentCut[render]' (use [api] for server dependencies)",
        }, ensure_ascii=False), file=sys.stderr)
        return 2
    except OSError as exc:
        print(json.dumps({"error": "FILESYSTEM_ERROR", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(json.dumps({"error": "INTERRUPTED", "message": "Cancelled; rerun the same roughcut job to resume."}), file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
