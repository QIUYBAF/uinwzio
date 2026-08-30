# Alpha 8 Practical Workflow

Use this when AgentCut is editing a real video. The goal is fewer manual framing fixes, not maximum automation.

## Recommended order

1. Build or restore scenes first.
2. Run visual composition only on scenes whose framing is not already artistically locked.
3. Add dialogue with `position="auto"` after visual composition.
4. Add deliberate camera motion only when it adds something beyond subject tracking.
5. Render the affected scene/span and inspect frames/contact sheet.
6. Run QA and correct only the flagged scene.

## Whole-project first pass

```python
from agentcut import Editor

e = Editor("project")
e.auto_compose_scenes(sample_count=3)
preview = e.render_preview()
print(e.qa(preview))
```

CLI:

```bash
agentcut auto-compose project --samples 3
agentcut render project --profile preview
agentcut qa project --rendered project/preview/preview.mp4
```

## Prefer local correction

```python
visual = e.analyze_scene_visual("scene_07", sample_count=5)
plan = e.suggest_composition("scene_07", text_hint="这一幕的标题", visual=visual)
e.apply_visual_composition("scene_07", text_hint="这一幕的标题", sample_count=5)
e.render_span("scene_06", "scene_08")
```

## Manual override

If saliency chose the wrong object, correct intent once instead of repeatedly rerunning analysis:

```python
e.tag_asset("scene07_image", focus_x=0.68, focus_y=0.43)
e.apply_auto_composition("scene_07")
```

Explicit tags override inferred focus.

## Text placement

```python
e.add_dialogue_segment("scene_07", "字幕内容", start=0.3, duration=1.5, position="auto")
```

For global captions:

```python
zone = e.suggest_caption_zone("scene_07", text="字幕内容")
e.add_caption("字幕内容", start, end, position=zone)
```

## Do not use tracking blindly

Avoid automatic tracking for montage clips with internal hard cuts, intentional locked-off compositions, scenes where the whole environment is the subject, or typography-led layouts. The discontinuity guard blocks some bad cases automatically, but explicit artistic intent remains authoritative.
