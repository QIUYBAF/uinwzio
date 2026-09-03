# uinwzio — ProjectOS workspace

本仓库承担 **ProjectOS 控制面 + 软件代码 + 历史 Legacy** 三种职责。正常工作只进入明确的当前区，不从根目录盲目遍历。

## Codex 最短入口

**已有任务 / handoff 已给 Project ID：**

```text
对应 PROJECT_HOME → task files → execute/test → SYNC_BACK
```

不需要先通读本 README、完整 ProjectOS 制度或 ACTIVE_INDEX。

**Project ID 未知：** 读 `00_ProjectOS/CODEX_ROUTER.md`。只有跨项目调度、制度维护或恢复任务才进入完整控制面。

## 人类 / 仓库治理入口

- `AGENTS.md` — Codex / AI 仓库级执行规则
- `00_ProjectOS/CODEX_ROUTER.md` — 最小执行路由
- `00_ProjectOS/README.md` — ProjectOS 制度真源
- `00_ProjectOS/ACTIVE_INDEX.md` — 跨项目状态板，不是常规任务必读
- `00_ProjectOS/REPOSITORY_MAP.md` — GitHub 目录地图
- `00_ProjectOS/projects/` — 各项目唯一 PROJECT_HOME
- `00_ProjectOS/workflows/` — 按需标准工作流
- `00_ProjectOS/STORAGE_AND_RETENTION.md` — 储存与保留规则

## 当前有效区域

| 路径 | 角色 | 默认是否搜索 |
|---|---|---|
| `00_ProjectOS/` | 控制面、PROJECT_HOME、制度、workflow | 精确读取，不整目录扫描 |
| `AgentCut/` | `SW-01 AgentCut` 当前代码与技术文档 | 对 SW-01 按任务范围搜索 |
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
- **Codex / 本地**：执行现场；跨端通过 PROJECT_HOME + DELTA/TASK/ACCEPTANCE 显式同步。
- **B站**：发布终点与数据反馈。

## 效率规则

- 已知 ID 直达 PROJECT_HOME；未知 ID 才路由。
- 一旦任务、验收标准和目标文件明确，就停止继续搜索。
- workflow、release notes、QA、历史 notes 按需读取，不作为礼仪性必读材料。
- 每个项目只有一个 PROJECT_HOME 和一个 NEXT，避免同一事实在多个控制文档重复维护。
- 先做最小相关测试，再根据风险扩大回归。

## 储存安全

大文件不得把 GitHub 变成第二个 Drive。视频、音频交付包、ZIP、可执行程序、模型权重和可再生成构建产物默认由 `.gitignore` 拦截并存入 Drive。

仓库历史若需真正瘦身，必须先完成大对象审计、Drive 真源核验和镜像备份；普通目录整理不得直接 force-push 重写历史。

## Legacy 策略

当前采用两阶段治理：
1. **逻辑冻结**：旧根目录正常 AI/Codex 工作不搜索、不写入；
2. **物理迁移**：未来完成依赖审计后一次性迁入 `90_Legacy/legacy_site/` 并修复引用。

对于 Codex usage 而言，逻辑冻结已经获得主要收益；物理搬迁只在确有维护价值时进行。
