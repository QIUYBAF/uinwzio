# AGENTS.md — AgentCut 1.0.0 Remaster

Default entry for Codex, ChatGPT Work and other agent runtimes.

## Zero-search rule
Do not search for the latest AgentCut. Read `agentcut.manifest.json`; if it says `latest: true`, use this checkout.

Run:
```bash
python -m pip install -e .
agentcut discover
agentcut doctor
```

Existing project:
```bash
agentcut agent-start PROJECT --task "<current task>"
```
New project:
```bash
agentcut setup PROJECT --create --name "<name>"
agentcut agent-start PROJECT --task "<current task>"
```

## Backend rule
Remotion is optional. Do not spend a session hunting Chromium, rewriting package.json or repairing PATH merely to begin editing. Use Remotion when healthy; otherwise use deterministic FFmpeg/Pillow fallback and report the backend choice.

## Context rule
`project.json` is truth. Prefer bootstrap → scoped context → preflight → apply → local render → QA. Do not reread repository history, old release notes, chat transcripts or unrelated projects.

## Cloud / Work mode
Cloud may lack persistent Node, Chromium, GPU tools or package privileges. Run `agentcut discover` first. Missing optional components must not destroy/rebuild canonical state. If final rendering is impossible, preserve the project and return one explicit missing-runtime requirement.

## Version rule
1.0.x = deployment/bug/reliability; 1.x = backward-compatible capabilities; 2.0 = breaking state/API. Never revive 3.x numbering. Director 4.0 is skipped as a release baseline.

Stop gathering context once task, project, touched scope and available backend are known.
