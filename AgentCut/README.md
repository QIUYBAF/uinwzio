# AgentCut

AI-native semantic video editing runtime.

Current baseline: **v0.2.0-alpha.6**.

Highlights:
- API-first semantic editing, deterministic FFmpeg rendering, history/checkpoints/rollback.
- 130-entry queryable content library.
- subpixel perspective+cubic camera backend.
- object-level graphics layers and keyframes.
- real `shared_morph` rendering for matching `shared_id` layers.
- lightweight audio tempo/onset/beat analysis and rhythm-aware scene-duration planning.
- compact Agent Context Pack + Project Facts.
- hierarchical Render DAG and QA.

Validation: **45/45 tests passed**, doctor pass.

For the alpha.6 delta read `V0.2_ALPHA6_NOTES.md`. For the complete frozen source snapshot use `releases/AgentCut_v0.2.0-alpha.6_source.zip`.
