# SW-01 AgentCut — PROJECT_HOME

**STATUS:** ACTIVE  
**UPDATED:** 2026-09-03

## 1. 项目族与当前代际

SW-01 是 AgentCut 项目族。为避免 3.x 与 4.x 在包名、CLI、状态格式和交接材料中混淆，从 2026-09-03 起固定使用以下名称：

- **AgentCut Classic 3.x**：现有成熟生产线，Python 包与 CLI 均为 `agentcut`；用于继续维护既有工程。
- **AgentCut Director 4.x**：新一代 Agent-native 语义导演控制面，Python 包与 CLI 均为 `agentcut-director`；代码入口为 `AgentCut/Director4/`。

禁止只写“AgentCut 最新版”而不注明 Classic 或 Director。

## 2. 一句话目标

让 AI/Codex 通过紧凑、可追踪、可局部修改的语义状态控制视频工程，再由 Remotion 承担帧级表现与最终渲染，从而减少重复读代码、重建状态、全片重渲和错误恢复成本。

## 3. 固定产品身份

### AgentCut Director 4

- canonical state：`agentcut.director.cutgraph.v1`
- distribution：`agentcut-director`
- CLI：`agentcut-director`
- Remotion composition：`AgentCutDirector4`
- source：`AgentCut/Director4/`

### 不可破坏约束

- CutGraph 是唯一编辑真源；生成的 TSX/manifest 不能成为第二套时间线。
- mutations 必须 atomic、versioned、hash-guarded，并返回 receipt、inverse operations 与 impact plan。
- 源素材非破坏；导出前检查已登记 SHA-256。
- Preview / Final 分离；局部修改默认只渲染受影响 span/domain。
- Classic 3 迁移必须写入新文件，不覆盖旧工程。
- 结构载荷或帧数缩减不能冒充 Codex token/credit 实测。

## 4. 当前交付

**AgentCut Director 4.0.0**：完成 CutGraph v1、事务/preflight/undo、语义 diff、依赖影响分析、Classic 3 非破坏迁移、Remotion Bridge v1、严格 bundle 验证、CLI/doctor、效率结构审计与发行测试。

Git 工作分支：`release/agentcut-director-4.0.0`。

## 5. 标准工作流

1. 读取本 PROJECT_HOME 与 `AgentCut/Director4/AGENTS.md`。
2. 获取当前 project hash 和任务相关 CutGraph 子集。
3. preflight semantic operations。
4. apply 时提交 `expected_project_hash`。
5. 按 impact plan 只验证/渲染受影响范围。
6. 通过 QA 后再执行完整 Remotion final render。
7. 代码、测试、文档进入 GitHub；wheel、Source ZIP、Handoff、demo 与大型证据进入 Drive ACTIVE。

## 6. 完成定义 DoD

- 源码与版本身份一致；
- 自动测试通过；
- wheel 干净安装与 doctor 通过；
- Remotion bundle 导出和 hash verification 通过；
- 至少一个真实或确定性 demo 工程通过；
- Drive 只有一个当前 Director 4 ACTIVE handoff；
- NEXT 唯一且可观察。

## 7. 文件真源

- **GitHub:** `AgentCut/Director4/`、本 PROJECT_HOME、版本历史和 PR。
- **Drive:** `01_进行中/SW-01_AgentCut_ACTIVE/AgentCut_Director_4.0.0_Handoff`，保存二进制发行物和验证证据。
- **Classic 3:** 原 `AgentCut/` 3.x 文档/发行材料，除迁移与回归任务外不与 Director 4 混用。

## 8. HANDOFF

**DONE:** Director 4.0.0 的独立命名、CutGraph、事务、影响分析、Remotion Bridge、迁移、CLI、测试、wheel 与发行包已形成。  
**NEXT:** 用同一真实视频项目完成 Pure Remotion 与 Director→Remotion 的 warm edit / cross-session / recovery A/B，每格至少三次并记录真实 Codex usage。  
**BLOCKERS:** 当前环境未安装 npm 依赖并执行 Chromium 最终渲染；这不影响 bridge 完整性验证，但正式成片前必须补做。  
**CHANGES:** 2026-09-03 将 3.x 正式命名为 AgentCut Classic，将 4.x 正式命名为 AgentCut Director，禁止模糊代际称呼。

## 9. 决策记录

- 2026-09-03 — 4.x 不覆盖或重命名 3.x，而以独立包、CLI、schema、目录和 Remotion composition 并行演进。
- 2026-09-03 — AgentCut 的竞争力继续定义为“紧凑的 Agent 状态控制 + 实际可发布的 Remotion 表现”，不重复建设通用渲染器。
