# Repository Map — GitHub 目录地图

**UPDATED:** 2026-09-03

本文件回答一个问题：**这个仓库里什么是当前工作区，什么只是历史遗留？**

## 1. 当前工作区（默认只看这里）

### `00_ProjectOS/`
项目控制面与制度真源。

- `README.md`：统一工作制度
- `ACTIVE_INDEX.md`：当前项目入口
- `projects/`：各项目唯一 PROJECT_HOME
- `workflows/`：标准工作流
- `STORAGE_AND_RETENTION.md`：跨平台储存规则
- `REPOSITORY_MAP.md`：本文件

### `AgentCut/`
`SW-01 AgentCut` 当前代码与技术文档目录。

这是历史原因保留的短名称；在所有 ProjectOS / Drive / Library / handoff 中仍以项目 ID `SW-01` 标识。除非单独执行迁移任务，不为了目录美观重命名此路径，避免破坏构建、workflow 或既有引用。

### `.github/`
GitHub Actions 与仓库自动化。属于当前基础设施。

### `AGENTS.md`
Codex / AI 的仓库级执行规则。

### `README.md`
人类与 AI 的根入口。

## 2. 归档区

### `90_Legacy/`
已经明确归档的旧制度、旧分类说明和未来迁移后的历史内容。

默认行为：**不搜索、不修改、不用于新项目决策**，除非任务明确要求恢复历史资料。

## 3. 根目录历史遗留区（冻结 Legacy）

以下目录来自本仓库早期作为个人知识库/网页分类系统的时期：

- `其他/`
- `化学/`
- `思想/`
- `教育/`
- `数学/`
- `文学/`
- `术数/`
- `电脑/`
- `templates/`
- 以及与旧网页生成体系直接绑定的根文件，如 `index.*`、`build.py`、`gen_css.py`、`make_indexorg.py` 等。

这些内容当前统一标记为 **Frozen Legacy**：

1. 不属于 ProjectOS 活跃项目；
2. 不作为 Codex / ChatGPT 正常检索入口；
3. 不继续往这些目录加入新项目资产；
4. 未完成依赖审计前不批量搬迁或删除；
5. 未来若确认无现行依赖，再整体迁入 `90_Legacy/legacy_site/`，而不是逐次零散整理。

## 4. 根目录准入规则

从 2026-09-03 起，**禁止随意新增顶层目录或散落文件**。

允许的新增内容原则上只能进入：

- `00_ProjectOS/`：制度、PROJECT_HOME、workflow、索引；
- 已有明确的软件代码目录（当前为 `AgentCut/`）；
- `.github/`：CI / Actions；
- `90_Legacy/`：明确归档。

若未来新增独立软件项目，应先建立项目 ID 和 PROJECT_HOME，再决定是否创建独立 repo；不要直接在本仓库根目录生成 `new-project`、`test2`、`final` 一类目录。

## 5. AI / Codex 默认搜索边界

正常任务默认搜索范围：

`README.md -> AGENTS.md -> 00_ProjectOS/ -> 对应 PROJECT_HOME -> 已知代码目录`

除非前述路径不足，**禁止递归扫描 Frozen Legacy 根目录**。

## 6. 当前推荐视觉结构

```text
uinwzio/
├─ README.md
├─ AGENTS.md
├─ .github/                 # CI / automation
├─ 00_ProjectOS/            # 控制面 / PROJECT_HOME / workflow
├─ AgentCut/                # SW-01 当前代码
├─ 90_Legacy/               # 已归档历史
└─ [Frozen Legacy roots]    # 旧知识库，仅暂存，默认忽略
```

这不是最终物理迁移结果，而是**当前唯一逻辑结构**。后续若做 Legacy 物理迁移，应一次性完成依赖审计、路径迁移和引用修复，不做长期半迁移状态。
