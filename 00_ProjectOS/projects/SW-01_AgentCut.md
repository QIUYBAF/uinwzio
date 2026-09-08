# SW-01 AgentCut — PROJECT_HOME

**STATUS:** WAITING  
**UPDATED:** 2026-09-09

## 1. 一句话目标
构建 Agent-native 剪辑运行时，让 Codex / ChatGPT Work 以最少上下文定位、启动、编辑和渲染项目，同时保留结构化状态、本地编辑、撤销 / diff / 历史与确定性回退。

## 2. 项目身份 / PROJECT IDENTITY
### 核心体验
Agent 能沿唯一入口迅速发现能力、项目状态和可用后端，执行可审计的非破坏编辑；可选运行时缺失时仍能明确降级，不把环境搜索当成剪辑工作。

### 识别特征
- `agentcut.manifest.json` 是唯一版本真源，`AGENTS.md` 是默认入口。
- `project.json` 或等价 canonical state 是项目真源。
- 语义 / API 操作优先；保留 history、undo、diff 与非破坏资产。
- 先预览 / 本地渲染，再进行昂贵最终渲染。
- Remotion 是可选呈现后端；FFmpeg / Pillow 提供确定性回退。
- 已知 manifest、任务、项目和后端后停止搜索，直接执行。

### 可变化区
- 可增加向后兼容的语义操作、可选后端、诊断与工作流。
- `1.0.x` 只做部署、缺陷、可靠性与兼容性；`1.x.0` 承载兼容新能力；破坏状态 / API 才进入 `2.0.0`。

### 不可无声变化
- 不能从 manifest 之外推断“最新版”，也不能复活旧 0.2 / 3.x 编号。
- 不能把 GUI 点击变成唯一控制面，或因 Remotion 缺失而让项目不可编辑。
- 不能破坏 canonical state、历史 / 撤销 / diff、非破坏资产与确定性回退。
- 状态格式、API 或版本线变化必须记录迁移依据与影响。

## 3. 用户承诺
用户或 Agent 能从下载后的 checkout 直接发现能力、诊断环境、打开 / 创建项目并完成可回退编辑；环境不满足时得到明确的降级路径。

## 4. 当前真源与状态
**Current release line:** AgentCut 1.x  
**LATEST:** 1.0.1 Remaster — Quick Connect  
旧 0.2 / 3.x 为冻结历史；AgentCut Director 4.0 不作为发布基线。

唯一启动路线：
```text
AgentCut/agentcut.manifest.json
→ AgentCut/AGENTS.md
→ python AgentCut/run.py discover
→ python AgentCut/run.py quickstart PROJECT [--create] --task "..."
→ scoped context / preflight / apply
```

1.0.1 已验证：
- full regression 164 / 164；
- 严格 release / version / source 检查；
- Python compile；
- 直接 checkout 的 discover / doctor / quickstart smoke；
- 自动选择 FFmpeg / Pillow，未把仅有 Node / npm 误判为 Remotion。
- 未完成真实 npm + Chromium / Remotion E2E，因此不作相关声明。

## 5. 当前唯一交付物
当前 release 已稳定，转入 WAITING；不开发新功能。待出现合适 npm + Chromium 环境时，只补一次可选 Remotion E2E 证据。

## 6. 文件真源
- **GitHub:** `AgentCut/` + `00_ProjectOS/projects/SW-01_AgentCut.md`；源码、文档、测试、配置、manifest、版本历史只认这里。
- **Drive:** 不再保存当前源码/文档/repo ZIP。仅允许无法重建的大型资产、必要演示媒体、或 GitHub Release 不适合承载的正式二进制交付。
- **Legacy Drive rollback:** `ROLLBACK_AgentCut_v3.3.1` 暂作为历史回退点保留；其中源码 ZIP / handoff / wheel / validation 的冗余关系尚未完全核验，在确认 Git 历史覆盖前不得整包自动删除。
- **Naming:** 新增正式文件必须遵循 `SW-01__<TRACK>__<MODULE>__<ROLE>[__<SPEC>].ext`。
- **Git history:** 代码版本、旧实现和 release 演进。

## 7. HANDOFF
**DONE:** 1.0.1 Remaster 已通过 164 / 164 回归及直接 checkout smoke；ProjectOS v1.3 已明确 AgentCut 软件源码只归 GitHub，Drive 不再作为源码仓库。  
**NEXT:** 仅在具备真实 npm + Chromium 的适当环境中验证一次 Remotion E2E；在此之前保持 WAITING。  
**BLOCKERS:** 当前环境不具备真实 Remotion E2E 条件；Legacy 3.3.1 Drive rollback 是否可进一步瘦身需先核验 Git 历史覆盖。  
**CHANGES:** **WHAT** 明确 GitHub/Drive 路由与 canonical filename；**WHY** 跨 Agent 记忆不互通导致 Drive 混入源码与难以检索；**IMPACT** 后续 AgentCut 源码不再上传 Drive，旧 Drive 内容仅按证据逐步收敛。

## 8. 决策记录
- 2026-09-04 — 1.0.1 Remaster / Quick Connect 成为唯一当前版本。
- 2026-09-07 — 完成身份四项补齐并转 WAITING；可选 Remotion E2E 保留为唯一未来 NEXT。
- 2026-09-09 — ProjectOS v1.3：AgentCut 软件源码/文档/测试只归 GitHub；Drive 仅承载必要大型资产或交付物，新文件强制 Project/Track/Module/Role 命名。
