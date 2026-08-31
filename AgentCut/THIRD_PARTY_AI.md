# Third-party AI backends

AgentCut does not claim ownership of external models or executables and does not bundle them into the 3.0 source/wheel.

## Real-ESRGAN ncnn Vulkan

- upstream: `xinntao/Real-ESRGAN-ncnn-vulkan`
- adapter target release: `v0.2.0`
- upstream license: MIT
- purpose: optional super-resolution

## RIFE ncnn Vulkan

- upstream: `nihui/rife-ncnn-vulkan`
- adapter target release: `20221029`
- upstream RIFE implementation: MIT
- purpose: optional frame interpolation

Third-party packages are downloaded only after explicit user acceptance and are stored outside project source by default. Users may instead supply executable paths through AgentCut environment variables.
