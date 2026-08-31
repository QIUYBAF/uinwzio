# AGENTS.md — ProjectOS execution rules

This repository is used by both ChatGPT and Codex. Treat ChatGPT cloud context and Codex/local session history as separate memory domains. Never assume Codex knows what was discussed in ChatGPT, or vice versa.

## Mandatory startup sequence
1. Read `00_ProjectOS/README.md`.
2. Read `00_ProjectOS/ACTIVE_INDEX.md`.
3. Identify the project ID.
4. Read the matching `00_ProjectOS/projects/<PROJECT_ID>_*.md` PROJECT_HOME.
5. Read the matching workflow under `00_ProjectOS/workflows/` when relevant.
6. If this session came from ChatGPT, read the supplied CODEX_HANDOFF / DELTA before execution.
7. Do not ask the user to repeat information already written there unless it is genuinely contradictory, stale, or missing.

## Memory rule
Codex thread history is execution context, not durable project memory. Durable facts must live in PROJECT_HOME, Git, or the canonical Drive location.

When a project is first transferred from ChatGPT cloud, require a self-contained handoff. On later sessions prefer a small delta: `PROJECT_HOME + DELTA + TASK + acceptance criteria`.

Before ending meaningful work, return `RESULT / CHANGED / TEST / OPEN / NEXT / SYNC_BACK`. SYNC_BACK contains only facts that the ChatGPT cloud side needs to persist.

## Project IDs
- `CT-*` content/video series
- `IP-*` original IP/worldbuilding
- `SW-*` software/tools
- `OPS-*` operations/publishing
- `LAB-*` study/research

Use the same project ID in ChatGPT group names, Codex/local folders, Google Drive folders, filenames and handoffs whenever possible.

## Source-of-truth rules
- GitHub: code, ProjectOS, PROJECT_HOME, technical version history.
- Google Drive: large media, source assets, executables, final delivery packages.
- ChatGPT Library: short summaries, prompts, references, AI quick-entry memory.
- Local filesystem/Codex: execution workspace and cache unless committed/uploaded.
- Bilibili: publishing endpoint and performance feedback, not asset storage.

Do not create another source of truth without explicitly recording why.

## Search policy
1. PROJECT_HOME and known project paths first.
2. Known GitHub/Drive ACTIVE location second.
3. Matching Library project folder third.
4. Broad/global search only for recovery.

In ChatGPT Library, normal work is scoped to `00_工作台`, `10_内容项目`, `20_软件项目`, `30_运营`, `40_学习研究`, `90_归档`, `99_收件箱`.
Treat loose historical files in the Library root as Legacy. Do not include them in normal searches. Some legacy root entries may be stale indexes whose backing files no longer exist; do not repeatedly retry them.

Avoid repeatedly enumerating Drive/GitHub roots just to rediscover known locations.

## ACTIVE rule
Each project has one state: `ACTIVE`, `WAITING`, `DONE`, or `ARCHIVE`.
A current project must have only one unversioned ACTIVE entry and exactly one NEXT.
Never create parallel folders like `Project_v3_ACTIVE`, `Project_v4_ACTIVE`, `final2`, `latest-new`.
Use Git history/releases or archive folders for old versions.

## Preserve successful project identity
For established series and tools, treat PROJECT_HOME constraints as protected defaults.
Do not redesign visual language, editing grammar, character behavior, architecture, naming or interaction patterns merely because a new conversation/session started.

For content series, the established audience experience is effectively an interface contract. Meaningful changes require evidence/reason and must be recorded under `CHANGES`. Prefer local experiments over silently changing the whole series.

## Work policy
- Prefer the smallest reliable deliverable first.
- Avoid redoing validated work without evidence.
- For heavy production, no more than 3 main ACTIVE projects per week.
- New ideas default to INBOX/WAITING rather than becoming ACTIVE automatically.
- Inspect existing implementation before changing it.
- Preserve verified working parts.
- Test actual outputs where possible.
- If a file is reproducible cache/intermediate output, do not treat it as permanent project memory.

## File lifecycle
`INBOX -> ACTIVE -> DELIVERY -> ARCHIVE`

At completion, keep the minimum durable set: source/master files, final deliverable, cover/thumbnail, script/subtitles where relevant, PROJECT_HOME/decision notes, and required licensing/source notes. Delete clearly reproducible/obsolete intermediates; archive uncertain historical material instead of destroying it.

## End-of-session protocol
Report and/or update:
- `STATUS`
- `DONE`
- `NEXT` — exactly one concrete next step
- `BLOCKERS`
- `FILES` — source-of-truth locations
- `CHANGES` — `none` unless a stable project rule changed

Then provide `SYNC_BACK` for the cloud side. Do not dump the entire execution log into PROJECT_HOME.
