# AgentCut 3.0

**Agent-native semantic video editing runtime.**

Current stable release: **3.0.1**.

Validation:
- **85 / 85 automated tests passed**
- `agentcut doctor`: pass
- generalized **3840×2160 @ 60 fps** export: real encode pass
- MP4/H.264, WebM/VP9, MOV/ProRes and MKV/HEVC: real encode pass
- Alpha 8/9/10 cinematic + reliability regression: pass

## 3.0: flexible delivery

The editing canvas does not dictate delivery settings. The Agent can plan/export width, height, fps, container, codec, encoder policy, quality and enhancement policy independently.

Supported containers: MP4, MOV, MKV, WebM.

Supported codecs: H.264, HEVC/H.265, AV1, VP9, ProRes, subject to the validated container/codec matrix and local FFmpeg encoder availability.

```python
plan = editor.plan_export(
    width=3840,
    height=2160,
    fps=60,
    container="mp4",
    codec="hevc",
    encoder="auto",
    upscale="auto",
    interpolate="auto",
    content="anime",
)
result = editor.export_video(...)
```

`encoder="auto"` performs a real runtime NVENC probe. An encoder merely appearing in FFmpeg's list is not enough; unusable hardware encoding falls back to CPU before expensive export begins.

## 3.0.1: offline anime super-resolution

AgentCut 3.0.1 **bundles a slim Real-ESRGAN ncnn Vulkan runtime** in the wheel/Handoff for Windows x64 and Linux x64:

- Windows and Linux executables
- AnimeVideo-v3 x2 model
- AnimeVideo-v3 x4 model
- upstream MIT license
- fixed SHA256 manifest

A Real-ESRGAN download is therefore no longer required on each fresh Windows/Linux runtime. The bundled AI still requires a working Vulkan-capable GPU/driver. External `AGENTCUT_REALESRGAN` or PATH installs override the bundled slim runtime when a newer/full model pack is desired.

**RIFE remains optional/external** because its portable package is much larger. RIFE interpolation is segmented at canonical hard cuts so the enhancer is never intentionally asked to invent an intermediate frame between unrelated shots.

`auto` uses AI only when the backend actually runs successfully. Missing/broken AI records the reason and falls back to Lanczos or FFmpeg motion interpolation. Explicit `ai` / `realesrgan` / `rife` policies fail instead of silently degrading. A fallback is never reported as AI.

## Export invariants

Every stage is probed. AgentCut raises machine-readable errors if enhancement changes duration beyond tolerance or the final file does not match requested geometry/fps. A sidecar `.agentcut-export.json` records the actual encoder and enhancement backends used.

Officially validated delivery ceiling: **3840×2160 @ 60 fps**. Guarded custom values up to 7680×4320 and 120 fps are experimental.

## Existing editing core

3.0 preserves focus-aware reframing, dynamic subject tracking, cinematic aspect-ratio changes, hard-cut close-up clusters, detail bursts, memory shards, shared-element morphs, rhythm planning, visual-safe text placement, semantic history/rollback, QA and the Alpha 10 Reliability Gateway.

Read first:
1. `V3.0_RELEASE_NOTES.md`
2. `V3_EXPORT_PROTOCOL.md`
3. `V3_AI_ENHANCEMENT.md`
4. `VALIDATION_SUMMARY_V3.md`
5. `START_HERE_WORK.md`

Full frozen source, wheel and validation evidence are stored in Google Drive folder `AgentCut_v3.0.1_Handoff`.
