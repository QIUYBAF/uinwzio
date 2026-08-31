# START HERE — AgentCut 3.0.1

Cross-conversation / Work / Codex handoff entry.

## Current stable baseline

**3.0.1**.

Validation:
- **85 / 85 automated tests passed**
- `agentcut doctor`: pass
- flexible MP4/H.264, WebM/VP9, MOV/ProRes, MKV/HEVC real exports: pass
- generalized 3840×2160@60 path: real export pass
- fallback frame interpolation + scaling chain: real render pass with duration invariants preserved
- slim Real-ESRGAN executable/models are bundled for Windows/Linux and SHA-verified
- current cloud has no usable Vulkan device, so bundled inference attempts safely fall back under `auto`
- RIFE adapter remains optional/external

Full source Handoff: Google Drive folder `AgentCut_v3.0.1_Handoff`.

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

## 3.0.1 delivery/enhancement rules

- Export settings do not silently mutate canonical editing state.
- Container/codec compatibility is validated before expensive work.
- `encoder=auto` requires a real hardware-encoder runtime probe.
- Real-ESRGAN discovery priority: explicit env path → PATH → bundled slim runtime → user backend root.
- Bundled Real-ESRGAN contains AnimeVideo-v3 x2/x4 only; general/photo models remain external.
- AI absence or runtime initialization failure must not break `auto` export.
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
7. Bundled third-party binaries/models retain upstream license and SHA256 manifests.
8. Cinematic discontinuity remains an accent; continuity remains first-class.

Product criterion: prefer fewer dependable operations and honest fallbacks over decorative feature count.
