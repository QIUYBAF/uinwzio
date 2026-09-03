# Repository Map — GitHub 目录地图

**UPDATED:** 2026-09-03

本文件回答：当前工作入口在哪里，哪些内容是活跃源码，哪些只是历史或兼容资产。

## 1. 当前工作区

### `00_ProjectOS/`

项目控制面与制度真源：

- `README.md`：统一工作制度
- `ACTIVE_INDEX.md`：当前项目入口
- `CODEX_ROUTER.md`：未知项目时的路由
- `projects/`：各项目唯一 PROJECT_HOME
- `workflows/`：标准工作流
- `STORAGE_AND_RETENTION.md`：跨平台储存规则
- `REPOSITORY_MAP.md`：本文件

### `AgentCut/Director4/`

`SW-01` 当前新一代代码入口，正式产品名为 **AgentCut Director 4**。

- distribution：`agentcut-director`
- CLI：`agentcut-director`
- schema：`agentcut.director.cutgraph.v1`
- Remotion composition：`AgentCutDirector4`

正常 Director 4 开发只读取：

```text
00_ProjectOS/projects/SW-01_AgentCut.md
→ AgentCut/Director4/AGENTS.md
→ AgentCut/Director4/README.md
→ 任务直接涉及的源码/测试
```

### `AgentCut/` 其余 3.x 内容

正式称为 **AgentCut Classic 3.x**。保留用于：

- 既有生产项目继续运行；
- Director 4 迁移与兼容回归；
- 历史发行验证。

除非任务明确涉及 Classic 3，不递归读取全部 3.x 文档，也不把 3.x package/CLI/schema 与 Director 4 混用。

### `.github/`

GitHub Actions 与仓库自动化。

### `AGENTS.md` / 根 `README.md`

仓库级 AI 规则和人类入口。

## 2. 归档区

### `90_Legacy/`

已明确归档的旧制度、旧分类说明和历史内容。默认不搜索、不修改、不用于新项目决策，除非任务明确要求恢复。

## 3. Frozen Legacy 根目录

以下目录来自早期个人知识库/网页分类系统：

- `其他/`
- `化学/`
- `思想/`
- `教育/`
- `数学/`
- `文学/`
- `术数/`
- `电脑/`
- `templates/`
- 旧网页生成根文件，如 `index.*`、`build.py`、`gen_css.py`、`make_indexorg.py` 等

规则：不作为正常检索入口；不加入新项目资产；未完成依赖审计前不批量移动或删除。

## 4. 根目录准入规则

允许新增内容原则上只能进入：

- `00_ProjectOS/`：制度、PROJECT_HOME、workflow、索引；
- 明确的软件代码目录；
- `.github/`：CI / Actions；
- `90_Legacy/`：明确归档。

禁止新增 `new-project`、`test2`、`final`、`最新版` 一类无 Project ID、无代际身份的顶层目录。

## 5. AI / Codex 默认搜索边界

```text
README.md
→ AGENTS.md
→ 00_ProjectOS/CODEX_ROUTER.md（仅未知项目时）
→ 对应 PROJECT_HOME
→ 已知代码目录
```

SW-01 已知任务必须进一步区分：

```text
Director 4 → AgentCut/Director4/
Classic 3 → AgentCut/ 既有 3.x 文件
```

## 6. 当前逻辑结构

```text
uinwzio/
├─ README.md
├─ AGENTS.md
├─ .github/
├─ 00_ProjectOS/
├─ AgentCut/
│  ├─ Director4/            # AgentCut Director 4 active source
│  └─ [Classic 3.x files]   # mature compatibility line
├─ 90_Legacy/
└─ [Frozen Legacy roots]
```

大型 ZIP、wheel、视频、模型和验证媒体不进入 Git 历史，统一进入 Drive 对应 ACTIVE handoff。
