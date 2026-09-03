# uinwzio — ProjectOS workspace

本仓库当前承担 **ProjectOS 控制面 + 软件代码 + 历史 Legacy** 三种职责。正常工作只进入明确的当前区，不从根目录盲目遍历。

## 从这里开始

1. `AGENTS.md` — Codex / AI 仓库级执行规则
2. `00_ProjectOS/README.md` — ProjectOS 制度真源
3. `00_ProjectOS/ACTIVE_INDEX.md` — 当前项目编号与状态
4. `00_ProjectOS/REPOSITORY_MAP.md` — **GitHub 唯一目录地图：哪些是当前项目，哪些只是历史遗留**
5. `00_ProjectOS/projects/` — 各项目唯一 PROJECT_HOME
6. `00_ProjectOS/workflows/` — 内容、绘画、发布、软件发布标准工作流
7. `00_ProjectOS/STORAGE_AND_RETENTION.md` — Library / Drive / GitHub 储存与保留规则

## 当前有效区域

| 路径 | 角色 | 默认是否搜索 |
|---|---|---|
| `00_ProjectOS/` | 控制面、PROJECT_HOME、制度、workflow | 是 |
| `AgentCut/` | `SW-01 AgentCut` 当前代码与技术文档 | 对 SW-01 是 |
| `.github/` | Actions / CI / 仓库自动化 | 需要时 |
| `90_Legacy/` | 明确归档的历史内容 | 否 |
| 旧知识分类根目录 | Frozen Legacy | 否 |

旧知识分类根目录包括 `其他/`、`化学/`、`思想/`、`教育/`、`数学/`、`文学/`、`术数/`、`电脑/`、`templates/` 以及旧网页生成文件。它们不是当前项目入口；完整规则见 `00_ProjectOS/REPOSITORY_MAP.md`。

## 根目录准入

从 2026-09-03 起，不再随意往仓库根目录新增项目文件夹、测试目录或 `final/latest/new` 类散件。

新内容原则上只能进入：

- `00_ProjectOS/`：项目控制与文本真源；
- 已登记的软件代码目录；
- `.github/`：自动化；
- `90_Legacy/`：归档。

未来新软件项目先建立项目 ID 与 PROJECT_HOME，再决定建立独立 repo 或代码目录，不直接污染根目录。

## 平台职责

- **GitHub**：ProjectOS、PROJECT_HOME、代码、文本规则、技术版本历史。
- **Google Drive**：大型素材、音视频、可执行程序、可编辑工程、最终交付。
- **ChatGPT Library**：轻量入口、项目摘要、提示词与参考。
- **Codex / 本地**：执行现场；跨端通过 PROJECT_HOME / HANDOFF 显式同步。
- **B站**：发布终点与数据反馈。

## 工作规则

已有项目先找项目 ID，再读 PROJECT_HOME。每个项目只允许一个 ACTIVE 和一个 NEXT；禁止因为换会话而重新设计已经验证的系列风格或软件架构。跨端交接统一使用 `STATUS / DONE / NEXT / BLOCKERS / FILES / CHANGES`。

## 储存安全

大文件不得把 GitHub 变成第二个 Drive。视频、音频交付包、ZIP、可执行程序、模型权重和可再生成构建产物默认由 `.gitignore` 拦截并存入 Drive。

仓库历史若需真正瘦身，必须先完成大对象审计、Drive 真源核验和镜像备份；普通目录整理不得直接 force-push 重写历史。

## Legacy 策略

当前采用“两阶段治理”：

1. **逻辑冻结**：旧根目录已统一定义为 Frozen Legacy，正常 AI/Codex 工作不再搜索或写入；
2. **物理迁移**：未来完成依赖审计后，一次性迁入 `90_Legacy/legacy_site/` 并修复引用，而不是长期零散搬动。

这样既让当前开发路径清晰，也避免为了美观破坏仍可能存在的历史依赖。
