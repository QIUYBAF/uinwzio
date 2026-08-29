# RNGtuber V1 Modular｜QA 与已知问题

## 自动验证门槛

- 所有正式 Base/Sprite 必须为 `1024×1536 RGBA`，Alpha 有有效区域；
- 两套服装必须覆盖全部 Layer transform；
- 配置损坏恢复、Casual/COS 分组与单部件 Calibration 持久化测试；
- 麦克风滞回/hold、眨眼、眼球弹簧与无输入设备降级测试；
- Windows PyInstaller onedir 构建；
- 只读正式素材 QA 与状态矩阵渲染（构建过程禁止用旧输入覆盖正式 Sprite）；
- 打包后 `RNGtuber.exe --diagnostics` 与 3 秒 GUI demo smoke test；
- ZIP CRC、根目录 `RNGtuber.exe` 与 SHA-256 校验。

## 已知问题

- V1 使用两态嘴型，不做复杂音素识别；阈值需按麦克风增益微调。
- 当前云端 QA 无法代替用户机器上的真实麦克风、全部第三方手柄型号和 OBS 捕获组合测试；XInput 为主路径，pygame-ce 为通用降级路径。
- Windows EXE 未做商业代码签名，SmartScreen 可能首次提示。
- AI 输入部件画布和尺寸不统一；已过滤远端低 Alpha 噪点、自动裁切并提供眼/嘴分组和单部件永久 Calibration，但个人审美仍可能需要微调。
- 表情由现有单部件的 transform/opacity 组合实现，视觉丰富度受当前单件素材限制；架构已允许后续加入新的独立表情辅助层。
- 鼠标穿透打开后无法直接拖动人物；需从控制面板关闭后再移动。

## 回归重点

若替换资产或角色 JSON，至少重新检查：透明边缘、眼组 pivot、虹膜圆形限幅、睁眼/闭眼交叉淡化、上唇注册点、两套服装独立 profile、损坏配置启动、无麦克风/无手柄启动和打包资源路径。
