# Alpha 9 practical cinematic workflow

The new grammar is strongest when used as an accent, not as the default treatment for every shot.

## Strong motion / impact peak

```python
e.apply_visual_composition("action")
e.fragment_scene("action", style="impact_cluster", count=5, intensity=.8)
```

Use when one continuous action feels visually flat and the cut benefits from context → detail → detail → release.

## Detail concentration

```python
e.fragment_scene("reaction", style="detail_burst", count=5, intensity=.7)
```

Useful for eyes / hands / weapon / object / UI detail clusters when the source focal point is already known.

## Fragmented memory / associative time

```python
e.fragment_scene("memory", style="memory_shards", count=6, intensity=.9)
```

On video sources, source time deliberately jumps non-linearly. Do not use this for continuity-dependent exposition.

## Cinematic frame lock and reveal

```python
e.set_cinematic_frame("before_peak", preset="scope_lock")
e.set_cinematic_frame("release", preset="scope_reveal")
```

A useful pattern is to tighten the perceived frame before an impact or emotional isolation, then reopen it after the sequence resolves.

## CLI

```bash
agentcut cinematic-plan project scene_04
agentcut cinematic-frame project scene_04 --preset scope_lock
agentcut fragment project scene_05 --style impact_cluster --count 5 --intensity .85
agentcut cinematic project scene_06 --style auto
```

## Stop conditions

Do not automatically add cinematic grammar when:

- the shot is already visually complex;
- dialogue comprehension is the priority;
- the effect repeats the same grammar used in the previous cluster;
- a clean hold is more emotionally appropriate;
- fragmentation would produce sub-2.5-frame flashes unintentionally.

The design goal is controlled discontinuity, not permanent visual noise.
