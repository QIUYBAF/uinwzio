# START HERE — AgentCut 3.2.2

Cross-conversation / Work / Codex handoff entry.

## Stable baseline

**3.2.2** — production-friction pass after EP07 Nether practical testing.

Validation:
- **135 / 135 tests passed**
- `agentcut doctor`: pass
- EP07 57.37 s bilingual diagnostic proxy: render + QA pass
- bundled Real-ESRGAN retained

## Restart / upgrade first step

Do **not** reread all docs or the full operation schema.

```text
agentcut agent-start PROJECT
```

Protocol v5 modes:
- `warm_resume`: project-local checkpoint/last receipt remain valid across normal edits;
- `upgrade_resume`: read only `schema_delta.added/changed/removed` plus release delta;
- `cold_resume`: request task-scoped `/agent/context`, not the whole project unless needed.

Use `agent-checkpoint` to persist goals/decisions, never raw conversation history.

## Practical editing loop

```text
agent-start
→ task-scoped context
→ preflight
→ apply with expected_project_hash
→ proxy scene/span/full according to verification plan
→ QA + visual inspection
→ final export only after proxy is stable
```

## Subtitle rules

- Import SRT with Cast-aware speaker parsing.
- Use structured `secondary_text` for bilingual captions.
- Auto-fit changes layout only, not text/timing.
- If QA emits `BILINGUAL_SPLIT_RECOMMENDED`, split/shorten the cue; do not shrink text further.

## Staging rules

- `suggest_scene_staging` returns anonymous anchors only.
- `stage_scene_by_order` requires explicit Cast order before writing coordinates.
- Never infer character identity purely from deterministic saliency.

## ASR

Windows x64 one-time sidecar:

```text
agentcut asr-install --accept-third-party
```

Backend/model live outside the project and persist across AgentCut upgrades.

Full source Handoff: Google Drive folder `AgentCut_v3.2.2_Handoff`. Prefer it over reconstructing from old Alpha folders.