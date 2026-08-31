# Validation Summary — AgentCut 3.0.2

- full automated regression suite: **96 / 96 passed**
- legacy Alpha 8/9/10 functionality: pass
- Agent Reliability Gateway regression: pass
- Agent Protocol v2 singleton/root-wrapper/params/arguments/flattened normalization: pass
- unique high-confidence action/argument syntax typo repair: pass
- compact Agent Context domain filtering: pass
- preflight change-impact / render-scope / verification guidance: pass
- transition boundary span recommendation: pass
- missing-entity recovery hints: pass
- compact apply transaction receipt: pass
- wheel clean-install Agent Protocol v2 runtime test: pass
- custom geometry/fps export: pass
- MP4/H.264, WebM/VP9, MOV/ProRes, MKV/HEVC: real encode pass
- generalized 3840×2160 @ 60fps export: real encode pass
- fallback interpolation + scaling pipeline: real render pass
- bundled Real-ESRGAN slim discovery + AnimeVideo-v3 x2/x4 SHA verification: pass
- RIFE discovery/installer + hard-cut segmentation contracts: pass
- `agentcut doctor`: pass

## Agent interaction benchmark

Synthetic 20-scene project:
- old full project + full schema + capabilities read: **33,988 compact JSON bytes**
- task-scoped Agent Context for 3 scenes and `visual,cinematic,transition`: **12,504 bytes**
- reduction: **63.2%**

A stress fixture containing 18 mixed non-canonical LLM-style operations normalized, preflighted and applied atomically as 18/18 semantic operations. This is a deterministic regression fixture, not a claim about universal model failure rate.

## Environment-specific note

The cloud machine has no usable NVENC runtime and no usable Vulkan device. AgentCut correctly chooses CPU/fallback paths. The bundled Linux Real-ESRGAN executable is present and starts, but actual neural inference fails at Vulkan initialization; neural inference is therefore not claimed as passed on this cloud. `auto` records the runtime failure and falls back while preserving dimensions/duration; explicit AI remains a hard failure.
