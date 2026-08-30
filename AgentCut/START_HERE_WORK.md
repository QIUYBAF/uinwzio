# START HERE — AgentCut v0.1.2 Work 接管总说明

> 这是聊天模式最后一轮交付的主入口。Work 模式请先完整阅读本文件，再动代码。

## 0. 一句话定义

AgentCut 不是“简化版 Premiere”，而是一个 **AI-native video editing runtime**：

```text
创作意图
  ↓
GPT / Agent
  ↓
语义操作（scene / camera / transition / effect / audio / caption）
  ↓
canonical project.json
  ↓
确定性 renderer
  ↓
preview / QA / frame inspection / contact sheet
  ↓
Agent 修正
```

设计目标不是让 AI 学会点人类软件，而是让“剪辑”本身成为 Agent 可读取、调用、验证、回滚的一组原生能力。

## 当前 GitHub 镜像说明

本目录镜像当前 AgentCut v0.2.0-alpha.5。大体积视频/完整 Handoff ZIP 仍保存在 Google Drive 的 `AgentCut_v0.2.0-alpha.5_Handoff`；跨对话优先从本目录读取 README、alpha.5 notes、library catalog 与 validation summary，再按需要读取/恢复完整源码。

## 绝对不要破坏的架构不变量

1. `project.json` 是 canonical state。
2. Agent-facing API 是 semantic API。
3. Agent 不直接写 filter graph。
4. source assets 非破坏性。
5. random effects 有 seed。
6. errors machine-readable。
7. mutation versioned + undo/redo/diff。
8. batch atomic。
9. Agent 可随时重新查询 state。
10. preview / final 分离。
11. QA 报告问题，不擅自修改艺术意图。
12. GUI 不是核心状态层。
13. capability 声明必须与 renderer 实际能力一致。
14. cache 必须基于真实依赖，而不是“看起来差不多”。

## 推荐阅读顺序

1. `README.md`
2. `V0.2_ALPHA5_NOTES.md`
3. `LIBRARY_CATALOG.md`
4. `VALIDATION_SUMMARY_A5.md`
5. Google Drive 中的完整 Handoff（需要完整源码/测试/范片时）

## 最终产品判断标准

每加一个功能先问：

> “这个能力是否让 Agent 更清楚、更确定、更低成本地完成剪辑？”

如果一个能力让 Agent 能：

```text
读状态 → 提交意图 → 确定执行 → 验证结果 → 局部修正 → 回滚
```

那就是正确方向。
