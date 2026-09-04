# Third-party AI backends

AgentCut 1.0.1 does not bundle third-party AI executables or model weights. This keeps the GitHub checkout small and directly usable in constrained Work/cloud environments. AgentCut does not claim ownership of these optional components; their upstream licenses still apply.

## Real-ESRGAN ncnn Vulkan — optional

- upstream: `xinntao/Real-ESRGAN-ncnn-vulkan`
- adapter target release: `20220424`
- upstream license: MIT
- purpose: optional video super-resolution
- discovery: `AGENTCUT_REALESRGAN`, PATH, or AgentCut's explicit installer

## RIFE ncnn Vulkan — optional

- upstream: `nihui/rife-ncnn-vulkan`
- adapter target release: `20221029`
- upstream license: MIT
- purpose: optional frame interpolation
- discovery: `AGENTCUT_RIFE`, PATH, or AgentCut's explicit installer

Installation always requires `--accept-third-party`. Automatic export falls back to FFmpeg Lanczos/minterpolate when a backend is missing or fails at runtime. An explicitly requested AI backend returns a clear error instead of silently changing the requested policy.
