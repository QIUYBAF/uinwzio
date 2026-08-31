# START HERE — AgentCut 3.0.2

Cross-conversation / Work / Codex handoff entry.

## Current stable baseline

**3.0.2**.

Validation:
- **96 / 96 automated tests passed**
- `agentcut doctor`: pass
- generalized 3840×2160@60 export: pass
- MP4/H.264, WebM/VP9, MOV/ProRes, MKV/HEVC: pass
- bundled slim Real-ESRGAN Windows/Linux + AnimeVideo-v3 x2/x4: packaged and SHA-verified
- current cloud has no usable Vulkan device, so Real-ESRGAN runtime-failure → honest `auto` fallback is the executed validation path
- RIFE remains optional/external

Full source Handoff: Google Drive folder `AgentCut_v3.0.2_Handoff`.

Read in this order:
1. `README.md`
2. `AGENT_PROTOCOL.md`
3. `VALIDATION_SUMMARY_V3.md`
4. `V3_AI_ENHANCEMENT.md`
5. `V3_EXPORT_PROTOCOL.md`
6. `ALPHA10_AGENT_RELIABILITY.md`
7. `ALPHA9_CINEMATIC_WORKFLOW.md`

## Preferred Agent workflow — Protocol v2

```text
GET /agent/context (optionally filter domains/scenes)
→ POST /agent/preflight
→ inspect deterministic repairs + change impact + verification plan
→ POST /agent/apply with expected_project_hash
→ render recommended scene/span/full scope
→ QA + inspect relevant frames
→ export-plan → export when delivery is requested
```

Do not require the model to memorize the exact JSON shape. The Agent gateway accepts canonical operations plus deterministic `operation/op/tool`, `params/arguments`, flattened args, singleton/root wrappers and uniquely high-confidence syntax typos. Ambiguous creative choices remain explicit.

Preflight is compact by default: full projected state is opt-in. Apply also returns a compact transaction receipt unless full project/results are explicitly requested.

## Architecture invariants

1. `project.json` remains canonical.
2. Agent operations remain semantic, versioned and reversible.
3. Source assets remain non-destructive.
4. Syntax/naming drift may be repaired; ambiguous artistic intent may not.
5. Preflight precedes mutation and reports impact/render scope.
6. QA/manifests report actual results rather than intended results.
7. Optional AI failure must not break `auto` export.
8. Fallback processing must never be reported as AI.
9. Hard cuts remain interpolation barriers.
10. Bundled third-party binaries/models retain upstream license and SHA256 manifests.

Product criterion: prefer dependable, low-context Agent interaction over decorative feature count.
