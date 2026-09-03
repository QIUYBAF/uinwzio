# AGENTS.md — ProjectOS execution rules

This repository is used by both ChatGPT and Codex. Treat ChatGPT cloud context and Codex/local session history as separate memory domains. Never assume another session already knows the current project state.

## Minimal startup route

The default goal is **minimum sufficient context**, not maximum repository awareness.

1. If the task or handoff already gives a Project ID, go directly to its `00_ProjectOS/projects/<PROJECT_ID>_*.md` PROJECT_HOME.
2. If the Project ID is absent but the project name is clear, use `00_ProjectOS/CODEX_ROUTER.md` to map it; do not perform a repo-wide search.
3. Read `00_ProjectOS/ACTIVE_INDEX.md` only when routing is genuinely ambiguous or the task concerns status/scheduling across projects.
4. Read the full `00_ProjectOS/README.md` / `REPOSITORY_MAP.md` only for ProjectOS policy, repository governance, storage, cross-project conflicts, or recovery work.
5. After PROJECT_HOME, read only the source files, tests, assets, or task-specific docs needed for the requested change.
6. Workflows and historical/release docs are opt-in: read them only when the task actually depends on that workflow/history.
7. If this session came from ChatGPT, use the supplied DELTA / TASK / acceptance criteria; do not reconstruct the whole prior conversation.

For the detailed low-cost routing and search escalation rules, see `00_ProjectOS/CODEX_ROUTER.md`.

## Stop-search rule

Stop gathering context and begin execution once all are known:
- the unique PROJECT_HOME;
- the current TASK;
- acceptance criteria;
- the concrete files/paths to inspect or modify;
- no blocking contradiction remains.

Do not keep scanning unrelated projects merely to gain broader context.

## Repository boundary rule

Normal work is restricted to the current zones documented in `00_ProjectOS/REPOSITORY_MAP.md`.

Treat old topic/category roots such as `其他/`, `化学/`, `思想/`, `教育/`, `数学/`, `文学/`, `术数/`, `电脑/`, `templates/` and the old static-site generator files as **Frozen Legacy**.

Unless the task explicitly targets historical material:
- do not recursively search those roots;
- do not write new project assets there;
- do not use them as evidence for current project state;
- do not opportunistically rename/move/delete them.

Do not create new top-level project/test folders. A new software project must first receive a ProjectOS ID and PROJECT_HOME; then decide deliberately whether it belongs in this repository or a separate repo.

## Memory rule

Codex thread history is execution context, not durable project memory. Durable facts must live in PROJECT_HOME, Git, or the canonical Drive location.

On later sessions prefer a small handoff: `PROJECT_ID + DELTA + TASK + acceptance criteria`. A full self-contained handoff is only needed when the canonical PROJECT_HOME is missing or inaccessible.

Before ending meaningful work, return `RESULT / CHANGED / TEST / OPEN / NEXT / SYNC_BACK`. SYNC_BACK contains only durable facts the cloud side needs to persist.

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

## Search escalation

Use the cheapest level that can answer the task:

1. **Known path** — read/modify directly; no search.
2. **Project scope** — search only the matching project/code directory.
3. **Current workspace** — search `.github/`, `00_ProjectOS/`, and known active code roots.
4. **Repository recovery** — repo-wide search only when canonical paths are missing or contradictory.

A broad GitHub search still excludes Frozen Legacy unless the target is known to predate ProjectOS. Do not enumerate Drive/GitHub roots simply to rediscover locations already recorded in PROJECT_HOME.

## ACTIVE rule

Each project has one state: `ACTIVE`, `WAITING`, `DONE`, or `ARCHIVE`.
A current project must have only one unversioned ACTIVE entry and exactly one NEXT.
Never create parallel folders like `Project_v3_ACTIVE`, `Project_v4_ACTIVE`, `final2`, `latest-new`.
Use Git history/releases or archive folders for old versions.

## Preserve successful project identity

For established series and tools, treat PROJECT_HOME constraints as protected defaults.
Do not redesign visual language, editing grammar, character behavior, architecture, naming or interaction patterns merely because a new conversation/session started.

Meaningful changes require evidence/reason and must be recorded under `CHANGES`. Prefer local experiments over silently changing the whole project.

## Work policy

- Prefer the smallest reliable deliverable first.
- Avoid redoing validated work without evidence.
- Inspect existing implementation before changing it.
- Preserve verified working parts.
- Run the smallest relevant test first; expand only if risk warrants it.
- Reproducible cache/intermediate output is not permanent project memory.
- New ideas default to INBOX/WAITING rather than becoming ACTIVE automatically.

## File lifecycle

`INBOX -> ACTIVE -> DELIVERY -> ARCHIVE`

At completion, keep the minimum durable set: source/master files, final deliverable, cover/thumbnail, script/subtitles where relevant, PROJECT_HOME/decision notes, and required licensing/source notes. Delete clearly reproducible/obsolete intermediates; archive uncertain historical material instead of destroying it.

## End-of-session protocol

Report and/or update:
- `RESULT`
- `CHANGED`
- `TEST`
- `OPEN`
- `NEXT` — exactly one concrete next step
- `SYNC_BACK` — only durable new facts

Do not dump the full execution log into PROJECT_HOME.
