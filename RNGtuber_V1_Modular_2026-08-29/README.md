# RNGtuber V1 Modular｜周婉晴

这是可直接运行的 Windows 模块化 RNGtuber。人物由固定 Base 与独立眉毛、眼白、左右虹膜、眼线/眼睑、嘴巴等 Sprite 实时合成，不再依赖多张完整人物 PNG 硬切换。

## Windows 使用

1. 下载 `RNGtuber_V1_Windows.zip`。
2. 完整解压 ZIP（不要直接在压缩包里运行）。
3. 双击根目录中的 `RNGtuber.exe`。

首次启动会同时显示透明人物窗口与控制面板。Windows SmartScreen 若提示未知发布者，请选择“更多信息 → 仍要运行”；V1 暂未购买代码签名证书。

## 已实现

- Base + 独立 Sprite 的数据驱动渲染器，角色配置与 Renderer 解耦；
- Casual / COS 独立 transform profile，切换采用无闪烁叠加过渡；
- Calibration：Alpha 自动提取、眼/嘴分组与单部件两级校准、移动、X/Y 独立缩放、旋转、透明度、Z-order、半透明 Base 对照、自动持久化；
- 麦克风 `closed ↔ open`，带 -33/-38 dB 滞回与 50 ms attack / 280 ms release；
- 自然随机眨眼、轻微呼吸和身体摆动；
- 左右眼球独立、弹性平滑追踪鼠标，使用圆形限幅与眨眼衰减，不能瞬移或越出眼眶；
- `neutral / happy / unamused / surprised` 与 `casual / cos`；
- XInput 四手柄轮询 + pygame-ce 通用手柄降级，实时显示双摇杆、十字键、ABXY、肩键与扳机；
- 键鼠输入显示、自动淡出、透明/绿幕输出、窗口置顶与鼠标穿透；
- 无麦克风、无手柄或配置损坏时仍可启动。

## 快捷键

快捷键为全局轮询：

- `Ctrl + Alt + 1/2/3/4`：常态 / 开心 / 无语 / 惊讶；
- `Ctrl + Alt + 7/8`：常服 / COS。

## Calibration

进入控制面板的 `Calibration`：

1. 选服装 profile，再选“左眼整体 / 右眼整体 / 嘴巴整体”或单个部件；
2. 开启“半透明 Base 校准预览”；
3. 调整 X、Y、Scale X、Scale Y、Rotation、Opacity 与 Z-order；
4. 每次调整立即原子写入用户配置，重启自动恢复；
5. “恢复当前目标默认值”只清除当前服装/当前目标的覆盖值。

建议先用分组校准完成整体注册，再对虹膜、眼睑或单个嘴型做小幅细调。张嘴采用固定上唇注册点向下展开，闭嘴与开嘴切换不会再向上跳。

## 动态预览

`reports/previews/` 包含 Casual/COS 的 5.4 秒循环 GIF，以及 idle / talk / blink 六状态定位对照 PNG。预览由与运行时一致的分组 transform、眨眼遮罩、嘴型插值、眼球限幅和呼吸参数生成。

配置与日志保存在 `%LOCALAPPDATA%\RNGtuberV1\`，不会改写发布包中的正式角色母版。

## OBS

- 推荐直接用“窗口采集”捕获 `RNGtuber V1 Modular｜周婉晴`；
- 若透明窗口捕获方式与当前 OBS/显卡不兼容，切到“绿幕背景”并添加色度键；
- 需要操作游戏时开启“鼠标穿透”，需要拖动人物时临时关闭。

## 源码开发与打包

需要 Python 3.11：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
.\build_windows.ps1
```

`build_windows.ps1` 会执行资产生成/QA、单元测试、PyInstaller onedir 构建、打包后 EXE 诊断、3 秒 GUI smoke test，并生成 `release\RNGtuber_V1_Windows.zip` 及 SHA-256。
