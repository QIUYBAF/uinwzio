# AgentCut 3.2

**Agent-native semantic video editing runtime.**

Current stable release: **3.2.3**.

Validation:
- **145 / 145 automated tests passed**
- `agentcut doctor`: pass
- dedicated 3.2.3 dialogue-coverage suite: 10 / 10
- EP07 Nether diagnostic coverage proxy: render pass + QA pass
- 3.2.2 subtitle/runtime, 3.1 performance, 3.0 flexible export/4K60 and Alpha cinematic regressions: pass
- bundled slim Real-ESRGAN AnimeVideo-v3 x2/x4 on Windows/Linux

## Codex / AI entry

Routine SW-01 work does **not** require reading every document in this directory.

Default route:

```text
00_ProjectOS/projects/SW-01_AgentCut.md
→ task-relevant AgentCut source/test files
→ smallest relevant test
→ broader regression only when risk requires it
```

Use `00_ProjectOS/CODEX_ROUTER.md` when the Project ID or path is unknown.

Read the documents below only when the task depends on them:

- `START_HERE_WORK.md` — legacy cross-conversation resume/bootstrap reference; not routine startup.
- `AGENT_PROTOCOL.md` — agent protocol/bootstrap/API changes.
- `V3.2.3_EDITORIAL_COVERAGE.md` — editorial coverage behavior or regression.
- `V3.2.2_PRODUCTION_FRICTION.md` — production-friction history/regression.
- `VALIDATION_SUMMARY_V3.md` — release validation / broad QA.
- `GLT_*` and cinematic playbooks — GLT-specific editing case studies, not core runtime prerequisites.
- `ALPHA*` / `V0.2_*_NOTES.md` — historical behavior or regression archaeology only.

Do not automatically read release notes just because they exist.

## 3.2.3: editorial coverage / anti-template pass

EP07 practical cutting showed a remaining failure mode: speaker tracking could be technically correct while a long static-image scene still felt like a slideshow because it used one continuous push/reframe.

3.2.3 adds semantic editorial coverage without forcing motion everywhere:

```python
editor.direct_dialogue_coverage("s06", intensity=.62)
editor.direct_attention_insert(
    "s09", start=.45, duration=2.0,
    focus_x=.50, focus_y=.30, intensity=.78,
)
```

`direct_dialogue_coverage` builds restrained establish → speaker medium/close → alternate/reaction coverage → group reset paths from existing Cast-aware captions/dialogue and per-scene staging. It preserves source assets and subtitle timing.

`direct_attention_insert` gives objects/actions/details their own deterministic insert shot without pretending they are Cast characters.

Long multi-speaker `compose_dialogue_scene(..., direction="auto")` may choose coverage automatically; short or contemplative dialogue keeps continuous speaker tracking/stillness.

QA adds:
- `LONG_SINGLE_COVERAGE` — long multi-line dialogue still uses one continuous reframe
- `LONG_PRE_DIALOGUE_HOLD` — long action-only lead needs an insert/visual beat
- `DENSE_SHOT_COVERAGE` — too many cuts in a short scene
- `TIGHT_COVERAGE` — crop may need headroom/framing review

These are editorial signals, not mandatory rewrites. Stillness remains a valid choice.

## 3.2.2 foundations retained

- Cast-aware SRT speaker recovery and scene-specific staging
- structured bilingual subtitles + safe auto-fit
- anonymous visual staging anchors with explicit role ordering
- optional persistent whisper.cpp ASR installer/cache
- Protocol v5 warm/upgrade resume capsules and schema deltas
- true low-cost proxy rendering

## Existing 3.x core

- persistent Cast registry and character-aware performance recipes
- speaker/beat-driven dynamicity and reaction shots
- flexible MP4/MOV/MKV/WebM export; H.264/HEVC/AV1/VP9/ProRes
- validated 4K60 delivery ceiling and runtime-tested NVENC fallback
- bundled Real-ESRGAN AnimeVideo-v3 x2/x4; optional RIFE
- semantic history, undo/redo/checkpoints/cache/QA

## Important EP07 asset boundary

The 3.2.3 practical validation uses images visibly marked **PROXY STORYBOARD**. They are diagnostic assets, not the user's prepared final generated EP07 art. Do not treat them as release footage. When the final image set becomes visible in the active runtime, replace scene assets while preserving the canonical subtitle/timeline/coverage logic and rerun visual staging + QA + proxy.

Full frozen source/wheel/validation package: `AgentCut_v3.2.3_Handoff`.
