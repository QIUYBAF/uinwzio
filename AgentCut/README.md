# AgentCut v0.2.0-alpha.10

**Agent-native semantic video editing runtime.**

Current baseline: **v0.2.0-alpha.10**.

Validation:
- **71 / 71 automated tests passed**
- `agentcut doctor`: pass
- real **3840×2160 @ 60 fps** motion + cinematic-frame + caption render: pass
- Alpha 8/9 visual analysis and cinematic grammar regression: pass

## Alpha 10 focus: fewer Agent failures

Alpha 10 adds an **Agent Reliability Gateway** instead of adding more decorative editing features.

Preferred loop:

```text
state_digest + operation_schema
        ↓
agent/preflight
        ↓
review normalized_operations / repairs / warnings
        ↓
agent/apply with expected_project_hash
        ↓
local render + QA + inspection
```

New entry points:

```python
editor.operation_schema()
editor.preflight_operations(operations)
editor.apply_agent_operations(operations)
```

HTTP:
- `GET /agent/operation-schema`
- `POST /agent/preflight`
- `POST /agent/apply`

The gateway deterministically normalizes safe naming drift such as `scene -> scene_id`, `transition -> set_transition`, and `type -> transition` where the action makes the meaning unambiguous. It validates arguments against the real Python signature and surfaces nearby Library IDs for bad preset names.

It **does not silently fuzzy-correct artistic intent**. If `cinematic_cool` could plausibly mean either `cool` or `cinematic_contrast`, the Agent receives suggestions and must choose.

A deterministic adversarial fixture of 11 non-canonical but semantically clear LLM-style calls produced:
- strict legacy acceptance: **0 / 11**
- Alpha 10 gateway preflight: **11 / 11**

This is a regression fixture, not a claim about real-world model failure rate.

## 4K60

Semantic project mode:

```python
editor.set_video_mode("4k60")
```

Official render profiles now include:
- `preview` — 720p
- `showcase` — 1080p
- `final` — 1080p high quality
- `uhd_4k30` — 3840×2160 @ 30 fps
- `uhd_4k60` — 3840×2160 @ 60 fps

Direct helper:

```python
editor.render_4k60()
```

Alpha 9 used 2× supersampled cubic perspective for camera motion. Doing that unchanged at 4K60 would create an 8K60 intermediate. Alpha 10 preserves the old 2× path for 720p/1080p compatibility, but UHD profiles use **native-resolution cubic perspective**.

A 0.6 s 4K60 sample with slow push + dynamic cinematic frame + subtitle rendered as **3840×2160 / 60/1 / 36 frames** in the current CPU environment.

## Existing core

- canonical `project.json`
- versions / undo / redo / diff / checkpoints
- atomic transactions, dry-run, optimistic concurrency
- deterministic visual analysis and focus-aware reframing
- dynamic aspect-ratio cinematic grammar
- duration-preserving fragments / impact clusters / memory shards
- shared-element morph
- rhythm-aware cut planning
- 130-entry queryable Library / 40 transitions
- audio/caption/dialogue system
- semantic cache + hierarchical Render DAG
- QA + frame/contact-sheet inspection

Read first:
1. `V0.2_ALPHA10_NOTES.md`
2. `ALPHA10_AGENT_RELIABILITY.md`
3. `VALIDATION_SUMMARY_A10.md`
4. `START_HERE_WORK.md`

Full frozen source and the 4K60 validation clip are stored in Google Drive folder `AgentCut_v0.2.0-alpha.10_Handoff`.
