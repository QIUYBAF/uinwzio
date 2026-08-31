# Validation Summary — AgentCut v0.2.0-alpha.10

- Automated tests: **71 / 71 passed**
- `agentcut doctor`: **pass**
- Official tested ceiling: **3840×2160 @ 60 fps**
- Actual 4K60 smoke: **3840×2160, 60/1 fps, 36 frames**
- 0.6 s 4K60 camera + cinematic-frame + caption sample: **pass**
- Sample render time in current CPU environment: **~10.1 s** (not a performance guarantee)
- UHD camera backend: **native-resolution cubic perspective**
- 720p / 1080p camera backend compatibility: **Alpha 9 2× supersampled cubic preserved**
- Agent Reliability fixture: **11/11 non-canonical LLM-style operations normalized and preflighted**
- Strict-operation signature failures are machine-readable `INVALID_OPERATION_ARGS`
- Full Alpha 9 feature regression: **pass**
