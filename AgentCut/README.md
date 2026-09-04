# AgentCut 1.0.1 Remaster — CURRENT

**LATEST / STABLE BASELINE: 1.0.1 Remaster**

AgentCut is an agent-native semantic video editing runtime. Version 1.0.1 restores the complete lightweight 3.3.1 editing surface behind one current manifest and a low-friction Work/Codex entry.

## Run immediately after download

From the repository root, no editable install is required:

```bash
python AgentCut/run.py discover
python AgentCut/run.py quickstart PROJECT --create --task "Describe the edit"
```

From inside `AgentCut/`, use `python run.py ...`. To install the `agentcut` command:

```bash
python -m pip install -e AgentCut
agentcut quickstart PROJECT --create --task "Describe the edit"
```

`quickstart` creates or opens the project, prepares its local runtime, detects the backend, runs diagnostics, and returns the compact agent bootstrap in one JSON response.

## Agent entry

Read `agentcut.manifest.json`, then `AGENTS.md`. Useful project-free commands:

```bash
python AgentCut/run.py discover
python AgentCut/run.py doctor
python AgentCut/run.py backend
```

`doctor` degrades cleanly when FFmpeg, Remotion, Chromium, AI enhancement, or ASR components are absent. `doctor --fix` only creates safe local AgentCut runtime directories; it does not install system software.

## Restored functionality

- canonical `project.json` state with history, undo/redo, diff, checkpoints, and atomic batches;
- agent context, operation schema, normalization, preflight, optimistic concurrency, apply receipts, and resume capsules;
- scene, asset, camera, transition, effects, audio, caption, dialogue, composition, cast, and cinematic operations;
- proxy/scene/span/final rendering, export planning, cache, contact sheets, and QA;
- subtitle/SRT workflows with optional Whisper.cpp ASR;
- Gen3/Jane3 scene grammar, actor cards, tile extraction/stitching, chroma key, and optional Remotion bridge;
- optional Real-ESRGAN/RIFE integrations with deterministic FFmpeg/Pillow fallbacks.

## Runtime policy

Remotion is selected only when a real local executable is available and React/UI rendering is requested. Otherwise AgentCut uses FFmpeg/Pillow. Heavy Real-ESRGAN binaries, model weights, Chromium, and generated media are intentionally excluded from the lightweight source checkout.

The version source of truth is `agentcut.manifest.json`. Old 0.2/3.x releases and Director 4.0 experiments are history, not startup candidates.

## Validation

Run from `AgentCut/`:

```bash
python run.py release-check . --strict
python -m pytest -q
```

Release validation for 1.0.1 completed with 164/164 tests passing. Optional real Chromium/Remotion rendering was not available in the validation environment and is not claimed.

SemVer policy: 1.0.x is for deployment, bug, reliability, and compatibility patches; 1.x adds compatible capability; 2.0 is reserved for breaking state/API changes.
