# SW-01 AgentCut — PROJECT_HOME

**STATUS:** ACTIVE  
**UPDATED:** 2026-09-04

## Current truth

**Current release line: AgentCut 1.x**  
**LATEST: 1.0.1 Remaster — Quick Connect**

The old 0.2/3.x numbering is frozen history. AgentCut Director 4.0 is skipped as a release baseline. Do not infer a newer release from old folders, Drive handoffs, or historical notes.

## One-line goal
Build an Agent-native editing runtime that Codex and ChatGPT Work can locate, understand and start with minimal context/setup while preserving structured state, local edits, undo/diff/history and deterministic rendering.

## Unique startup route

```text
AgentCut/agentcut.manifest.json
→ AgentCut/AGENTS.md
→ python AgentCut/run.py discover
→ python AgentCut/run.py quickstart PROJECT [--create] --task "..."
→ scoped context / preflight / apply
```

Do not scan release history before executing a normal task.

## Product invariants
- `project.json` / equivalent canonical state is truth.
- API/semantic operations over GUI clicking.
- Non-destructive assets; history/undo/diff retained.
- Preview/local render before expensive final render.
- Remotion is an optional presentation backend, not a prerequisite for project state/editing.
- FFmpeg/Pillow deterministic fallback keeps the project operable when cloud/local optional runtimes are missing.
- Codex/Work should stop searching once manifest, task, project and backend availability are known.

## Platform boundary
- GitHub: current lightweight source + manifest + agent entry + ProjectOS truth.
- Drive: large binaries/models/media/handoffs when needed; not the version selector.
- Codex/local: execution/build environment.
- ChatGPT Work/cloud: may lack persistent Node/Chromium/GPU/system privileges; discover first and degrade gracefully.

## Version policy
- `1.0.x`: deployment, bugs, reliability, compatibility.
- `1.x.0`: backward-compatible new capability.
- `2.0.0`: breaking API/state change only.
- Never revive 3.x numbering.

## Current release — 1.0.1 Remaster
Based on the verified 3.3.1 runtime, with a reset control surface for agents:
- machine-readable `agentcut.manifest.json` is the unique version truth;
- `AGENTS.md` is the default Codex/Work entry;
- the full lightweight editing runtime and test suite are present in GitHub;
- `run.py` works directly from a downloaded checkout without editable installation;
- `discover`, actionable non-crashing `doctor`, and verified `backend` auto-selection are project-free;
- `quickstart` combines project create/open, runtime setup, discovery, diagnosis, backend choice, and agent bootstrap;
- explicit cloud/Work fallback policy;
- optional heavy AI runtimes are not part of the lightweight GitHub checkout;
- no major editing feature intentionally added.

## Validation status
- Full regression: 163/163 passed in the current Linux cloud runtime.
- Strict release/version/source check: passed.
- Python compile check: passed.
- Direct checkout `discover`, `doctor`, and `quickstart --create` smoke tests: passed.
- Backend auto selected FFmpeg/Pillow and did not mistake Node/npm alone for Remotion.
- Real npm + Chromium/Remotion E2E was not available in this environment and is not claimed.

## NEXT — exactly one
**1.0.x maintenance:** keep deployment and compatibility stable; validate optional Remotion npm + Chromium E2E when an appropriate environment is available.
