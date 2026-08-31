# AgentCut 3.0 — Export Protocol

## Planner first

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
```

Review normalized target spec, selected CPU/GPU encoder, enhancement stages, warnings and validated-ceiling status before executing `editor.export_video()`.

A JSON manifest is written next to the final media file as `<video>.<container>.agentcut-export.json` and records actual stage backends plus ffprobe-verified output.

## Container / codec matrix

| Codec | MP4 | MOV | MKV | WebM |
|---|---:|---:|---:|---:|
| H.264 | yes | yes | yes | no |
| HEVC | yes | yes | yes | no |
| AV1 | yes | no | yes | yes |
| VP9 | no | no | yes | yes |
| ProRes | no | yes | yes | no |

## Guarded bounds

- width: 64–7680
- height: 64–4320
- fps: 1–120

Officially validated release ceiling: **3840×2160 @ 60 fps**. Requests above that remain experimental and receive planner warnings.

## Invariants

- export target is independent of editing canvas
- container/codec compatibility is checked before render
- `encoder=auto` uses runtime hardware probing
- enhancement stages must preserve duration within tolerance
- final width/height/fps must match normalized requested spec
- sidecar manifest reports actual rather than intended backend choices
