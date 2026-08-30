# Validation Summary — v0.2.0-alpha.8

- Automated tests: **57 / 57 passed** across grouped regression runs.
- `agentcut doctor`: **pass**.
- FFmpeg / FFprobe: pass.
- Existing Alpha.6/7, library, QA, editor, hardening and Agent-native suites: pass.
- Alpha.8-specific tests: **9 / 9 passed**.

## Real renderer checks

- off-center subject survives a real focus-aware `cover` render: **pass**
- dynamic `focus_path` changes crop from left subject to right subject in rendered frames: **pass**
- moving-video scene analysis generates a continuous tracking path: **pass**
- composition change creates a new scene cache artifact instead of reusing stale framing: **pass**

## Workflow checks

- deterministic saliency finds an intentionally off-center subject: pass
- safe caption zone moves away from that subject: pass
- bulk `auto_compose_scenes()` updates multiple scenes in one history commit: pass
- dialogue `position="auto"` uses visual composition: pass
- QA detects stacked tracking + camera movement: pass
- integrated three-scene 720p smoke render (off-center still + moving video + low-res portrait): pass

Full source and smoke artifacts are stored in Google Drive folder `AgentCut_v0.2.0-alpha.8_Handoff`.
