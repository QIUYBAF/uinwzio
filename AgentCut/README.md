# AgentCut

AI-native semantic video editing runtime.

Current baseline: **v0.2.0-alpha.7**.

Highlights:
- API-first semantic editing, deterministic FFmpeg rendering, history/checkpoints/rollback.
- 130-entry queryable content library, including 40 transitions.
- subpixel perspective+cubic camera backend.
- object-level graphics layers and keyframes.
- rendered `shared_morph` for matching `shared_id` layers.
- deterministic audio tempo/onset/beat analysis and rhythm-aware scene planning.
- **Cinematic Composition**: `cover`, `contain`, `native_window`, `ambient`.
- automatic composition planning from source geometry/resolution plus optional focus tags.
- nine-zone composition-aware caption placement.
- compact Agent Context Pack + Project Facts.
- hierarchical Render DAG and QA.

Validation: **48/48 tests passed across grouped regression runs**, `agentcut doctor` pass.

Full Alpha 7 source handoff is stored in Google Drive folder `AgentCut_v0.2.0-alpha.7_Handoff`.

Read `V0.2_ALPHA7_NOTES.md` and `VALIDATION_SUMMARY_A7.md` before continuing development.
