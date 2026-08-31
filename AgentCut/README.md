# AgentCut 3.2

**Agent-native semantic video editing runtime.**

Current stable release: **3.2.2**.

Validation:
- **135 / 135 automated tests passed**
- `agentcut doctor`: pass
- EP07 Nether 57.37 s bilingual diagnostic proxy: render pass + QA pass
- 3.1 anime-band/dialogue, 3.0 flexible export/4K60 and Alpha cinematic regressions: pass
- bundled slim Real-ESRGAN AnimeVideo-v3 x2/x4 on Windows/Linux

## 3.2.2: production friction pass

### Readable bilingual captions by default

Imported/ASR bilingual cues are now auto-fitted **without rewriting text or timing**. AgentCut adjusts line-wrap targets, secondary-language scale and (only for very dense pairs) conservative base font size. Existing projects can run:

```python
editor.optimize_subtitle_layout()
```

If a cue remains too dense after the safe minimum, QA emits `BILINGUAL_SPLIT_RECOMMENDED`; AgentCut does not keep shrinking text until it becomes unreadable.

### Visual staging without identity hallucination

```python
anchors = editor.suggest_scene_staging("s04", count=4)
editor.stage_scene_by_order("s04", ["nijika", "ryo", "bocchi", "kita"])
```

The first call only detects anonymous visual anchors. The second requires an explicit left-to-right Cast order before writing staging. Saliency is allowed to estimate coordinates, but never to claim a character identity.

### One-time ASR sidecar setup

Windows x64:

```bash
agentcut asr-install --accept-third-party
```

This installs a checksum-verified whisper.cpp CPU runtime plus the quantized `tiny-q5_1` model to the persistent AgentCut backend directory. Project or AgentCut upgrades reuse the same files. Linux/macOS keep the same persistent model path but currently require an externally installed `whisper-cli`.

The installer deliberately stays optional so the base AgentCut wheel remains small.

### Agent Protocol v5: restart from decisions, not transcripts

```text
agentcut agent-start PROJECT
```

The project-local resume capsule now carries:
- last compact transaction receipt;
- active semantic checkpoint/decisions;
- operation-signature map;
- exact schema delta on upgrade.

A changed project hash from normal editing no longer forces `cold_resume`. On the EP07 diagnostic project, warm bootstrap measured about **2.1 KB** versus **46.9 KB** for full context (~95.5% smaller; byte comparison, not an exact tokenizer count).

Store a bounded semantic checkpoint explicitly when useful:

```bash
agentcut agent-checkpoint PROJECT \
  --goal "Finish EP07 subtitle pass" \
  --scenes s04,s05 --domains text,performance \
  --decision "Chinese primary; English secondary smaller"
```

### Simplified local deployment

```bash
python INSTALL_LOCAL.py --project ./MyProject --create
```

Optional ASR in the same setup:

```bash
python INSTALL_LOCAL.py --project ./MyProject --create --with-asr --accept-third-party
```

## Existing 3.x core

- Cast-aware SRT speaker parsing and scene-specific character staging
- structured bilingual subtitles and multi-style ASS rendering
- character-aware dialogue/performance/reaction recipes
- speaker/beat-driven dynamicity
- cheap 640×360/12fps proxy rendering
- flexible MP4/MOV/MKV/WebM export
- H.264/HEVC/AV1/VP9/ProRes
- runtime-tested NVENC fallback
- 4K60 validated delivery ceiling
- bundled Real-ESRGAN anime SR; optional RIFE interpolation
- cinematic framing/fragment grammar
- semantic history, undo/redo/checkpoints/cache/QA

## Read next

1. `V3.2.2_PRODUCTION_FRICTION.md`
2. `V3.2_SUBTITLE_RUNTIME.md`
3. `V3.1_PERFORMANCE_DIRECTION.md`
4. `AGENT_PROTOCOL.md`
5. `VALIDATION_SUMMARY_V3.md`

Full frozen source/wheel/EP07 validation evidence: Google Drive folder `AgentCut_v3.2.2_Handoff`.