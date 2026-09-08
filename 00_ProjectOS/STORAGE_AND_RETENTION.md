# Storage & Retention — 跨平台储存与主动断舍离规则

**UPDATED:** 2026-09-09  
**VERSION:** ProjectOS v1.3  
**SCOPE:** ChatGPT Library / Google Drive / GitHub / Codex 本地

## 1. 总原则：保留来路，不保留全部施工废料

ProjectOS 保存的是能够支撑当前运行、可靠回退、关键复现和经验传承的**最小历史充分集**，不是每一代完整副本。

长期保留：
1. 当前可运行源码与唯一 CURRENT RELEASE；
2. 必要时一个最近稳定回退点；
3. 每个具有独立创作或技术意义的大版本的一份代表性最终成品；
4. 精炼的关键开发路径、决策、迁移说明与经验；
5. 无法重建的原始创作资产、授权与必要校验信息。

确认不再承担上述作用后直接删除：
- 旧代完整源码副本、已由 Git 历史覆盖的平级版本目录；
- 旧安装包、旧构建、重复 ZIP、过期 preview/checkpoint/handoff；
- 失败测试输出、缓存、依赖目录、虚拟环境、可再生成中间文件；
- 重复导出、无复用价值的 REJECTED 候选及过时校验清单。

归档不是默认终点。只有仍有明确历史、展示、法律或复现价值的内容才归档；“也许以后有用”不足以成为长期保留理由。

## 2. 唯一真源

| 平台 | 唯一职责 | 应长期保留 | 应主动删除/移出 |
|---|---|---|---|
| GitHub | ProjectOS、PROJECT_HOME、当前代码、文本规则、必要 Git 历史 | 源码、配置、测试、轻量文档、tags/releases | 成片、PSD/Procreate/Blender 大工程、录屏、模型、依赖与构建缓存 |
| Google Drive | 大型媒体与最终交付真源 | 不可重建原始素材、关键可编辑创作工程、母版、最终成品、封面/字幕交付、大型必要发布包 | repo/source ZIP、源码/README 重复副本、旧构建、重复导出、过期 handoff、无引用中间文件 |
| ChatGPT Library | AI 快速入口 | 项目入口、短摘要、提示词、少量高价值参考 | 大型媒体、重复附件、长期版本链、根目录散件 |
| Codex / 本地 | 执行现场 | 当前工作副本与必要短期缓存 | 已完成任务的临时目录、依赖、构建输出、未同步副本 |

**软件项目特别约束：源码、文档、测试、配置、版本历史只认 GitHub。** Drive 不承担 AgentCut 等软件项目的源码仓库职责。

## 3. 生命周期

`INBOX -> ACTIVE -> DELIVERY -> KEEP / DELETE`

- INBOX/待整理不是永久仓库；每日处理最近新增内容。
- 每个项目只有一个无版本号 ACTIVE 和一个 CURRENT RELEASE。
- DELIVERY 完成后，从工作目录提取最小历史充分集，其余删除。
- 历史大版本只保留代表性成品 + 关键开发路径/经验，不保留完整工作目录。
- REJECTED 候选若无复用价值，清理时删除，不无限归档。
- 同名不等于重复；删除前核对引用、身份、哈希或可重建性。
- `UNSYNCED` 项目不得自动进入 ARCHIVE/DELETE。

## 4. 自动删除权限与保护线

在证据充分且无 ACTIVE 引用时，维护任务可直接移动、归档和永久删除，无需逐项确认。

不得自动删除：
- 唯一且无法重建的原始创作资产；
- 唯一最终成品；
- 当前 ACTIVE 或 CURRENT RELEASE 所依赖的文件；
- 当前可运行源码；
- 用途、归属或引用关系无法可靠判断的文件；
- 处于 UNSYNCED 的关键文件；
- 账号、隐私、法律、授权或财务材料。

不确定项标记 `NEEDS-HUMAN`，不得用“先删再说”代替判断。GitHub 不自动重写共享历史、不删除默认分支或当前 Release tag。

## 5. 软件版本保留

每个软件项目的长期存储最多包含：
- GitHub 上的当前可运行源码；
- 当前正式发布包（优先 GitHub Release）；
- 必要时一个最近稳定回退点；
- 关键里程碑 tag/changelog/迁移说明；
- 无法重建的必要测试 fixture 或大型资产。

Git 历史已经记录的源码变化，不再通过 `v1/v2/v3/final/latest` 完整目录或 ZIP 在 Drive 重复保存。

对于 AgentCut 等 `SW-*`：
- `src / tests / docs / README / py/js/ts` 等代码和文本真源必须回到 GitHub；
- Drive 中若存在完整 repo ZIP、旧源码树或 GitHub 已覆盖的文档副本，确认无唯一资产后删除；
- 构建出的安装包优先 GitHub Release；仅在体积、交付或平台限制明确需要时才在 Drive 留一份 canonical CURRENT RELEASE。

## 6. 内容项目保留

长期保留：
- 最终成片/母版；
- 必要源工程或可继续修改的最小源集合；
- 封面、字幕/脚本、授权与关键素材说明；
- 经过验证的制作经验。

草稿、失败生成、重复配音/导出、低清预览、可再生成代理文件和未采用方案，在最终交付确认后删除。

内容项目使用了 AgentCut / Remotion / FFmpeg 等工具，并不改变内容文件的 PRIMARY_PROJECT；视频归内容项目，工具只记 RELATED_PROJECT。

## 7. 命名与上传前闸门

详细规范以 `FILE_NAMING_AND_ROUTING.md` 为准。

正式文件默认命名：
`<PROJECT_ID>__<TRACK>__<MODULE>__<ROLE>[__<SPEC>].<ext>`

其中：
- PROJECT_ID：项目编号；
- TRACK：业务分支/期数/子项目，不是 Git branch；
- MODULE：VIDEO / ART / AUDIO / SCRIPT / SUBTITLE / COVER / MODEL / DATA / BUILD / DOC / SOURCE；
- ROLE：RAW / SOURCE / CURRENT / MASTER / DELIVERY / RELEASE / PREVIEW / ARCHIVE。

例如：
- `SW-02__QFT-PROMO__VIDEO__MASTER__1080p30.mp4`
- `CT-02__EP09__VIDEO__DELIVERY__1080p30.mp4`
- `SW-01__CORE__BUILD__RELEASE__win-x64.zip`

禁止 `final2`、`new final`、`latest-new` 等无法判断关系的名称。

### 上传前必须完成
1. 确认 Project ID；
2. 确认 TRACK；
3. 确认 MODULE；
4. 确认 ROLE；
5. 在本地先改成 canonical filename；
6. 判断应进入 GitHub 还是 Drive；
7. 上传后在 SYNC_BACK 回报最终文件名与位置。

归属不明时不得猜测，使用 `UNASSIGNED__<描述>__<原文件名>` 进入 `99_待整理`，并标 `NEEDS-HUMAN`。

## 8. 每日维护

每日执行增量清理：
1. 检查最近 7 天新增/修改内容；
2. 检查新文件是否符合 canonical filename；
3. 优先使用 `PROJECT_ID + TRACK + MODULE + ROLE` 判断归属；
4. 清空或收敛根目录散件、INBOX/待整理；
5. 删除已确认冗余的构建、缓存、重复导出与过期 handoff；
6. 检查唯一 ACTIVE/CURRENT RELEASE；
7. 检查 GitHub 已覆盖的软件源码/文档是否仍冗余留在 Drive；
8. 对 UNSYNCED/NEEDS-HUMAN 不做破坏性整理；
9. 只在有实际证据时更新规则。

每日整理器不得把自己的聊天记忆当成项目事实来源。判断优先级：
`canonical filename -> PROJECT_HOME/manifest -> 父目录 -> SYNC_BACK -> 时间戳/内容猜测`。

每逢周日执行全量结构检查。输出仅包括：
`TODAY_CLEANED / SPACE_OR_NOISE_REDUCED / RULE_UPDATED / NEEDS_HUMAN`。
无实质变化时只报告 `healthy`，不为维护制造新文件。

## 9. GitHub 防膨胀

- `.gitignore` 阻止媒体、ZIP、EXE、模型权重、依赖和构建目录进入普通提交。
- HEAD 不保存每个小版本的独立说明或源码副本。
- 历史大对象瘦身必须先核验 Drive 真源和回退点；不得在日常清理中 force-push。
- Frozen Legacy 完成依赖审计后可主动删除或收敛，不因“历史”身份永久保留。

## 10. 规则变更记录

### 2026-09-09 — 上传前命名与跨平台路由强化
`WHAT`：正式文件必须在上传前写入 Project ID / TRACK / MODULE / ROLE；Drive 明确禁止承担软件源码仓库职责。  
`WHY`：ChatGPT、Codex 和每日整理对话处于不同记忆域；仅靠目录与会话记忆会造成完成项目误归类、难检索和跨平台重复存储。  
`EVIDENCE`：RNGtuber 绘制宣传成片能按“视频 + 时间”找到，但项目目录检索困难；AgentCut 等 GitHub 应有内容仍残留 Drive。  
`IMPACT`：以后即使文件临时落错目录，也可仅凭文件名恢复归属；软件项目的代码/文本重复项将从 Drive 收敛回 GitHub。

### 2026-09-05 — 主动断舍离授权
`WHAT`：由保守归档优先改为主动删除无长期价值内容。  
`WHY`：工程规模已超过人工逐项审阅能力；冗余版本显著增加检索与 Codex usage。  
`EVIDENCE`：用户明确授权自动删除，并要求软件旧代只保留成品、关键开发路径与经验。  
`IMPACT`：每日维护可直接清除已确认的可重建/重复/过期内容；唯一资产、当前版本和最终成品继续受保护。

### 2026-09-05 — AgentCut CURRENT 身份纠偏
`WHAT`：将根入口中残留的 AgentCut “3.3.1 当前基线”更正为唯一 CURRENT **1.0.1 Remaster**。  
`WHY`：根 README 与 `AgentCut/README.md`、`SW-01_AgentCut.md` 相互矛盾，会诱发错误路由与重复检索。  
`EVIDENCE`：`AgentCut/agentcut.manifest.json` 与两个当前入口均指向 1.0.1；当前轻量源码和 164 项测试已在 GitHub。  
`IMPACT`：Drive 的 3.3.1 只保留一份回退点；0.2/3.x 与 Director 4.x 不再作为启动或发布候选。
