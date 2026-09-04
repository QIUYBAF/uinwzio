# AgentCut 1.0.0 Remaster — CURRENT

**LATEST / STABLE BASELINE: 1.0.0 Remaster**

This is the reset baseline after the 3.x experimental line, designed so Codex and ChatGPT Work can locate the current AgentCut without version archaeology.

## Agent start

Read `agentcut.manifest.json` → `AGENTS.md`, then:

```bash
python -m pip install -e .
agentcut discover
agentcut doctor
```

For a project, use `agentcut setup PROJECT --create` and `agentcut agent-start PROJECT --task "..."`.

## 1.0.0 Remaster

- unique version truth: `agentcut.manifest.json`;
- unique agent entry: `AGENTS.md`;
- project-free `agentcut discover` environment/backend probe;
- explicit Codex + ChatGPT Work/cloud behavior;
- Remotion optional; deterministic FFmpeg/Pillow fallback policy;
- old 0.2/3.x numbering frozen; Director 4.0 skipped as a release baseline;
- SemVer from this point: 1.0.x fixes/deployment, 1.x compatible capability, 2.0 breaking change.

No major editing feature was intentionally added.

## Current boundary

The 1.0.0 control/discovery layer is live on GitHub. The complete inherited 3.3.1 lightweight runtime source is not yet fully synchronized into `AgentCut/` in this session, so a fresh GitHub-only clone is **not yet claimed fully installable**. The packaged 1.0.0 Remaster source artifact is the reference for completing that sync.

Validation completed here: remaster tests 2/2; Python compile check; `python -m agentcut discover`. The inherited 3.3.1 baseline had a prior 156-test release validation, but that full suite was not rerun to completion during this remaster.

## NEXT

**1.0.1 Quick Connect:** finish lightweight runtime source sync, fresh-machine bootstrap, actionable doctor/fix, backend-auto, and real npm + Chromium/Remotion E2E where available. Do not begin a feature-heavy 1.1 before this closes.

Heavy optional Real-ESRGAN binaries/models stay out of the active GitHub checkout to keep Codex/Work startup light.
