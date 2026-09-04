from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .doctor import run_doctor
from .editor import Editor
from .errors import AgentCutError
from .manifest import manifest_path
from . import __version__


class Operation(BaseModel):
    action: str
    args: dict = Field(default_factory=dict)


class Transaction(BaseModel):
    # Agent Protocol v5 accepts canonical arrays, a singleton operation object, or {operations:[...]}.
    operations: list[dict] | dict
    expected_project_hash: str | None = None
    dry_run: bool = False
    include_projected_state: bool = False
    include_project: bool = False


class ExportRequest(BaseModel):
    width: int
    height: int
    fps: float
    container: str = "mp4"
    codec: str = "h264"
    encoder: str = "auto"
    quality: int = 18
    upscale: str = "auto"
    interpolate: str = "auto"
    content: str = "anime"
    output: str | None = None
    keep_intermediate: bool = False


class AutoSubtitleRequest(BaseModel):
    asset_id: str
    language: str = "auto"
    model: str | None = None
    bilingual: bool = False
    translate_to: str = "en"
    subtitle_style: str = "bilingual"
    position: str = "bottom"
    speaker: str | None = None
    offset: float = 0.0
    max_segments: int | None = None
    replace_existing: bool = True
    use_cache: bool = True
    auto_fit: bool = True


class AgentCheckpointRequest(BaseModel):
    goal: str | None = None
    active_scene_ids: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)


class StagingOrderRequest(BaseModel):
    character_ids: list[str]
    minimum_confidence: float = 0.18


class SubtitleOptimizeRequest(BaseModel):
    caption_ids: list[str] | None = None
    include_dialogue: bool = True


class RemotionRegisterRequest(BaseModel):
    source: str
    component_id: str
    export_name: str = "default"
    props_schema: dict | None = None


class RemotionBindRequest(BaseModel):
    scene_id: str
    component_id: str
    start: float
    duration: float
    props: dict = Field(default_factory=dict)
    z: int = 50
    binding_id: str | None = None


class RemotionExportRequest(BaseModel):
    output_dir: str | None = None


class EfficiencyStartRequest(BaseModel):
    arm: str
    task_id: str
    metadata: dict = Field(default_factory=dict)


class EfficiencyFinishRequest(BaseModel):
    actual_usage: dict | None = None
    elapsed_seconds: float | None = None
    tool_calls: int | None = None
    failed_commands: int | None = None
    rendered_frames: int | None = None
    qa_issues: int | None = None
    notes: str | None = None


class EfficiencyMeasureRequest(BaseModel):
    operations: list[dict] = Field(default_factory=list)


def create_app(root: str | Path) -> FastAPI:
    editor = Editor(root)
    app = FastAPI(title="AgentCut Agent API", version=__version__)
    lock = threading.RLock()

    def safe_project_file(value: str | None, default: Path) -> Path:
        candidate = Path(value) if value else default
        if not candidate.is_absolute():
            candidate = editor.root / candidate
        candidate = candidate.resolve()
        try:
            candidate.relative_to(editor.root)
        except ValueError as exc:
            raise AgentCutError("PATH_OUTSIDE_PROJECT", "HTTP inspection is sandboxed to the project root", path=str(candidate), project_root=str(editor.root)) from exc
        return candidate

    def render_payload(path: Path) -> dict:
        return {
            "path": str(path),
            "manifest": str(manifest_path(path)),
            "state": editor.state_digest(),
        }

    @app.exception_handler(AgentCutError)
    async def agentcut_error_handler(_, exc: AgentCutError):
        return __import__("fastapi").responses.JSONResponse(status_code=400, content=exc.as_dict())

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/doctor")
    def doctor():
        return run_doctor()

    @app.get("/capabilities")
    def capabilities():
        with lock:
            return editor.list_capabilities()

    @app.get("/state-digest")
    def state_digest():
        with lock:
            return editor.state_digest()

    @app.get("/project")
    def project():
        with lock:
            return editor.get_project()

    @app.get("/timeline")
    def timeline():
        with lock:
            return editor.get_timeline()

    @app.get("/assets")
    def assets():
        with lock:
            return editor.get_assets()

    @app.get("/audio-mix")
    def audio_mix():
        with lock:
            return editor.get_audio_mix()

    @app.get("/scenes/{scene_id}")
    def scene(scene_id: str):
        with lock:
            return editor.get_scene(scene_id)

    @app.get("/versions")
    def versions():
        with lock:
            return editor.versions()

    @app.get("/checkpoints")
    def checkpoints():
        with lock:
            return editor.checkpoints()

    @app.post("/checkpoints/{name}")
    def create_checkpoint(name: str, note: str | None = None):
        with lock:
            return editor.create_checkpoint(name, note=note)

    @app.post("/checkpoints/{name}/restore")
    def restore_checkpoint(name: str):
        with lock:
            return {"project": editor.restore_checkpoint(name), "state": editor.state_digest()}

    @app.get("/scenes/{scene_id}/history")
    def scene_history(scene_id: str):
        with lock:
            return editor.scene_history(scene_id)

    @app.post("/scenes/{scene_id}/restore-checkpoint/{checkpoint}")
    def restore_scene_checkpoint(scene_id: str, checkpoint: str):
        with lock:
            return {"scene": editor.restore_scene(scene_id, checkpoint=checkpoint), "state": editor.state_digest()}

    @app.post("/undo")
    def undo():
        with lock:
            return {"project": editor.undo(), "state": editor.state_digest()}

    @app.post("/redo")
    def redo():
        with lock:
            return {"project": editor.redo(), "state": editor.state_digest()}

    @app.get("/agent/context")
    def agent_context(scene_ids: str | None = None, domains: str | None = None, include_schema: bool = True):
        with lock:
            scenes = [x.strip() for x in scene_ids.split(",") if x.strip()] if scene_ids else None
            domain_list = [x.strip() for x in domains.split(",") if x.strip()] if domains else None
            return editor.agent_context(scene_ids=scenes, domains=domain_list, include_schema=include_schema)

    @app.get("/agent/bootstrap")
    def agent_bootstrap(task: str | None = None, scene_ids: str | None = None, domains: str | None = None, write: bool = True):
        with lock:
            scenes = [x.strip() for x in scene_ids.split(",") if x.strip()] if scene_ids else None
            domain_list = [x.strip() for x in domains.split(",") if x.strip()] if domains else None
            return editor.agent_bootstrap(task=task, scene_ids=scenes, domains=domain_list, write=write)

    @app.post("/runtime/setup")
    def runtime_setup():
        with lock:
            return editor.setup_runtime()

    @app.post("/agent/checkpoint")
    def agent_checkpoint(req: AgentCheckpointRequest):
        with lock:
            return editor.agent_checkpoint(goal=req.goal, active_scene_ids=req.active_scene_ids, domains=req.domains, decisions=req.decisions)

    @app.get("/staging/{scene_id}/suggest")
    def staging_suggest(scene_id: str, count: int | None = None):
        with lock:
            return editor.suggest_scene_staging(scene_id, count=count)

    @app.post("/staging/{scene_id}/by-order")
    def staging_by_order(scene_id: str, req: StagingOrderRequest):
        with lock:
            return editor.stage_scene_by_order(scene_id, req.character_ids, minimum_confidence=req.minimum_confidence)

    @app.get("/subtitles/status")
    def subtitle_status():
        with lock:
            return editor.subtitle_status()

    @app.post("/subtitles/optimize")
    def subtitle_optimize(req: SubtitleOptimizeRequest):
        with lock:
            return editor.optimize_subtitle_layout(req.caption_ids, include_dialogue=req.include_dialogue)

    @app.post("/subtitles/auto")
    def auto_subtitles(req: AutoSubtitleRequest):
        with lock:
            return editor.auto_subtitles(req.asset_id, language=req.language, model=req.model, bilingual=req.bilingual, translate_to=req.translate_to, subtitle_style=req.subtitle_style, position=req.position, speaker=req.speaker, offset=req.offset, max_segments=req.max_segments, replace_existing=req.replace_existing, use_cache=req.use_cache, auto_fit=req.auto_fit)

    @app.get("/agent/operation-schema")
    def agent_operation_schema(domains: str | None = None, actions: str | None = None):
        with lock:
            domain_list = [x.strip() for x in domains.split(",") if x.strip()] if domains else None
            action_list = [x.strip() for x in actions.split(",") if x.strip()] if actions else None
            return editor.operation_schema(domains=domain_list, actions=action_list)

    @app.post("/agent/preflight")
    def agent_preflight(tx: Transaction):
        with lock:
            return editor.preflight_operations(
                tx.operations,
                expected_project_hash=tx.expected_project_hash,
                include_projected_state=tx.include_projected_state,
            )

    @app.post("/agent/apply")
    def agent_apply(tx: Transaction):
        with lock:
            return editor.apply_agent_operations(
                tx.operations,
                expected_project_hash=tx.expected_project_hash,
                dry_run=tx.dry_run,
                include_project=tx.include_project,
            )

    @app.post("/operations/batch")
    def operation_batch(ops: list[Operation]):
        with lock:
            return editor.apply_operations([op.model_dump() for op in ops])

    @app.post("/operations/transaction")
    def operation_transaction(tx: Transaction):
        with lock:
            if not isinstance(tx.operations, list):
                raise AgentCutError("INVALID_OPERATIONS", "Strict transaction endpoint requires an operations array")
            return editor.apply_operations(
                tx.operations,
                expected_project_hash=tx.expected_project_hash,
                dry_run=tx.dry_run,
            )

    @app.post("/operations")
    def operation(op: Operation):
        with lock:
            result = editor.apply_operation(op.action, op.args)
            return {"result": result, "state": editor.state_digest()}

    @app.post("/remotion/components/register")
    def remotion_register(req: RemotionRegisterRequest):
        with lock:
            source = safe_project_file(req.source, editor.root / req.source)
            return editor.register_remotion_component(source, component_id=req.component_id, export_name=req.export_name, props_schema=req.props_schema)

    @app.post("/remotion/bindings")
    def remotion_bind(req: RemotionBindRequest):
        with lock:
            return editor.bind_remotion_component(req.scene_id, req.component_id, start=req.start, duration=req.duration, props=req.props, z=req.z, binding_id=req.binding_id)

    @app.delete("/remotion/bindings/{binding_id}")
    def remotion_remove(binding_id: str):
        with lock:
            return editor.remove_remotion_binding(binding_id)

    @app.post("/remotion/export")
    def remotion_export(req: RemotionExportRequest):
        with lock:
            output = safe_project_file(req.output_dir, editor.root / "remotion_gen3") if req.output_dir else None
            return editor.export_gen3_remotion(str(output) if output else None)

    @app.post("/remotion/verify")
    def remotion_verify(req: RemotionExportRequest):
        with lock:
            output = safe_project_file(req.output_dir, editor.root / "remotion_gen3") if req.output_dir else None
            return editor.verify_remotion_bundle(str(output) if output else None)

    @app.post("/efficiency/sessions/start")
    def efficiency_start(req: EfficiencyStartRequest):
        with lock:
            return editor.efficiency_start(arm=req.arm, task_id=req.task_id, metadata=req.metadata)

    @app.post("/efficiency/sessions/{session_id}/finish")
    def efficiency_finish(session_id: str, req: EfficiencyFinishRequest):
        with lock:
            return editor.efficiency_finish(session_id, actual_usage=req.actual_usage, elapsed_seconds=req.elapsed_seconds, tool_calls=req.tool_calls, failed_commands=req.failed_commands, rendered_frames=req.rendered_frames, qa_issues=req.qa_issues, notes=req.notes)

    @app.post("/efficiency/measure")
    def efficiency_measure(req: EfficiencyMeasureRequest):
        with lock:
            return editor.efficiency_measure(req.operations)

    @app.get("/efficiency/report")
    def efficiency_report():
        with lock:
            return editor.efficiency_report()

    @app.get("/cache")
    def cache_info():
        with lock:
            return editor.cache_info()

    @app.post("/cache/clear")
    def cache_clear():
        with lock:
            return editor.clear_cache()

    @app.get("/enhancement/status")
    def enhancement_status():
        with lock:
            return editor.enhancement_status()

    @app.post("/export/plan")
    def export_plan(req: ExportRequest):
        with lock:
            return editor.plan_export(width=req.width, height=req.height, fps=req.fps, container=req.container, codec=req.codec, encoder=req.encoder, quality=req.quality, upscale=req.upscale, interpolate=req.interpolate, content=req.content)

    @app.post("/export")
    def export_video(req: ExportRequest):
        with lock:
            output = None
            if req.output:
                output = safe_project_file(req.output, editor.root / "output" / f"export.{req.container}")
            return editor.export_video(width=req.width, height=req.height, fps=req.fps, container=req.container, codec=req.codec, encoder=req.encoder, quality=req.quality, upscale=req.upscale, interpolate=req.interpolate, content=req.content, output=output, keep_intermediate=req.keep_intermediate)

    @app.post("/render/preview")
    def render_preview():
        with lock:
            return render_payload(editor.render_preview())

    @app.post("/render/final")
    def render_final():
        with lock:
            return render_payload(editor.render_final())

    @app.post("/render/4k60")
    def render_4k60():
        with lock:
            return render_payload(editor.render_4k60())

    @app.post("/render/scene/{scene_id}")
    def render_scene(scene_id: str):
        with lock:
            return render_payload(editor.render_scene(scene_id))

    @app.post("/render/span/{start_scene}/{end_scene}")
    def render_span(start_scene: str, end_scene: str):
        with lock:
            return render_payload(editor.render_span(start_scene, end_scene))

    @app.get("/qa")
    def qa(rendered: str | None = None):
        with lock:
            source = safe_project_file(rendered, editor.root / "preview" / "preview.mp4") if rendered else None
            return editor.qa(source)

    @app.get("/inspect/frame")
    def inspect_frame(time: float, video: str | None = None):
        from .inspect import extract_frame
        with lock:
            source = safe_project_file(video, editor.root / "preview" / "preview.mp4")
            target = editor.root / "preview" / f"frame_{time:.3f}.jpg"
            return {"path": str(extract_frame(source, target, time=time)), "time": time}

    @app.get("/inspect/contact-sheet")
    def inspect_sheet(interval: float = 2.0, video: str | None = None):
        from .inspect import inspect_contact_sheet
        with lock:
            source = safe_project_file(video, editor.root / "preview" / "preview.mp4")
            target = editor.root / "preview" / "contact_sheet.jpg"
            return {"path": str(inspect_contact_sheet(source, target, interval=interval)), "interval": interval}

    return app


def run_server(root: str | Path, host: str = "127.0.0.1", port: int = 8765):
    import uvicorn
    uvicorn.run(create_app(root), host=host, port=port)
