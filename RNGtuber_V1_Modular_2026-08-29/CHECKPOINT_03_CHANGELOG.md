# Checkpoint 03｜眼口注册与动态分离

版本：RNGtuber V1 Modular 1.1.0

## 本轮完成

- 新增 `eye_left`、`eye_right`、`mouth` 三个父级分组；组内眼白、虹膜、上下眼睑、闭眼片、眉毛或嘴型保持相对结构，可整体移动、独立 X/Y 缩放、旋转、透明度与层级。
- Casual 与 COS 分别保存组 transform 和 pivot；COS 不再沿用 Casual 的脸部坐标。
- Alpha 裁切忽略大画布中的孤立低透明噪点，同时保留全画布 Sprite 的自然原点。
- 张嘴以固定上唇注册点向下展开；闭嘴/开嘴使用窄交叉淡化区，减少跳位与重影。
- 眼白、虹膜和睁眼睑在眨眼时同步压缩并淡出，闭眼片同步淡入；虹膜运动随眨眼衰减。
- 眼球追踪增加死区、弹性插值与圆形限幅，左右眼分别受眼眶半径约束。
- Calibration 面板同时支持“分组”与“单部件”两级编辑，配置 schema 升级并保持旧配置兼容。
- Windows 构建改为只读验证正式素材，不再从旧输入素材重新生成运行资产。
- 修复 Windows packaged GUI smoke test 的退出清理：Qt 退出时显式关闭 pygame/SDL，并给 diagnostics / GUI smoke test 增加 15 秒外部硬超时，避免 CI 被悬挂进程拖到 workflow 总超时。

## 本轮预览

- `reports/previews/casual_blink_talk_gaze_preview.gif`
- `reports/previews/cos_blink_talk_gaze_preview.gif`
- `reports/previews/eye_mouth_registration_v11.png`

GIF 为 5.4 秒、15 FPS 循环，组合张嘴、两次自然眨眼、受限眼球追踪与轻微呼吸/摆动。
