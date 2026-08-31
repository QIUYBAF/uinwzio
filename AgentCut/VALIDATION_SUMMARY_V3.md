# Validation Summary — AgentCut 3.0.1

- full automated regression suite: **85 / 85 passed**
- legacy Alpha 8/9/10 functionality: pass
- Agent Reliability Gateway: pass
- custom geometry/fps export: pass
- MP4/H.264, WebM/VP9, MOV/ProRes, MKV/HEVC: real encode pass
- generalized 3840×2160 @ 60fps export: real encode pass
- fallback interpolation + scaling pipeline: real render pass
- duration/spec invariants: pass
- bundled Real-ESRGAN slim discovery: pass
- bundled AnimeVideo-v3 x2/x4 files + SHA256 manifest: pass
- wheel clean-install includes Windows/Linux binaries and models: pass
- bundled Linux executable startup: pass
- `auto` runtime-failure fallback: pass
- RIFE discovery/installer + hard-cut segmentation contracts: pass
- `agentcut doctor`: pass

## Environment-specific note

The cloud validation machine has no usable NVIDIA NVENC runtime, so AgentCut correctly selects CPU fallback.

It also has no usable Vulkan device. The bundled Linux Real-ESRGAN executable starts, but a real tiny inference attempt fails at Vulkan initialization with `vkCreateInstance failed` / `invalid gpu device`. Neural Real-ESRGAN inference is therefore **not claimed as passed on this cloud**. The installed-wheel test verifies the intended production behavior: `auto` records the AI runtime failure and falls back to Lanczos while preserving requested dimensions and duration; explicit AI remains a hard failure.

On a Vulkan-capable Windows/Linux machine, the Real-ESRGAN executable and AnimeVideo-v3 x2/x4 models are now fully local and require no new download.
