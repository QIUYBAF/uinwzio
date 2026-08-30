# AgentCut v0.2.0-alpha.9

**Agent-native semantic video editing runtime.**

AgentCut is not a simplified Premiere clone. It gives an AI/Agent stable semantic editing operations, a canonical `project.json`, deterministic FFmpeg rendering, inspection, QA, history and rollback.

```text
creative intent
   ↓
Agent / GPT
   ↓
semantic edit operations
   ↓
project.json
   ↓
deterministic renderer
   ↓
preview / frame inspection / QA
   ↓
local correction / rollback
```

## Current baseline

- version: **v0.2.0-alpha.9**
- automated validation: **63/63 grouped tests passed**
- `agentcut doctor`: **pass**
- built-in queryable library: **130 entries**
- transitions: **40**

Read first:

1. `V0.2_ALPHA9_NOTES.md`
2. `ALPHA9_CINEMATIC_WORKFLOW.md`
3. `VALIDATION_SUMMARY_A9.md`
4. `V0.2_ALPHA8_NOTES.md`
5. `START_HERE_WORK.md`

## What Alpha 9 adds: cinematic grammar

Alpha 9 turns several film-editing ideas into semantic, reversible operations:

```python
# a shot gradually narrows from 16:9 to 2.39:1
e.set_cinematic_frame("scene_04", preset="scope_lock")

# one shot becomes context → close-up cluster → release, with unchanged total duration
e.fragment_scene("scene_05", style="impact_cluster", count=5, intensity=.85)

# non-linear temporal shards for a video scene
e.fragment_scene("memory", style="memory_shards", count=6, intensity=.9)
```

New primitives include moving aspect-ratio bars, immediate focus-aware `crop_zoom`, duration-preserving fragmentation, detail bursts, impact clusters and non-linear memory shards. The system deliberately rejects complex scene-bound audio/dialogue/layers during fragmentation rather than corrupting them.

## What Alpha 8 adds for real editing

### Visual analysis → real reframing

```python
visual = e.analyze_scene_visual("scene_04", sample_count=3)
e.apply_visual_composition("scene_04", text_hint="title")
```

AgentCut estimates visual saliency, focus position, subject bounds and quiet text zones. For moving video it can produce a guarded `focus_path` that drives the actual FFmpeg crop.

### Bulk composition pass

```python
e.auto_compose_scenes()
```

or:

```bash
agentcut auto-compose project
```

### Visual-safe dialogue

```python
e.add_dialogue_segment(
    "scene_04",
    "她们继续向前。",
    start=0.2,
    duration=1.8,
    position="auto",
)
```

### Manual intent always wins

```python
e.tag_asset("hero", focus_x=0.70, focus_y=0.42)
e.apply_auto_composition("scene_04")
```

Explicit focus tags override inferred saliency.

## Existing core capabilities

- canonical `project.json`
- versions / undo / redo / diff / checkpoints
- atomic transactions, dry-run and optimistic concurrency
- image/video scenes, source-in and playback rate
- subpixel perspective+cubic camera backend
- `cover`, `contain`, `native_window`, `ambient` composition
- focus-aware crop and dynamic focus tracking
- text/rect/image graphic layers and keyframes
- rendered shared-element `shared_morph`
- 40 transitions and transition-bound SFX
- deterministic environmental effects
- BGM / ambience / SFX / dialogue mix
- rhythm analysis, onset/beat grid and rhythm-aware cut planning
- nine-zone captions
- scene-relative dialogue binding
- hierarchical Render DAG + semantic cache
- frame extraction / contact sheet
- QA + machine-readable errors

## Install

Requirements:

- Python >= 3.11
- FFmpeg + ffprobe
- recommended: Noto Sans CJK SC

```bash
pip install -e '.[api,dev]'
python -m agentcut doctor
pytest -q
```

## Minimal example

```python
from agentcut import Editor

e = Editor.create("project", width=1920, height=1080, fps=30)
e.add_asset("image.png", asset_id="hero")
e.add_scene("hero", 4.0, scene_id="scene_01")

e.apply_visual_composition("scene_01", text_hint="旅途继续")
e.set_camera("scene_01", motion="slow_push", amount=0.02, easing="ease_in_out")
e.add_dialogue_segment(
    "scene_01", "旅途继续。", start=0.5, duration=1.5, position="auto"
)

preview = e.render_preview()
print(e.qa(preview))
```

## Practical CLI

```bash
agentcut doctor
agentcut analyze-visual project hero
agentcut composition-plan project scene_01 --analyze --text "旅途继续"
agentcut auto-compose project --scenes scene_01,scene_02 --samples 3
agentcut cinematic-plan project scene_01
agentcut cinematic-frame project scene_01 --preset scope_lock
agentcut fragment project scene_02 --style impact_cluster --count 5 --intensity .85
agentcut render project --profile preview
agentcut qa project --rendered project/preview/preview.mp4
```

## Important limitation

Alpha 9 cinematic grammar does not make every shot better. Fragmentation and changing aspect ratios are accents; the Agent should prefer clean continuity when comprehension, dialogue, or stillness is the stronger choice. Alpha 8 visual analysis is deterministic saliency estimation, not semantic object recognition. Explicit `focus_x` / `focus_y` tags remain the art-direction override.

Full Alpha 9 source handoff and the cinematic-grammar reference render are stored in Google Drive folder `AgentCut_v0.2.0-alpha.9_Handoff`.
