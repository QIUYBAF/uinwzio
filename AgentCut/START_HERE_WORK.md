# START HERE — AgentCut 3.0.0

Cross-conversation / Work / Codex handoff entry.

## Current stable baseline

**3.0.0** — first non-alpha release of the current AgentCut line.

Validation:
- **82 / 82 automated tests passed**
- `agentcut doctor`: pass
- flexible MP4/H.264, WebM/VP9, MOV/ProRes, MKV/HEVC real exports: pass
- generalized 3840×2160@60 path: real export pass
- fallback frame interpolation + scaling chain: real render pass with duration invariants preserved
- optional Real-ESRGAN/RIFE adapters: integration/discovery/install contracts validated; actual neural inference requires those external backends on the execution machine

Full source Handoff: Google Drive folder `AgentCut_v3.0.0_Handoff`.

Read in this order:
1. `README.md`
2. `V3.0_RELEASE_NOTES.md`
3. `V3_EXPORT_PROTOCOL.md`
4. `V3_AI_ENHANCEMENT.md`
5. `VALIDATION_SUMMARY_V3.md`
6. `ALPHA10_AGENT_RELIABILITY.md`
7. `ALPHA9_CINEMATIC_WORKFLOW.md`

## Preferred Agent workflow

```text
read state/capabilities
→ edit through Reliability Gateway
→ local render / inspect / QA
→ export-plan
→ inspect normalized target, warnings and actual backend choices
→ export
→ verify .agentcut-export.json + ffprobe result
```

## 3.0 delivery rules

- Export settings do not silently mutate canonical editing state.
- Container/codec compatibility is validated before expensive work.
- `encoder=auto` requires a real hardware-encoder runtime probe.
- Optional AI absence must not break `auto` export.
- A deterministic fallback must never be reported as AI.
- Hard cuts are interpolation barriers.
- Every enhancement/export stage must preserve canonical duration within tolerance.
- Final geometry and fps must match the normalized requested spec.
- 4K60 is the official validated ceiling; higher guarded values are experimental.

## Architecture invariants

1. `project.json` remains canonical.
2. Agent operations remain semantic, versioned and reversible.
3. Source assets remain non-destructive.
4. Ambiguous artistic choices are never silently fuzzy-corrected.
5. Cache keys include semantic inputs that affect pixels/audio.
6. QA/manifests report actual results rather than intended results.
7. Cinematic discontinuity remains an accent; continuity remains first-class.

Product criterion: prefer fewer dependable operations and honest fallbacks over decorative feature count.
