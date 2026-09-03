# uinwzio — ProjectOS workspace

本仓库当前同时承载 ProjectOS、软件项目与若干历史内容。新的 AI / Codex 会话不要从根目录盲目遍历；先从下面的固定入口开始。

## 固定入口

1. `AGENTS.md` — Codex / AI 接管规则
2. `00_ProjectOS/README.md` — 统一工作制度（制度真源）
3. `00_ProjectOS/ACTIVE_INDEX.md` — 当前项目编号与状态
4. `00_ProjectOS/projects/` — 各项目 PROJECT_HOME
5. `00_ProjectOS/workflows/` — 内容、绘画、发布、软件发布标准工作流
6. `00_ProjectOS/STORAGE_AND_RETENTION.md` — Library / Drive / GitHub 储存边界、命名、保留与清理记录
7. `AgentCut/` — SW-01 AgentCut 当前代码目录

## 平台职责

- GitHub：ProjectOS、PROJECT_HOME、代码、文本规则、技术版本历史。
- Google Drive：大型素材、音视频、可执行程序、发布交付。
- ChatGPT Library：轻量入口、项目摘要、提示词与参考；不要把根目录散件当作工作入口。
- Codex / 本地：执行现场。Codex 的会话历史不等于 ChatGPT 的个人/项目记忆，必须通过 PROJECT_HOME / HANDOFF 显式同步。
- B站：发布终点与数据反馈。

## 工作规则

已有项目先找项目 ID，再读 PROJECT_HOME；禁止因为换了会话就重新设计已验证的系列风格或软件架构。每个项目只允许一个 ACTIVE 和一个 NEXT。跨端交接使用 `STATUS / DONE / NEXT / BLOCKERS / FILES / CHANGES`。

## 储存安全

大文件不得把 GitHub 或 Library 变成第二个 Drive。视频、音频交付包、ZIP、可执行程序、模型权重和可再生成构建产物默认由 `.gitignore` 拦截并存入 Drive。超过跨端单文件限制时，按 `STORAGE_AND_RETENTION.md` 的无损分卷与 SHA-256 规则处理。

## Legacy

根目录仍有部分旧网页/脚本文件，暂不大规模移动，以免破坏历史依赖。它们默认视为 Legacy，不参与正常项目检索。旧版根 README 已保存到 `90_Legacy/README_legacy_taxonomy.md`。

仓库历史若需真正瘦身，必须先做大对象审计、镜像备份和 Drive 真源核验；普通整理不得直接 force-push 重写历史。
