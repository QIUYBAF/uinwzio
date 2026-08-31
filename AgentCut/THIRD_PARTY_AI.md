# Third-party AI backends

AgentCut does not claim ownership of third-party AI executables/models. Upstream licenses and source attribution remain part of the distribution.

## Real-ESRGAN ncnn Vulkan — bundled slim runtime in 3.0.1

- upstream implementation: `xinntao/Real-ESRGAN-ncnn-vulkan`
- portable source release used by the reproducible bundle workflow: Real-ESRGAN `v0.2.5.0` / `20220424`
- upstream license: MIT
- purpose: anime-video super-resolution
- bundled platforms: Windows x64, Linux x64
- bundled models: `realesr-animevideov3-x2`, `realesr-animevideov3-x4`
- intentionally not bundled: large general/photo models, macOS executable

The Handoff/wheel includes an upstream license copy and SHA256 manifest. A reproducible GitHub Actions workflow at `.github/workflows/build-agentcut-realesrgan-slim.yml` downloads the official portable packages and extracts only the required executables/models.

The slim bundle still requires a working Vulkan-capable GPU/driver. Users can override it with a newer/full runtime via `AGENTCUT_REALESRGAN` or PATH.

## RIFE ncnn Vulkan — external

- upstream: `nihui/rife-ncnn-vulkan`
- adapter target release: `20221029`
- upstream implementation license: MIT
- purpose: optional frame interpolation
- distribution: **not bundled**; its portable packages are hundreds of MB

RIFE can be supplied through `AGENTCUT_RIFE`, PATH, or AgentCut's explicit third-party installer. `auto` export falls back safely if an AI backend is missing or fails at runtime; explicit AI policy never silently degrades.
