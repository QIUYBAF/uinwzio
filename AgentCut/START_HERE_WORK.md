# START HERE — AgentCut v0.2.0-alpha.7

> 跨对话 / Work / Codex 接管 AgentCut 时先读本文件。

## 一句话定义

AgentCut 不是“简化版 Premiere”，而是一个 **AI-native video editing runtime**：

```text
创作意图
  ↓
GPT / Agent
  ↓
语义操作（scene / composition / camera / transition / effect / audio / caption）
  ↓
canonical project.json
  ↓
确定性 renderer
  ↓
preview / QA / frame inspection
  ↓
Agent 局部修正 / 回滚
```

## 当前基线

当前稳定开发基线：**v0.2.0-alpha.7**。

完整源码 Handoff 位于 Google Drive：`AgentCut_v0.2.0-alpha.7_Handoff`。

Alpha 7 在 Alpha 6 基础上新增 Cinematic Composition：
- `cover`
- `contain`
- `native_window`
- `ambient`
- 基于素材分辨率 / 宽高比 / focus tags 的自动构图规划
- 九宫格字幕位置建议

同时已经把 Alpha 6 的 `shared_morph` 真正渲染与 rhythm analysis 恢复进完整源码树。

## 不可破坏的架构不变量

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
14. cache 必须基于真实依赖。

## 推荐阅读顺序

1. `README.md`
2. `V0.2_ALPHA7_NOTES.md`
3. `VALIDATION_SUMMARY_A7.md`
4. `V0.2_ALPHA6_NOTES.md`
5. Google Drive 中完整 Alpha 7 Handoff（需要源码/测试时）

## 发布前验证

Alpha 7：48/48 tests passed（分组回归），`agentcut doctor` pass。

最终判断标准仍然是：这个能力是否让 Agent 更清楚、更确定、更低成本地完成剪辑。
