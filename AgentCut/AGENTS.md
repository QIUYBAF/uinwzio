# AGENTS.md — AgentCut 1.0.1 Remaster

Default entry for Codex, ChatGPT Work, and other agent runtimes.

## Zero-search rule

Do not search for the latest AgentCut. Read `agentcut.manifest.json`; when it says `latest: true`, use this checkout. From the repository root:

```bash
python AgentCut/run.py discover
python AgentCut/run.py quickstart PROJECT --create --task "<current task>"
```

For an existing project, omit `--create`. If installed, replace `python AgentCut/run.py` with `agentcut`.

## Backend rule

Use `backend` or the backend returned by `quickstart`. Remotion is optional and is available only when a real executable is detected. Use deterministic FFmpeg/Pillow fallback when possible; do not block project editing on Chromium, GPU, ASR, or AI enhancement.

## Context rule

`project.json` is truth. Prefer quickstart/bootstrap → scoped context → preflight → apply → local render → QA. Do not reread repository history, old release notes, chat transcripts, or unrelated projects.

## Cloud / Work mode

Cloud may lack persistent Node, Chromium, GPU tools, or package privileges. Missing optional components must not rebuild or damage canonical state. If rendering is unavailable, preserve the project and report the single missing runtime requirement from `doctor`.

## Version rule

1.0.x = deployment/bug/reliability; 1.x = backward-compatible capabilities; 2.0 = breaking state/API. Never revive 3.x numbering. Director 4.0 is not a release baseline.

Stop gathering context once the task, project, touched scope, and available backend are known.
