# AgentCut 3.0 — AI Enhancement

## Optional backends

AgentCut integrates adapters for third-party portable backends rather than bundling them as hard dependencies:

- Real-ESRGAN ncnn Vulkan — optional super-resolution
- RIFE ncnn Vulkan — optional frame interpolation

Check discovery/status:

```bash
agentcut enhance-status
```

Explicit install path:

```bash
agentcut ai-install realesrgan --accept-third-party
agentcut ai-install rife --accept-third-party
```

Alternative environment variables:

```text
AGENTCUT_REALESRGAN=/path/to/realesrgan-ncnn-vulkan(.exe)
AGENTCUT_RIFE=/path/to/rife-ncnn-vulkan(.exe)
AGENTCUT_BACKEND_ROOT=/custom/backend/root
```

## Super-resolution policy

- `off`: no dedicated enhancement stage
- `auto`: Real-ESRGAN if discovered and runtime-successful, otherwise FFmpeg Lanczos
- `ai` / `realesrgan`: require AI backend and fail explicitly if unavailable/broken

Content hint `anime` selects the anime-oriented model; `general` selects the general model.

## Frame interpolation policy

- `off`: no dedicated interpolation stage
- `auto`: RIFE if discovered and runtime-successful, otherwise FFmpeg motion-compensated interpolation
- `ai` / `rife`: require RIFE

## Hard-cut protection

RIFE receives independently extracted temporal segments split at AgentCut's canonical hard-cut boundaries, preventing intentional cross-shot interpolation. The FFmpeg fallback additionally uses scene-change detection.

## Honesty / failure semantics

A fallback is never labelled as AI. If an executable is discovered but fails at runtime, `auto` records the failure reason and falls back; explicit AI policy remains a hard error.

Every enhancement stage is probed for duration invariance before proceeding.
