# AgentCut — CURRENT

> **LATEST USABLE RELEASE: 3.3.1** — 2026-09-03  
> **Current production baseline:** 3.3.1  
> **Current P0:** deployment / Remotion environment friction  
> **Do not treat 3.2.3 or any Alpha note as current.**

AgentCut is an Agent-native semantic video editing runtime. Its core identity remains: structured state, deterministic edits, local modification, undo/diff/history, cheap preview, and reproducible export.

## Start here — Codex / AI

For SW-01 work, use the shortest path:

```text
00_ProjectOS/projects/SW-01_AgentCut.md
→ AgentCut/README.md
→ only the concrete source/test files required by the task
```

Do **not** enumerate old release notes or reconstruct project state from historical docs.

## Current version truth

### 3.3.1 — current usable baseline

3.3.1 is the newest verified usable AgentCut package currently present in the project storage.

Verified on 2026-09-03:

- 156 automated tests passed, 0 failed;
- `agentcut doctor`: pass;
- CLI/API package version: 3.3.1;
- task-scoped Agent context and warm bootstrap;
- local render-scope planning;
- Remotion Bridge v2 integrity / tamper verification;
- three-scene bridge E2E proxy render + QA pass.

### AgentCut Director 4.0.0 — NOT a current release

A Drive folder named `AgentCut_Director_4.0.0_Handoff` exists, but it is currently an empty placeholder. Until it contains a real source/package/validation handoff, **do not select it as latest and do not deploy from it**.

## Important source-of-truth warning

The GitHub `AgentCut/` directory currently contains the control/documentation layer and tool metadata, **not the complete installable 3.3.1 source tree**. The deployable 3.3.1 wheel/source/handoff is currently stored in Drive under:

`SW-01_AgentCut_ACTIVE/AgentCut_v3.3.1_Handoff`

Current package folder:
https://drive.google.com/drive/folders/1uOdLQHuwjulgfOylcNRR-f8igtQB0DrL

If that package is not available in the execution environment, stop and report the missing package path. **Never silently fall back to the 3.2.3 GitHub docs as though they were the latest source.**

Synchronizing the current source tree back to GitHub is part of the deployment P0.

## Why deployment is currently too heavy

AgentCut itself can fall back to deterministic FFmpeg/Pillow rendering, but the preferred AgentCut + Remotion path crosses multiple runtime boundaries:

- Python / AgentCut package;
- FFmpeg / ffprobe;
- Node.js + npm;
- pinned Remotion / React dependencies;
- Chromium used by Remotion rendering;
- optional bundled Real-ESRGAN and optional whisper.cpp / RIFE.

3.3.1 verified Remotion Bridge v2 generation and integrity, but its validation did **not** claim a fresh npm dependency installation + Chromium render in the isolated validation environment. Therefore a green AgentCut test suite does not prove low-friction Remotion deployment.

This is now treated as a product bug, not as user setup work.

## NEXT — v3.4 deployment-first iteration

Do not add major editing features before closing this P0.

Target experience:

```text
install AgentCut
→ agentcut setup --remotion   # or equivalent single bootstrap command
→ agentcut doctor
→ agentcut render PROJECT --backend auto
```

Acceptance criteria:

1. Fresh Windows and Linux environments require no manual editing of `package.json`, no manual Chromium hunting, and no ad-hoc PATH surgery.
2. Node/Remotion/Chromium versions are pinned and reproducible.
3. `agentcut doctor --fix` (or equivalent) can repair ordinary missing dependencies or return one actionable machine-readable failure.
4. `--backend auto` selects Remotion when healthy and falls back deterministically when it is unavailable; the user should not rebuild the bridge manually.
5. Release validation must include **real npm install + real Chromium/Remotion render**, not only bridge bundle generation/static integrity.
6. One small real project must deploy and render end-to-end from a fresh environment before the release is called stable.
7. Current 3.3.1 source/wheel/version manifest must be synchronized so GitHub has an unambiguous current source entry.

## Durable references

Keep these current files only when relevant:

- `README.md` — authoritative current release / deployment status.
- `AGENT_PROTOCOL.md` — Agent editing protocol.
- `agent_tools.json` — machine-readable capability metadata.
- `THIRD_PARTY_AI.md` — third-party runtime/license boundary.
- `LIBRARY_CATALOG.md` — reusable editing vocabulary.
- `HISTORY.md` — compressed milestone history.

Detailed old per-version notes are intentionally removed from the current tree. Git history remains the archaeology layer.
