# START HERE — AgentCut v0.2.0-alpha.10

Cross-conversation / Work / Codex handoff entry.

## Current baseline

**v0.2.0-alpha.10**

Validation:
- **71 / 71 tests passed**
- `agentcut doctor`: pass
- real 3840×2160 @ 60 fps render with camera motion + cinematic frame + caption: pass
- full Alpha 8/9 regression: pass

Full source Handoff: Google Drive folder `AgentCut_v0.2.0-alpha.10_Handoff`.

Read in this order:
1. `README.md`
2. `V0.2_ALPHA10_NOTES.md`
3. `ALPHA10_AGENT_RELIABILITY.md`
4. `VALIDATION_SUMMARY_A10.md`
5. `V0.2_ALPHA9_NOTES.md`
6. `ALPHA9_CINEMATIC_WORKFLOW.md`

## Alpha 10: preferred Agent control path

Do not require the model to memorize every exact operation/parameter name. Prefer:

```text
read state_digest + operation_schema
→ agent/preflight
→ inspect repairs/warnings
→ agent/apply with expected_project_hash
→ render affected scene/span
→ QA + inspect
→ local correction / undo
```

The Reliability Gateway only auto-repairs deterministic naming drift. Ambiguous creative choices stay explicit errors/suggestions.

## UHD

Semantic canvas modes include `1080p30`, `1080p60`, `4k30`, `4k60`.

Official render profiles include `uhd_4k30` and `uhd_4k60`. UHD camera motion uses native-resolution cubic perspective; 720p/1080p retains Alpha 9's 2× supersampled cubic path.

## Architecture invariants — do not break

1. `project.json` is canonical state.
2. Agent-facing API stays semantic.
3. Agent does not write raw filter graphs.
4. Source assets stay non-destructive.
5. Random effects have explicit seeds.
6. Errors stay machine-readable.
7. Mutations stay versioned with rollback.
8. Batch edits stay atomic.
9. Agent can always re-read state.
10. Preview/final remain separate.
11. QA reports problems but does not silently rewrite artistic intent.
12. GUI is not the core state layer.
13. Capability claims must correspond to renderer behavior.
14. Cache keys must include every semantic input affecting pixels/audio.
15. Automatic visual decisions remain overridable by explicit artistic intent.
16. Cinematic discontinuity is an accent; clean continuity remains first-class.
17. Reliability normalization may repair syntax/naming, never ambiguous artistic intent.

## Product criterion

Prefer fewer dependable operations over feature count. Every change should make the Agent more reliably able to read, edit, verify and locally correct a real video.
