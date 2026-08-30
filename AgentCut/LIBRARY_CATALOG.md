# AgentCut Content Libraries

AgentCut keeps reusable editing vocabulary outside the core runtime.

| Library | Count | Purpose |
|---|---:|---|
| transitions | 39 | cuts, fades, wipes, slides, smooth moves, dissolve, blur, cover/reveal, etc. |
| effects | 24 | semantic weather / atmosphere / energy / light presets |
| filters | 14 | neutral, monochrome, cinematic, warm/cool, vintage, night, detail/softness |
| motions | 12 | stable whole-scene camera-motion recipes |
| layer_motions | 12 | object-level entrance/exit/reveal/pop/zoom recipes |
| subtitle_styles | 8 | reusable subtitle presentation defaults |
| audio_cues | 8 | semantic whoosh/impact/UI cue defaults |
| materials | 12 | procedural particle appearance definitions |

## Query examples

```python
editor.list_library("effects", tags=["weather", "cold"])
editor.inspect_library_item("effects", "snow_wind")
editor.apply_effect_preset("scene_04", "snow_wind")
editor.add_filter("scene_04", "cool")
editor.apply_transition_preset("scene_04", "dissolve")
```

## Stability

Catalog entries carry `stability` and `tags`. Agents should prefer stable entries unless experimentation is explicitly desired.

## License policy

Built-in procedural effects are original implementations. External projects may inspire taxonomy/parameters, but importing external binary assets requires source URL, license, attribution requirements, checksum, and local asset ID.
