# SW-01 AgentCut — PROJECT_HOME

**STATUS:** ACTIVE  
**UPDATED:** 2026-09-05

## Current truth

**Current release line: AgentCut 1.x**  
**LATEST: 1.0.0 Remaster**

The old 0.2/3.x numbering is frozen history. AgentCut Director 4.0 is skipped as a release baseline. Do not infer a newer release from old folders, Drive handoffs, or historical notes.

## One-line goal
Build an Agent-native editing runtime that Codex and ChatGPT Work can locate, understand and start with minimal context/setup while preserving structured state, local edits, undo/diff/history and deterministic rendering.

## Unique startup route

```text
AgentCut/agentcut.manifest.json
→ AgentCut/AGENTS.md
→ agentcut discover
→ agentcut doctor
→ project agent-start / scoped context
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

## Current release — 1.0.0 Remaster
Based on the verified 3.3.1 runtime, with a reset control surface for agents:
- machine-readable `agentcut.manifest.json` is the unique version truth;
- `AGENTS.md` is the default Codex/Work entry;
- `agentcut discover` is project-free environment/backend discovery;
- explicit cloud/Work fallback policy;
- optional heavy AI runtimes are not part of the lightweight GitHub checkout;
- no major editing feature intentionally added.

## Validation status
- Remaster-specific tests: 2/2 passed.
- Python compile check: passed.
- `python -m agentcut discover`: passed in current Linux cloud runtime.
- Full inherited 3.3.1 regression was not rerun to completion in this remaster session; do not claim it was. The source baseline had a prior 156/156 release validation before the remaster.

## NEXT — exactly one
**1.0.1 Quick Connect:** synchronize the remaining full lightweight runtime source into GitHub and harden fresh-environment bootstrap/doctor/backend-auto, including real Remotion npm + Chromium E2E where the environment permits it.
