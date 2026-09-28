# SW-02 RNGtuber — PROJECT_HOME

**STATUS:** WAITING  
**UPDATED:** 2026-09-28

## 1. 一句话目标
做一个 Windows 上可直接开播的轻量 RNGtuber/PNGTuber：角色自然、响应稳定、资产可维护。

## 2. 项目身份 / PROJECT IDENTITY
### 核心体验
打开程序后，角色稳定存在于桌面；呼吸、说话、眨眼、表情与输入反馈自然，用户无需反复校准。

### 识别特征
- 直播可用优先：透明窗、置顶/穿透、麦克风、快捷键、配置保存和 EXE 交付。
- 模块资产共享统一画布/坐标，运行时无拼贴、残影与漂移。
- 低幅自然运动；嘴型、眨眼、表情切换连续。
- approved master 为「椋梓怅惀」，账号/作者名为「薇纷芳橙」。

### 可变化区
状态机、表情、服装、输入 Overlay 与动态参数可迭代；未来可加追踪/弹幕/变声，但不阻塞开播链路。

### 不可无声变化
不得退回手工 offset、牺牲稳定状态、覆盖未经 QA 的 master，或只有开发环境可跑却标完成。

## 3. 用户承诺
稳定打开、开麦、切状态并直播；表现自然可预测。

## 4. 不可破坏约束
真透明 RGBA、统一坐标、嘴型 hysteresis、绝对状态计算、正确 alpha；EXE/ZIP 启动验证属于 DoD。

## 5. 当前状态
角色母稿与宣传片已完成；真实 Windows 彩排仍未回写。本周不开发新直播工具，不扩服装/表情。

## 6. 标准工作流
锁 master → 资产 QA → 最小 runtime → 麦克风/眨眼 → 快捷键/窗口 → Windows 构建与 smoke test。

## 7. 完成定义 DoD
无错位/黑边/残影；嘴型眨眼稳定；快捷键/窗口有效；Windows EXE 可直接启动；真源明确。

## 8. 文件真源
- **GitHub:** 代码、协议、QA/构建脚本与本文件
- **Drive WAITING:** `90_归档/SW-02_RNGtuber_WAITING`
- **Library:** `20_软件项目/SW-02_RNGtuber`

## 9. HANDOFF
**DONE:** 「椋梓怅惀」母稿和绘制宣传片已完成并发布；宣传片数据不能替代软件运行验收。  
**NEXT:** 用户下次在真实 Windows 环境运行时，完成一次 10 分钟技术彩排并记录麦克风、眨眼、快捷键、透明窗与录屏。  
**BLOCKERS:** 本轮没有真实 Windows 彩排证据。  
**CHANGES:** **WHAT** 转 WAITING；**WHY** 本周主交付为 CT-05 且直播不得新增工具开发；**EVIDENCE** 未收到 Windows 彩排回写；**IMPACT** 保留唯一 master 与全部规则，只等待人工运行证据。
