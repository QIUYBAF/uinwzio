# Validation Summary — AgentCut 3.0.0

Release validation:

- full automated regression suite: **82 / 82 passed**
- legacy Alpha 8/9/10 functionality: pass
- Agent Reliability Gateway: pass
- custom geometry/fps export: pass
- MP4/H.264: real encode pass
- WebM/VP9: real encode pass
- MOV/ProRes: real encode pass
- MKV/HEVC: real encode pass
- generalized 3840×2160 @ 60fps export: real encode pass
- fallback interpolation + scaling pipeline: real render pass
- duration invariants through semantic render/interpolation/upscale/final encode: pass
- AI backend discovery/installer contracts: pass
- explicit third-party acceptance guard: pass
- no-AI fallback honesty: pass
- `agentcut doctor`: pass

## Environment-specific note

The release environment had no usable NVIDIA NVENC runtime despite FFmpeg listing NVENC encoders; AgentCut correctly selected CPU fallback.

The environment also had no Real-ESRGAN/RIFE binaries and blocked direct Python network download, so the neural models were **not executed in this freeze environment**. Adapter discovery, install/error contracts, hard-cut segmentation, runtime-failure fallback and deterministic fallback paths were tested. Do not describe those fallback renders as AI-model inference.
