# File Naming & Routing — 文件归属与跨平台路由标准

**VERSION:** ProjectOS v1.3  
**UPDATED:** 2026-09-09

## 1. 原则

文件在上传、同步或交付前，必须仅凭文件名就能回答：
1. 属于哪个 Project ID；
2. 属于项目里的哪个业务分支 / 期数 / 子项目；
3. 属于哪个模块；
4. 这个文件承担什么角色。

目录结构是第二层索引，**文件名是第一层索引**。不得依赖某个 ChatGPT/Codex 对话“记得这个文件是什么”。

## 2. Canonical filename

默认格式：

`<PROJECT_ID>__<TRACK>__<MODULE>__<ROLE>[__<SPEC>].<ext>`

使用双下划线分隔语义字段，字段内部使用短横线 `-`。

### PROJECT_ID
稳定项目编号，例如：
- `CT-01` 她们仍在旅行
- `CT-02` 结束乐队×Minecraft
- `CT-03` 纯手绘 / 插画
- `SW-01` AgentCut
- `SW-02` RNGtuber
- `OPS-01` B站运营

### TRACK — 业务分支
这里的 TRACK **不是 Git branch**。它表示项目内可稳定识别的业务分支、期数或子项目，例如：
- `EP09`
- `QFT-PROMO`
- `QFT-AVATAR`
- `CHINA-S11`
- `POLITICAL-BENCHMARK`
- `CORE`

禁止使用 `misc / temp / new / latest` 作为 TRACK。

### MODULE — 模块
优先使用有限词表：
- `VIDEO`
- `ART`
- `AUDIO`
- `SCRIPT`
- `SUBTITLE`
- `COVER`
- `MODEL`
- `DATA`
- `BUILD`
- `DOC`
- `SOURCE`

### ROLE — 文件角色
优先使用有限词表：
- `RAW`：不可替代/尚未加工的原始输入
- `SOURCE`：可编辑源资产
- `CURRENT`：当前工作态文件
- `MASTER`：最高质量母版
- `DELIVERY`：准备发布/交付的文件
- `RELEASE`：软件正式发布包
- `PREVIEW`：低价值预览，可清理
- `ARCHIVE`：明确保留的历史代表物

不得使用 `final2 / new-final / latest-new / 最终最终版`。

### SPEC — 可选规格
只放机器或交付真正需要的规格，例如：
- `1080p30`
- `4K60`
- `win-x64`
- `zh-CN`
- `transparent`

日期只有在确有业务意义时才放最后，不得用日期代替版本控制。

## 3. 示例

- `SW-02__QFT-PROMO__VIDEO__MASTER__1080p30.mp4`
- `SW-02__QFT-AVATAR__ART__SOURCE.procreate`
- `CT-02__EP09__VIDEO__DELIVERY__1080p30.mp4`
- `CT-02__EP09__SUBTITLE__DELIVERY__zh-CN.srt`
- `CT-01__CHINA-S11__COVER__DELIVERY.png`
- `CT-03__QFT-AVATAR__ART__RAW__IMG5504-2.jpeg`
- `SW-01__CORE__BUILD__RELEASE__win-x64.zip`

旧的 `RNGTuber_QFT_V3_1080p30.mp4` 在下一次整理时应收敛为类似：
`SW-02__QFT-PROMO__VIDEO__MASTER__1080p30.mp4`。

## 4. 上传前命名闸门

任何 ChatGPT / Codex / 本地 Agent 在把文件上传到 Drive、GitHub Release 或其他正式位置之前必须：
1. 确认 PROJECT_ID；
2. 确认 TRACK；
3. 确认 MODULE；
4. 确认 ROLE；
5. 先在本地改成 canonical filename；
6. 再按平台路由规则上传；
7. 在 SYNC_BACK 中回报最终文件名与实际位置。

如果归属无法确定：
- 不得猜测；
- 不得直接塞入项目正式目录；
- 使用 `99_待整理`，并命名为 `UNASSIGNED__<简短描述>__<原文件名>`；
- 标记 `NEEDS-HUMAN`。

## 5. 平台路由：什么应该放哪里

### GitHub — 控制面、源码与文本真源
应放：
- 源码、脚本、配置、测试；
- README / ProjectOS / PROJECT_HOME / manifest / changelog；
- 小型且属于代码运行必要条件的文本或轻量资产；
- Git history / tag；
- 软件 release metadata；
- 体积合理时的软件正式 Release 包优先放 GitHub Release。

不应长期放：
- 视频母版、PSD/Procreate、Blender 大工程、模型大文件、录屏、音频母带；
- 大量构建目录、依赖、缓存。

### Google Drive — 大型媒体与最终交付真源
应放：
- 不可重建原始媒体；
- Procreate/PSD/Blender 等大型可编辑创作工程；
- 视频/音频/模型母版；
- 封面、字幕交付件；
- 最终发布视频；
- GitHub Release 不适合承载的大型二进制交付。

**不得把 Drive 当源码仓库。** 以下内容若 GitHub 已有 canonical 真源，应从 Drive 收敛：
- repo/source 完整 ZIP 快照；
- `.py/.js/.ts` 等源码副本；
- README / changelog / 技术文档重复副本；
- Git 历史已经覆盖的 AgentCut 等软件旧版本源码目录；
- 可从 GitHub checkout + build 重新生成的构建缓存。

### Codex / 本地
只作为执行现场。任何关键产物必须在会话结束前按本标准命名并同步到 canonical 平台；本地不能成为唯一真源。

## 6. 软件项目特别规则

对 `SW-*`：
- **源码、文本规则、版本历史永远以 GitHub 为准**；
- Drive 只允许大型不可重建资产、必要演示媒体、以及确有交付需要的大型二进制；
- 软件源代码 ZIP 若只是 Git 仓库快照，默认删除；
- 正式安装包优先 GitHub Release；只有体积/交付限制明确需要时才在 Drive 留一份 CURRENT RELEASE。

因此 `SW-01 AgentCut` 的代码、文档、测试、版本历史不应再由 Drive 承担；Drive 中旧 AgentCut 源码/工程快照在确认 GitHub 已覆盖后应清理。

## 7. 内容项目特别规则

对 `CT-* / IP-*`：
- Drive 是大型创作资产和最终视频真源；
- GitHub 可保存脚本、剪辑程序、Remotion/FFmpeg 代码、PROJECT_HOME 和可重建逻辑；
- 如果一个视频制作同时涉及系列与软件工具，文件以**内容项目作为 PRIMARY_PROJECT**，工具项目只在 manifest / SYNC_BACK 中写 RELATED_PROJECT；不要因为“用 AgentCut 剪了”就把视频归到 SW-01。

例如 RNGtuber 绘制宣传视频若本质是频道内容，可按实际项目归属选择 `CT-03` 或明确的内容 Project ID；`SW-02` 只承载 RNGtuber 软件/角色系统本身。归属必须在 PROJECT_HOME 中固定，避免一份素材同时散落多个项目。

## 8. 每日整理器的行为

每日整理不得只根据“最近修改”“看起来像最终版”推断归属。

排序优先级：
1. canonical filename；
2. PROJECT_HOME / DELIVERY_MANIFEST；
3. 文件父目录；
4. SYNC_BACK；
5. 最后才使用时间戳和内容猜测。

发现旧文件没有 canonical filename 时：
- 能可靠判断归属则重命名并移动到正确位置；
- 无法可靠判断则放 `99_待整理` + `NEEDS-HUMAN`；
- 不得因整理器自己的记忆缺失而把文件误归档或删除。
