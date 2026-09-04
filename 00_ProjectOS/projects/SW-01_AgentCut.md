# SW-01 AgentCut — PROJECT_HOME

**STATUS:** ACTIVE  
**UPDATED:** 2026-09-05

## 1. 一句话目标
做一个真正为 AI/Agent 操作设计、而且能低摩擦部署的剪辑系统：可控、可追踪、可局部修改、可复现，并且最终剪出来的片子本身要自然好看。

## 2. 项目身份 / PROJECT IDENTITY
### 核心体验
AgentCut 不是“传统 GUI 剪辑器外面套一层聊天框”，而是 Agent-native 编辑系统。AI 应能读懂项目状态、执行结构化操作、比较差异、撤销局部修改并可靠导出，而无需靠屏幕坐标猜测。

### 识别特征
- **结构化 Agent API 优先**：AI 操作时间线、素材、特效、字幕和导出时优先调用稳定接口，而不是模拟人点 GUI。
- **单一 canonical state**：`project.json`/等价结构是项目状态真源；操作可序列化、可 diff、可恢复。
- **局部可修改**：一处字幕、镜头、转场或参数变化不应迫使整条时间线重建。
- **非破坏编辑**：源素材不被直接改写；历史、undo、diff、确定性 seed 与操作日志允许重放和追责。
- **Preview / Final 分离**：低成本预览用于判断，高质量最终渲染用于交付；不能每次调整都跑最终导出。
- **影视语言优先于效果数量**：推拉、关键帧、转场、字幕、UI、BGM、音效应共同服务影片；效果看起来“被故意加上去”本身就是失败信号。
- **部署也是产品体验**：如果 AgentCut + Remotion 需要用户手工拼 Python、FFmpeg、Node/npm、Chromium 和 PATH，视为产品缺陷，不视为“用户自己配环境”。

### 可变化区
- GUI、素材库、特效数量、模型接入方式、渲染后端都可以继续升级。
- 可以吸收 Remotion、AgentCut 外部版本或其他开源工具的长处，但必须转换成 AgentCut 的结构化能力，而不是拼贴。

### 不可无声变化
- 从 API-first 退化为 GUI 自动点击优先。
- 丢失 `undo/diff/history` 或让操作不可追踪。
- 为新功能破坏已有导出、局部修改、时间线连续性。
- 重新引入已验证会产生错误观感的实现而没有证据与测试。
- 产品架构重大变化必须写明“改了什么、为什么改、迁移代价”。

## 3. 用户承诺
AI 应能在不同会话继续同一个剪辑项目，而不是每次重新做一遍；用户应能知道 AI 改了什么，并得到可以实际发布的成片，而不只是技术 demo。部署应接近“安装后即可工作”，而不是先进行一轮环境工程。

## 4. 不可破坏约束
- canonical state、deterministic seed、non-destructive assets、machine-readable errors、history/undo/diff、atomic batch operations 保持为核心能力。
- 镜头运动连续自然；推拉/关键帧不得机械突变。
- 转场保证帧连续，不制造缺帧/跳帧。
- 新视觉效果先确认是否提高影片体验，再决定是否进入默认库。
- 已验证稳定部分默认保护；修一个问题不允许无依据重做整套系统。
- Remotion 是可选的高质量呈现后端，不得成为“没有手工配环境就完全不能工作的单点故障”。

## 5. 当前版本与唯一交付物

**Current usable baseline: AgentCut 3.3.1.**

已验证：156 tests / 0 failures、`agentcut doctor` pass、Remotion Bridge v2 完整性与三场景代理 E2E。  
未充分验证：fresh npm install + Chromium/Remotion 真实渲染部署路径。

因此当前唯一交付物不是继续堆功能，而是：

> **AgentCut 3.4 — deployment-first iteration**：把 AgentCut + Remotion 从“环境工程”变成“一次 bootstrap + doctor/fix + backend auto”的生产工作流。

`AgentCut_Director_4.0.0_Handoff` 目前为空占位，不是可用最新版，不得覆盖 3.3.1 的 current 标记。

## 6. 标准工作流
1. 定义一个具体痛点与可观察验收条件。
2. 读取当前 canonical state / 代码 / 测试，不重建已有能力。
3. Codex 实现最小结构化增量，优先 API 与状态模型。
4. 单元/集成测试后，用 10–30 秒真实素材做 preview。
5. 检查：时间线连续、局部修改、undo/diff、转场、字幕、音画、性能。
6. 涉及部署时必须在 fresh environment 做真实 E2E，不允许只验证 bundle/manifest。
7. 通过后再 final render；代码提交 Git，大交付进入 Drive ACTIVE。
8. 旧 handoff/构建归档；更新 RESULT / TEST / NEXT / CHANGES。

## 7. 3.4 部署验收条件
- fresh Windows / Linux 不需要手工编辑 `package.json`、寻找 Chromium、修改多处 PATH。
- Node / Remotion / Chromium 版本固定且可复现。
- 存在一个顶层 bootstrap 命令（如 `agentcut setup --remotion` 或等价实现）。
- `agentcut doctor --fix` 或等价能力能自动修复普通缺失项；无法修复时返回单一、可执行、machine-readable 错误。
- `agentcut render PROJECT --backend auto` 能优先选择健康的 Remotion，失败时确定性回退 FFmpeg/Pillow，无需用户重建 bridge。
- release validation 必须包含真实 npm install + Chromium/Remotion render。
- 用一个真实短项目完成从 fresh environment 到代理/最终渲染的闭环。
- 当前 3.3.1 source/wheel/version manifest 同步到明确的 GitHub current source 入口；不得再靠旧 3.2.3 文档猜版本。

## 8. 完成定义 DoD
代码可追踪；自动测试通过；至少一个真实短片验证通过；可启动/可导出；没有回归已有核心能力；Drive 只有一个 ACTIVE；NEXT 唯一。对 3.4 额外要求：fresh-environment Remotion E2E 通过且不依赖手工环境拼装。

## 9. 文件真源
- **GitHub:** ProjectOS、当前入口文档、工具元数据；3.3.1 完整源码仍需同步回来，这是当前 P0 的一部分。
- **Drive:** `01_进行中/SW-01_AgentCut_ACTIVE`，当前 3.3.1 wheel/source/handoff、大型资源/交付。
- **Local/Codex:** 构建与运行现场，不是长期唯一真源。

## 10. HANDOFF
**DONE:** 3.3.1 已成为明确 current usable baseline；已确认 GitHub 旧 README/`agent_tools.json` 仍写 3.2.3，且 AgentCut 目录包含大量逐版历史文档；Drive 中 3.3.1 有真实 wheel/source/handoff，而 Director 4.0.0 只是空占位。  
**NEXT:** 实现并实测 AgentCut 3.4 的 one-command Remotion bootstrap / doctor-fix / backend-auto，并把当前源码同步回 GitHub。  
**BLOCKERS:** GitHub 当前缺少 3.3.1 完整源码；Remotion 路径跨 Python + FFmpeg + Node/npm + Chromium，部署面过宽。  
**CHANGES:** 2026-09-05 将“部署简单”提升为产品身份约束；当前 HEAD 只保留 current + 长期文档 + 压缩里程碑历史，逐版 Alpha/patch 文档退出默认工作集。

## 11. 决策记录
- 2026-09-01 — AgentCut 的竞争力定义为“AI可编程编辑状态 + 实际好看的剪辑结果”，不是单纯更多特效或更复杂 GUI。
- 2026-09-05 — 3.3.1 定义为 current usable baseline；Director 4.0.0 空占位不得冒充最新版。
- 2026-09-05 — 部署摩擦视为 P0 产品 bug；下一版本先降低环境要求，再继续大规模功能扩张。
- 2026-09-05 — GitHub 当前目录不再保存每个小版本说明；Git history 负责考古，HEAD 只服务当前开发。
