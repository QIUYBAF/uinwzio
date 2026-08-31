# AgentCut 3.2

**Agent-native semantic video editing runtime.**

Current stable release: **3.2.0**.

Validation:
- **120 / 120 automated tests passed**
- `agentcut doctor`: pass
- real bilingual/multi-style subtitle render: pass + QA pass
- 3.1 anime-band/dialogue direction regression: pass
- 3.0 flexible export/4K60 and Alpha cinematic/reliability regressions: pass
- bundled slim Real-ESRGAN AnimeVideo-v3 x2/x4 on Windows/Linux

## 3.2: subtitles + cheap Agent restart

3.2 adds structured bilingual captions/dialogue, more ASS subtitle styles, optional whisper.cpp ASR, SRT import, ASR caching/idempotency and a persistent Agent restart capsule.

```python
editor.add_caption(
    "下一首，直接进副歌。", .2, 1.5,
    speaker="虹夏", subtitle_style="bilingual",
    secondary_text="Next song — straight into the chorus.",
)
```

Semantic subtitle styles include `default`, `band`, `thought`, `shout`, `whisper`, `aside`, `karaoke`, `neon`, `manga`, `boxed`, `cinematic`, `lower_third`, and `bilingual`. The Library exposes 16 subtitle presets.

Automatic subtitles:

```python
editor.auto_subtitles("voice", language="auto")
editor.auto_subtitles("voice", language="auto", bilingual=True, translate_to="en")
```

ASR is optional and uses whisper.cpp when `whisper-cli` + a ggml model are configured. Input media is normalized through FFmpeg to 16 kHz mono WAV. Repeated ASR on the same asset replaces prior auto-generated captions by default and reuses cached timestamped transcripts when the asset/backend/options fingerprint is unchanged.

## Agent Protocol v4

On restart/upgrade, **do not begin by rereading the entire repository or full operation schema**.

```text
GET /agent/bootstrap
→ inspect warm_resume / upgrade_resume / cold_resume
→ request only touched scenes/domains if needed
→ preflight
→ apply
→ render recommended scope
→ QA
```

CLI:

```bash
agentcut agent-start PROJECT --task "subtitle pass" --scenes s01,s02 --domains text,performance
```

In a synthetic 20-scene benchmark, the warm bootstrap payload was **1,160 bytes** versus **44,355 bytes** for the full context (~97.4% smaller; rough tokenizer-independent estimate ~258 tokens).

## Simplified deployment

```bash
agentcut setup ./project --create --name "My Project"
```

Frozen Handoffs also include `INSTALL_LOCAL.py` for local wheel install + doctor + project bootstrap.

## Existing 3.x core

- persistent Cast registry and character-aware dialogue/performance recipes
- speaker/beat-driven dynamicity and reaction shots
- flexible MP4/MOV/MKV/WebM export; H.264/HEVC/AV1/VP9/ProRes
- runtime-tested NVENC fallback and validated 4K60 delivery ceiling
- bundled Real-ESRGAN anime SR; optional RIFE interpolation
- cinematic framing/fragment grammar
- semantic history, undo/redo/checkpoints/cache/QA

Read first:
1. `START_HERE_WORK.md`
2. `V3.2_SUBTITLE_RUNTIME.md`
3. `V3.1_PERFORMANCE_DIRECTION.md`
4. `AGENT_PROTOCOL.md`
5. `VALIDATION_SUMMARY_V3.md`

Full frozen source/wheel/validation evidence: Google Drive folder `AgentCut_v3.2.0_Handoff`.
