# START HERE — AgentCut v0.2.0-alpha.9

Cross-conversation / Work / Codex handoff entry.

## Definition

AgentCut is an **AI-native video editing runtime**, not a traditional NLE GUI project.

```text
intent → semantic operations → canonical project.json → deterministic renderer → inspect/QA → local correction/rollback
```

## Current baseline

**v0.2.0-alpha.9**

Validation:
- **63 / 63 grouped tests passed**
- `agentcut doctor`: pass
- real moving aspect-ratio render: pass
- real focus-aware crop zoom: pass
- duration-preserving fragment montage: pass
- integrated memory-shards render: pass

Full source Handoff: Google Drive folder `AgentCut_v0.2.0-alpha.9_Handoff`.

Read in this order:

1. `README.md`
2. `V0.2_ALPHA9_NOTES.md`
3. `ALPHA9_CINEMATIC_WORKFLOW.md`
4. `VALIDATION_SUMMARY_A9.md`
5. `V0.2_ALPHA8_NOTES.md`
6. `ALPHA8_PRACTICAL_WORKFLOW.md`
7. `VALIDATION_SUMMARY_A8.md`
8. `V0.2_ALPHA7_NOTES.md`

## Alpha 9 cinematic additions

- dynamic in-shot aspect ratio (`scope_lock`, `scope_reveal`, `impact_pulse`, `scope_hold`)
- immediate focus-aware `crop_zoom` for hard-cut closeups
- duration-preserving `impact_cluster` / `detail_burst` fragmentation
- non-linear video `memory_shards`
- semantic treatment planner and CLI commands
- QA guardrails against unreadably short fragments / over-stacked motion
- moving-bar exact-duration guard
- fixed contact-sheet extraction on current FFmpeg

## Alpha 8 practical additions

- deterministic visual saliency analysis
- focus-aware real `cover` crop
- guarded dynamic `focus_path`
- subject crop-risk planning
- visual-safe caption/dialogue placement
- `position="auto"` for dialogue
- project/scene bulk auto composition
- composition-aware render cache key
- QA for stacked tracking/camera movement

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
14. Cache keys must include every semantic input that affects pixels/audio.
15. Automatic visual decisions must remain overridable by explicit artistic intent.
16. Cinematic discontinuity is an accent; clean continuity remains a first-class choice.

## Product criterion

Before adding a feature ask:

> Does this make the Agent more reliably able to read, edit, verify and locally correct a real video?

Prefer fewer dependable operations over decorative feature count.
