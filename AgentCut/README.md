# AgentCut

AI-native semantic video editing runtime.

Current baseline: **v0.2.0-alpha.8**.

Highlights:
- API-first semantic editing, deterministic FFmpeg rendering, history/checkpoints/rollback.
- 130-entry queryable content library, including 40 transitions.
- rendered `shared_morph` and deterministic rhythm-aware scene planning.
- cinematic composition: `cover`, `contain`, `native_window`, `ambient`.
- **deterministic visual saliency analysis** for image/video scene segments.
- **focus-aware real FFmpeg crop**: planned `focus_x/focus_y` now affect rendered pixels.
- guarded dynamic `focus_path` tracking for continuously moving subjects.
- subject crop-risk preservation and nine-zone visually safe text placement.
- dialogue `position="auto"` and bulk `auto_compose_scenes()` workflow.
- composition-aware scene cache invalidation.
- compact Agent Context Pack, hierarchical Render DAG and QA.

Validation: **57/57 tests passed across grouped regression runs**, `agentcut doctor` pass. Real focus-aware crop, dynamic focus tracking and integrated three-scene smoke render all passed.

Full Alpha 8 source handoff is stored in Google Drive folder `AgentCut_v0.2.0-alpha.8_Handoff`.

Read `V0.2_ALPHA8_NOTES.md`, `ALPHA8_PRACTICAL_WORKFLOW.md` and `VALIDATION_SUMMARY_A8.md` before continuing development.
