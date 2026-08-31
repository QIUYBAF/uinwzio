# AGENTS.md — Project OS

This repository is used by both ChatGPT and Codex. Before starting work on any existing project, follow these rules.

## Start here
1. Read `00_ProjectOS/README.md`.
2. Read `00_ProjectOS/ACTIVE_INDEX.md`.
3. Read the matching `00_ProjectOS/projects/<PROJECT_ID>_*.md` PROJECT_HOME file.
4. Read the matching workflow under `00_ProjectOS/workflows/` when relevant.
5. Do not ask the user to repeat information already written there unless it is genuinely contradictory or stale.

## Project IDs
- `CT-*` content/video series
- `IP-*` original IP/worldbuilding
- `SW-*` software/tools
- `OPS-*` operations/publishing
- `LAB-*` study/research

Use the same project ID in ChatGPT group names, Codex/local folders, Google Drive folders, filenames and handoffs whenever possible.

## Source-of-truth rules
- GitHub: code, Project OS, PROJECT_HOME, technical version history.
- Google Drive: large media, source assets, executables, final delivery packages.
- ChatGPT Library: short summaries, prompts, references, AI working memory.
- Local filesystem/Codex: execution workspace and cache only unless committed/uploaded.

Do not create another source of truth without explicitly recording why.

## Search policy
- Search PROJECT_HOME and known project paths first.
- In ChatGPT Library, default to the standardized folders `00_工作台`, `10_内容项目`, `20_软件项目`, `30_运营`, `40_学习研究`, `90_归档`, `99_收件箱`.
- Treat loose historical files in the Library root as Legacy. Do not include them in normal searches.
- Use a broad/all-Library search only for recovery when the expected scoped locations fail.
- Avoid repeatedly enumerating Drive/GitHub roots just to rediscover known locations.

## ACTIVE rule
Each project has one state: `ACTIVE`, `WAITING`, `DONE`, or `ARCHIVE`.
A current project must have only one unversioned ACTIVE entry. Never create parallel folders like `Project_v3_ACTIVE`, `Project_v4_ACTIVE`.
Use Git history/releases or archive folders for old versions.

## Preserve successful project identity
For established series and tools, treat PROJECT_HOME constraints as protected defaults.
Do not redesign visual language, editing grammar, character behavior, architecture, naming or interaction patterns merely because a new conversation/session started.
If a meaningful rule changes, record it under `CHANGES` with the reason/evidence.

## Handoff protocol
Before ending a meaningful work session, update or produce exactly these fields:
- `STATUS`
- `DONE`
- `NEXT` — one concrete next step only
- `BLOCKERS`
- `FILES` — source-of-truth locations
- `CHANGES` — `none` unless a stable rule changed

## Work policy
- Prefer the smallest reliable deliverable first.
- Avoid redoing validated work without evidence.
- For heavy production, no more than 3 main ACTIVE projects per week.
- New ideas default to INBOX/WAITING rather than becoming ACTIVE automatically.
- Search PROJECT_HOME/known paths before broad repository/Drive searches to reduce wasted tokens.
- When a file is reproducible cache/intermediate output, do not treat it as permanent project memory.

## File lifecycle
`INBOX -> ACTIVE -> DELIVERY -> ARCHIVE`

At completion, keep the minimum durable set: source/master files, final deliverable, cover/thumbnail, script/subtitles where relevant, PROJECT_HOME/decision notes, and required licensing/source notes. Archive or delete obsolete generated intermediates as appropriate.
