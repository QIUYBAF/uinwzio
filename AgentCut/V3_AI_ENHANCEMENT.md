# AgentCut 3.0.1 — AI Enhancement

## Bundled offline super-resolution

AgentCut 3.0.1 bundles a slim **Real-ESRGAN ncnn Vulkan** runtime for Windows x64 and Linux x64:

- platform executable
- AnimeVideo-v3 x2 model
- AnimeVideo-v3 x4 model
- upstream MIT license
- SHA256 manifest

It is intentionally optimized for anime/video. Large general-photo models and macOS binaries remain external.

The executable does not require CUDA or PyTorch, but it **does require a working Vulkan-capable GPU/driver**.

Check discovery/status:

```bash
agentcut enhance-status
```

Discovery priority for Real-ESRGAN:
1. `AGENTCUT_REALESRGAN`
2. PATH
3. bundled slim runtime
4. user backend root

This allows a newer/full external runtime to override the bundled version without modifying AgentCut.

## Super-resolution policy

- `off`: no dedicated enhancement stage
- `auto`: try Real-ESRGAN; if unavailable, model-incompatible, or runtime initialization/inference fails, record the reason and fall back to FFmpeg Lanczos
- `ai` / `realesrgan`: require successful Real-ESRGAN execution; never silently degrade

For anime content, ratios up to about 2.25× prefer AnimeVideo-v3 x2; larger ratios prefer x4, followed by exact resize to the requested delivery geometry.

## Frame interpolation

RIFE ncnn Vulkan remains optional/external because its portable bundle is much larger.

- `off`: no dedicated interpolation stage
- `auto`: use RIFE when installed and runnable, otherwise FFmpeg motion-compensated interpolation
- `ai` / `rife`: require successful RIFE execution

Optional install:

```bash
agentcut ai-install rife --accept-third-party
```

Environment override:

```text
AGENTCUT_REALESRGAN=/path/to/realesrgan-ncnn-vulkan(.exe)
AGENTCUT_RIFE=/path/to/rife-ncnn-vulkan(.exe)
AGENTCUT_BACKEND_ROOT=/custom/backend/root
```

## Hard-cut protection

RIFE receives independently extracted temporal segments split at AgentCut's canonical hard-cut boundaries, preventing intentional cross-shot interpolation. The FFmpeg fallback additionally uses scene-change detection.

## Honesty / failure semantics

A fallback is never labelled as AI. If an executable is discovered but fails at runtime, `auto` records the failure reason and falls back; explicit AI policy remains a hard error.

Every enhancement stage is probed for duration invariance before proceeding.

## Cloud validation note

The current cloud has no usable Vulkan device. The bundled Linux executable starts, but inference fails at Vulkan initialization. Therefore the 3.0.1 cloud validation verifies packaging, model integrity, runtime invocation and safe fallback behavior—not successful neural inference. A Vulkan-capable Windows/Linux environment can use the bundled runtime offline without downloading Real-ESRGAN again.
