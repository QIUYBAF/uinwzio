# AgentCut 3.0

**Agent-native semantic video editing runtime.**

Current stable release: **3.0.2**.

Validation:
- **96 / 96 automated tests passed**
- `agentcut doctor`: pass
- generalized **3840×2160 @ 60 fps** export: real encode pass
- MP4/H.264, WebM/VP9, MOV/ProRes and MKV/HEVC: real encode pass
- bundled slim Real-ESRGAN for Windows/Linux with AnimeVideo-v3 x2/x4 models
- Alpha 8/9/10 cinematic + reliability regression: pass

## 3.0.2: Agent Protocol v2

3.0.2 focuses on AI ↔ AgentCut interaction reliability rather than adding renderer effects.

Preferred loop:

```text
GET /agent/context
→ POST /agent/preflight
→ inspect repairs + impact + verification
→ POST /agent/apply with expected_project_hash
→ render recommended scene/span/full scope
→ QA + inspect relevant frames
```

The Agent gateway accepts canonical operations and deterministic LLM formatting drift:

```json
{"action":"set_camera","args":{"scene_id":"scene_01","motion":"slow_push"}}
```

```json
{"operation":"camera","params":{"scene":"scene_01","type":"slow_push"}}
```

It also accepts singleton/root-wrapped operations, flattened arguments and uniquely high-confidence syntax typos. Creative/library ambiguity is never silently fuzzy-corrected.

`GET /agent/context` can be domain-filtered (`visual,cinematic,transition,text,...`) and combines compact state, entity IDs, selected scene context and semantic schema. On a synthetic 20-scene benchmark, a 3-scene visual/cinematic/transition context was **12,504 bytes vs 33,988 bytes** for the old full project + full schema + capabilities read (**63.2% smaller**).

Preflight returns a projected digest plus change-impact map, recommended render scope and verification plan. Full projected state is opt-in. Apply returns a compact transaction receipt with before/after hashes and result summaries.

Transition edits are boundary-aware: verification renders the current + next scene span instead of an isolated scene.

## Flexible delivery

Export settings are independent from the editing canvas. Supported containers: MP4, MOV, MKV, WebM. Supported codecs include H.264, HEVC/H.265, AV1, VP9 and ProRes subject to local encoder availability.

Official validated ceiling: **3840×2160 @ 60 fps**. Higher guarded values are experimental.

## AI enhancement

- Real-ESRGAN ncnn Vulkan slim runtime is bundled on Windows/Linux for offline anime-video super-resolution.
- AnimeVideo-v3 x2 and x4 models are bundled.
- RIFE remains optional/external for AI interpolation.
- `auto` records AI runtime failures and safely falls back; fallback is never labelled as AI.
- RIFE respects AgentCut hard-cut boundaries.

## Existing editing core

AgentCut preserves focus-aware reframing, dynamic tracking, cinematic aspect-ratio changes, hard-cut close-up clusters, detail bursts, memory shards, shared-element morphs, rhythm planning, visual-safe text placement, semantic history/rollback, QA and flexible export.

Read first:
1. `START_HERE_WORK.md`
2. `AGENT_PROTOCOL.md`
3. `VALIDATION_SUMMARY_V3.md`
4. `V3_AI_ENHANCEMENT.md`
5. `V3_EXPORT_PROTOCOL.md`

Full frozen source/wheel/validation evidence: Google Drive folder `AgentCut_v3.0.2_Handoff`.
