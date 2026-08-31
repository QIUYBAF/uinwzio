# Project OS v1.0 — 统一工作制度

> 目标：让 ChatGPT / Codex / 本地 / Google Drive / Library / GitHub / B站之间只传递最小必要信息，避免重复搜索、重复解释、记忆断裂和版本混乱。

## 1. 平台唯一职责

- **GitHub = 控制面 + 代码真源**：项目编号、PROJECT_HOME、工作流、决策记录；软件代码与技术版本历史也只认 GitHub。
- **Google Drive = 大文件真源**：原始素材、PSD/Procreate 导出、音视频、模型、可执行文件、最终交付。Drive 根目录不得堆版本。
- **ChatGPT Library = AI 快速工作区**：当前项目卡、短摘要、提示词、参考资料。不是大文件仓库，也不是长期版本库。
- **Codex / 本地 = 执行现场**：允许缓存和中间产物，但任何关键决定必须回写 PROJECT_HOME；本地不是长期真源。
- **B站 = 发布终点 + 数据反馈**：发布文件与数据结论回流到 OPS-01，不作为素材仓库。

## 2. 记忆边界：默认不共享

ChatGPT 云端项目/个人上下文与 Codex 的项目线程、repo 和本地会话默认视为**不同记忆域**。制度上禁止假设“另一个端已经知道我们聊过什么”。

跨端连续性依靠显式外部记忆层：
1. `PROJECT_HOME`：长期项目事实、固定规则与当前状态；
2. `CODEX_HANDOFF`：ChatGPT → Codex 的本轮自包含交接；
3. `SYNC_BACK`：Codex → ChatGPT 的结果增量；
4. Git / Drive：代码与大型文件的实际真源。

第一次把成熟的云端项目转到 Codex 时使用完整 HANDOFF；之后只传 `PROJECT_HOME + 本轮 DELTA + TASK + 验收标准`，不要重复整个聊天历史。

## 3. 项目编号与跨端命名

所有地方使用同一编号：
- CT-*：内容/视频系列
- IP-*：原创 IP / 世界观项目
- SW-*：软件/工具开发
- OPS-*：运营/发布/复盘
- LAB-*：研究/学习/实验

ChatGPT group、Codex 本地目录、Drive 文件夹、GitHub 项目卡都以同一编号开头。编号稳定优先于项目显示名稳定。

## 4. 状态机

项目只有四种状态：`ACTIVE / WAITING / DONE / ARCHIVE`。

- ACTIVE：本周真的会推进；每周重制作主项目最多 3 个。
- WAITING：保留但不主动消耗算力。
- DONE：已完成，等待发布/复盘/收尾。
- ARCHIVE：停止搜索，除非明确恢复。

任何项目不得用版本号代替 ACTIVE，例如禁止 `AgentCut_v3.2.3_ACTIVE`；活动入口固定为 `SW-01_AgentCut_ACTIVE`，版本进入 Git 历史或归档。

## 5. 项目入口文件

每个项目必须有且只有一个权威 `PROJECT_HOME`（目前集中在 `00_ProjectOS/projects/`）。新 ChatGPT 对话、新 Codex 会话、本地接手时先读它。

PROJECT_HOME 控制在约 100 行以内，只记录：
1. 项目目标与观众/用户承诺
2. 固定风格或不可破坏约束
3. 当前状态
4. 当前唯一 ACTIVE / NEXT
5. 标准工作流
6. 完成定义（DoD）
7. 文件真源位置
8. 最新交接摘要
9. 最近关键决定
10. CHANGES

详细聊天史、长日志、旧方案不塞进 PROJECT_HOME，只链接到日志或归档。

## 6. 标准交接协议

跨端状态只认 6 个字段：
- `STATUS` 当前状态
- `DONE` 已完成
- `NEXT` 唯一下一步
- `BLOCKERS` 阻塞
- `FILES` 真源位置
- `CHANGES` 本轮改变了什么固定规则

`CHANGES = none` 时，下一端必须默认维持上一轮已验证的视觉、剪辑、叙事、命名或技术规则。

### ChatGPT → Codex
使用 `CODEX_HANDOFF_TEMPLATE.md`。提示词必须自包含，不依赖 Codex 能看到云端聊天历史。

### Codex → ChatGPT
结束时生成 `RESULT / CHANGED / TEST / OPEN / NEXT / SYNC_BACK`；云端只把真正稳定的新事实回写 PROJECT_HOME，不把整段执行日志复制回来。

## 7. 文件生命周期

`INBOX -> ACTIVE -> DELIVERY -> ARCHIVE`

- 临时文件先进 `99_待整理/99_收件箱`。
- 进入项目后改成语义化文件名。
- 中间文件只保留能继续工作的最小集合。
- 发布后长期保留：源/母版、最终成片、封面、字幕/脚本、PROJECT_HOME、必要授权/素材说明。
- 可再生成缓存、重复导出、旧 Handoff、无意义 AI 中间图可以删除；不确定是否有价值的先归档，不冒险永久删除。

## 8. 搜索顺序（Token 防浪费）

已有项目严格按以下顺序：
1. `ACTIVE_INDEX` 确认 ID；
2. PROJECT_HOME；
3. 已知 GitHub / Drive ACTIVE 路径；
4. 项目对应 Library 文件夹；
5. 只有前四项失败时才做全局恢复搜索。

禁止把 Library 根目录历史散件、Drive 根目录或整个 GitHub repo 当作每轮默认搜索起点。

## 9. AI 默认行为

AI 接手已有项目时：
1. 先找编号和 PROJECT_HOME；
2. 不重新询问已写明的信息；
3. 不因为换模型/线程/平台就重做已验证成功的风格；
4. 先完成最小可靠交付，再升级；
5. 本轮结束前更新 `STATUS/NEXT/CHANGES`；
6. 发现混乱优先修入口、索引和真源，不进行无依据的大规模搬家；
7. 新创意默认进入 INBOX/WAITING，不自动抢占 ACTIVE。

## 10. 系列连续性规则

已经定型的内容系列，把“观众预期得到的影视体验”视为产品接口。除非有明确数据、制作问题或创作理由证明需要改变，否则下一期默认继承：视觉语言、角色设定、镜头/剪辑语法、节奏区间、字幕/声音体系与核心叙事气质。

改变这些规则必须写入 `CHANGES`，说明原因和预期收益；实验优先局部 A/B，而不是整期突然换体系。

## 11. 每周维护

并入 B站周决策会：
- 检查重制作主项目是否超过 3 个；
- 每个 ACTIVE 是否有唯一 NEXT；
- Drive/GitHub 是否出现多个“最新版”；
- DONE/旧版本是否需要归档；
- 是否存在重复存储或无意义中间产物；
- 系列风格是否发生未经记录的漂移；
- 只提出 1 条本周最值得执行的制度维护动作。

## 12. 当前物理结构

### Library
`00_工作台 / 10_内容项目 / 20_软件项目 / 30_运营 / 40_学习研究 / 90_归档 / 99_收件箱`

Library 根目录的历史 UUID/旧生成散件按 Legacy 处理，不参与正常检索；部分旧索引因底层文件已不可用，无法迁移时直接忽略，不重复尝试。

### Drive
`00_项目管理 / 01_进行中 / 02_发布交付 / 03_原始素材 / 90_归档 / 99_待整理`

### GitHub
根入口 `README.md` / `AGENTS.md` → `00_ProjectOS/` → 项目 PROJECT_HOME / workflows；历史根目录文件默认 Legacy，除非现有构建明确引用。
