# START HERE — AgentCut v0.2.0-alpha.8

> 跨对话 / Work / Codex 接管 AgentCut 时先读本文件。

## 一句话定义

AgentCut 不是传统 NLE GUI，而是一个 **AI-native video editing runtime**：

```text
创作意图 → 语义操作 → canonical project.json → 确定性 renderer → preview / QA / frame inspection → Agent 局部修正 / 回滚
```

## 当前基线

当前稳定开发基线：**v0.2.0-alpha.8**。

完整源码 Handoff 位于 Google Drive：`AgentCut_v0.2.0-alpha.8_Handoff`。

Alpha 8 的核心是把视觉理解真正接进渲染链：
- deterministic visual saliency analysis
- `focus_x / focus_y` 真正驱动 FFmpeg cover crop
- guarded dynamic `focus_path` subject tracking
- subject crop-risk protection
- visually safe nine-zone text placement
- dialogue `position="auto"`
- `auto_compose_scenes()` bulk workflow
- composition-aware scene cache key
- QA for stacked tracking/camera motion and text overlap risk

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
14. cache 必须包含所有真正影响像素/音频的语义依赖。
15. 自动视觉决策必须可被明确艺术意图覆盖。

## 推荐阅读顺序

1. `README.md`
2. `V0.2_ALPHA8_NOTES.md`
3. `ALPHA8_PRACTICAL_WORKFLOW.md`
4. `VALIDATION_SUMMARY_A8.md`
5. `V0.2_ALPHA7_NOTES.md`
6. Google Drive 中完整 Alpha 8 Handoff（需要源码/测试/范片时）

## 发布前验证

Alpha 8：**57/57 tests passed**（分组回归），`agentcut doctor` pass；focus-aware crop、dynamic focus path、integrated smoke render 均实际出片通过。

最终产品判断标准：这个能力是否让 Agent 更可靠、更低成本地完成真实剪辑，而不是增加功能数量。
