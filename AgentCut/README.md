# AgentCut 3.0

**Agent-native semantic video editing runtime.**

Current stable release: **3.0.0**.

Validation:
- **82 / 82 automated tests passed**
- `agentcut doctor`: pass
- generalized **3840×2160 @ 60 fps** export: real encode pass
- MP4/H.264, WebM/VP9, MOV/ProRes and MKV/HEVC: real encode pass
- Alpha 8/9/10 cinematic + reliability regression: pass

## 3.0: flexible delivery

The editing canvas no longer dictates delivery settings. The Agent can plan/export with semantic controls for width, height, fps, container, codec, encoder policy, quality and enhancement policy.

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

`encoder="auto"` performs a real runtime NVENC probe. Seeing `h264_nvenc` in FFmpeg's encoder list is not considered enough; unusable hardware encoding falls back to CPU before the expensive export begins.

## Optional AI enhancement

3.0 includes adapters for optional third-party portable backends:
- Real-ESRGAN ncnn Vulkan for super-resolution
- RIFE ncnn Vulkan for frame interpolation

They are not bundled or required. `auto` uses AI only when the backend is installed and actually runs successfully; otherwise it records the failure/fallback and uses Lanczos or FFmpeg motion interpolation. Explicit `ai`/`realesrgan`/`rife` policies fail instead of silently degrading.

RIFE interpolation is segmented at canonical hard cuts so the enhancer is never intentionally asked to invent an intermediate frame between unrelated shots.

## Export invariants

Every stage is probed. AgentCut raises machine-readable errors if enhancement changes duration beyond tolerance or the final file does not match requested geometry/fps. A sidecar `.agentcut-export.json` records the actual encoder and enhancement backends used.

Officially validated delivery ceiling: **3840×2160 @ 60 fps**. Guarded custom values up to 7680×4320 and 120 fps are accepted as experimental.

## Existing editing core

3.0 preserves focus-aware reframing, dynamic subject tracking, cinematic aspect-ratio changes, hard-cut close-up clusters, detail bursts, memory shards, shared-element morphs, rhythm planning, visual-safe text placement, semantic history/rollback, QA and the Alpha 10 Reliability Gateway.

Read first:
1. `V3.0_RELEASE_NOTES.md`
2. `V3_EXPORT_PROTOCOL.md`
3. `V3_AI_ENHANCEMENT.md`
4. `VALIDATION_SUMMARY_V3.md`
5. `START_HERE_WORK.md`

Full frozen source, wheel and validation media are stored in Google Drive folder `AgentCut_v3.0.0_Handoff`.
