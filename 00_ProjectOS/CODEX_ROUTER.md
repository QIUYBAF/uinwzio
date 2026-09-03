# CODEX ROUTER — 最小启动路由

**目标：** 让 Codex 用最少必要上下文进入正确项目。这里是执行路由，不是另一份制度手册。

## 0. 核心原则

**已知项目 ID 就直达。未知项目 ID 才路由。**

正常执行不需要依次阅读根 README、完整 ProjectOS README、ACTIVE_INDEX、REPOSITORY_MAP 和多个项目文档。

一旦已经获得：`PROJECT_ID + TASK + acceptance criteria`，默认只读取对应 `PROJECT_HOME`，随后进入任务相关代码/文件。

## 1. 项目直达表

| ID | PROJECT_HOME | 默认代码/工作入口 |
|---|---|---|
| CT-01 | `00_ProjectOS/projects/CT-01_她们仍在旅行.md` | PROJECT_HOME 指定的 Drive / Library 当前路径 |
| CT-02 | `00_ProjectOS/projects/CT-02_结束乐队xMinecraft.md` | PROJECT_HOME 指定的 Drive 当前分集 |
| CT-03 | `00_ProjectOS/projects/CT-03_纯手绘插画.md` | PROJECT_HOME 指定的素材/交付路径 |
| IP-01 | `00_ProjectOS/projects/IP-01_异象研究.md` | PROJECT_HOME 指定路径 |
| OPS-01 | `00_ProjectOS/projects/OPS-01_B站运营发布.md` | ProjectOS + Drive 发布交付 |
| SW-01 | `00_ProjectOS/projects/SW-01_AgentCut.md` | `AgentCut/` |
| SW-02 | `00_ProjectOS/projects/SW-02_RNGtuber.md` | PROJECT_HOME 指定的 GitHub/本地代码路径 |

## 2. 最小启动路径

### A. 提示词 / handoff 已给项目 ID

```text
PROJECT_HOME
→ TASK 指向的具体文件/代码
→ 执行 / 测试
→ SYNC_BACK
```

**不读：** `README.md`、完整 `00_ProjectOS/README.md`、`ACTIVE_INDEX.md`、其他 PROJECT_HOME，除非本轮任务本身需要它们。

### B. 没给项目 ID，但项目名明确

用上面的直达表映射 ID，然后按 A 执行。不要为了确认显而易见的映射做 repo-wide search。

### C. 项目归属确实不清楚

先读 `ACTIVE_INDEX.md`。仍无法确定时才做有限搜索。

### D. 本轮任务是 ProjectOS / 仓库治理 / 跨项目调度

这时才读取完整 `00_ProjectOS/README.md`、`REPOSITORY_MAP.md`、`ACTIVE_INDEX.md` 等控制面文档。

## 3. 搜索升级阶梯

按成本从低到高：

1. **L0 — 已知路径：** 直接读取/修改，不搜索。
2. **L1 — 项目内：** 只搜索对应代码目录或 PROJECT_HOME 已知路径。
3. **L2 — 当前工作区：** 只搜索 `.github/`、`00_ProjectOS/`、明确的软件代码目录。
4. **L3 — 全仓恢复：** 仅当真源缺失、路径矛盾或任务明确要求历史恢复时使用。

`Frozen Legacy` 默认不进入任何正常搜索级别。

## 4. 停止搜索条件

满足以下条件就停止继续“了解情况”，转入执行：

- 已找到唯一 PROJECT_HOME；
- 已知道本轮 TASK；
- 已知道验收标准；
- 已定位待修改/待读取的具体文件；
- 没有阻塞性矛盾。

不要为了获得“更完整的全局理解”继续扫描无关项目。

## 5. 文档按需原则

- workflow：只有任务涉及对应流程时才读。
- 历史版本说明 / release notes：只有回归、兼容、历史行为问题时才读。
- QA 文档：只有交付验收、回归或具体 QA 问题时才读。
- Handoff：只读本轮明确提供或 PROJECT_HOME 明确指向的 handoff。
- 同一会话已经读取且未变化的控制文档，不重复读取。

## 6. AgentCut 特例

Routine SW-01 开发：

```text
SW-01 PROJECT_HOME
→ AgentCut/ 中与 TASK 直接相关的源码/测试
→ 运行最小相关测试
```

`AgentCut/START_HERE_WORK.md`、`AGENT_PROTOCOL.md`、版本 notes、GLT case-study 文档都不是每轮必读材料。

只有任务涉及 agent bootstrap/protocol、特定历史回归、GLT 剪辑经验或 release QA 时才打开对应文档。

## 7. Context 预算目标

常规已知项目任务在读源码前，控制面文档目标为 **1 份 PROJECT_HOME**；路由不明确时最多增加本文件或 `ACTIVE_INDEX`。

这是预算目标而不是僵硬上限：真正存在冲突时允许扩大上下文，但不能把“多读一点保险”当成默认行为。

## 8. 收尾

只回写稳定增量：

`RESULT / CHANGED / TEST / OPEN / NEXT / SYNC_BACK`

不要把执行日志、完整聊天或可从 Git diff 恢复的信息复制进 PROJECT_HOME。
