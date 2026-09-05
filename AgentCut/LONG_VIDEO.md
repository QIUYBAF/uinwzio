# 长视频粗剪与模块化部署

**1.1.0.dev0 开发版；上一稳定版 1.0.1。** 默认场景：战地游戏直播回放，“精彩交战＋前后语境”。本版是候选筛选与粗剪基础流程，尚未验证游戏击杀、战局、精彩程度识别。

## 轻量启动

Python 3.11+ 和 PATH 中的 FFmpeg/ffprobe 即可运行粗剪，无需 Python 第三方包、GPU、大模型、Node、Chromium 或数据库。

```bash
python AgentCut/run.py modules
python AgentCut/run.py roughcut "D:/recordings/battlefield.mp4" "D:/cuts/session"
```

默认分块 300 秒，解码单声道 8 kHz 音频，逐 0.5 秒计算 RMS。超过 -28 dBFS 的活动形成候选事件；前留 12 秒、后留 8 秒，重叠或相隔不超过 5 秒的候选合并。只分析音轨，不解码全长高分辨率视频，不创建全长代理，不复制原片。默认单块临时 PCM 约 4.8 MB，用完删除；小型事件元数据随时长增长，解码器资源使用仍取决于媒体格式。

音乐、喊话可能误选，安静的精彩操作可能漏选。`--audio-threshold -22` 提高门槛；`--audio-stream 1` 选择第二条音轨（序号从零开始），可选择 OBS 单独录制的游戏声。多音轨导出目前只保留指定的一条音轨，不自动混合游戏声与主播声。

```bash
python AgentCut/run.py roughcut replay.mkv cuts --before 15 --after 10 --budget 600
```

`--budget` 是候选总秒数上限：按分数选完整候选，再按原片顺序排列，不截断语境凑时长。长候选可能全部落选，计划会提示原因。分数是信号强度，不是精彩概率。默认无总时长限制。

## 审阅、导出、续跑

审阅 `cuts/plan.json` 中 `clips` 的 `start/end`（原片绝对秒数），删除不需要的片段后导出：

```bash
python AgentCut/run.py roughcut-export cuts/plan.json cuts/preview.mp4
```

只编码所选区间并拼接，输出 H.264/AAC、最大 1280×720、30 fps、保留原比例和所选音轨的预览。重新编码保证剪点精度，不承诺无损或最终交付画质。每次一个编码任务，解码/编码线程数设为 2；导出临时片段磁盘占用随候选总时长增长。已有输出拒绝覆盖，空计划拒绝导出。计划始终标记 `needs_review`，不会自动改写项目。

重跑原分析命令即可续跑。`checkpoint.json` 记录进度，`chunks/` 保存每块结果；失败块不会被标为完成，损坏缓存会重算。更改语境和预算只重新选片；原片、块长度、检测参数或检测器版本变化会使用新缓存键。旧缓存不会自动清理，任务结束可删除 `chunks/`。重算会更新 `plan.json`，人工修改后请先另存计划。

同一任务有 OS 文件锁防止并发写入；进程退出后自动释放，不用删锁文件。源身份使用路径、大小、修改时间及首尾各 1 MiB 摘要，不是全文件校验；同大小、同修改时间且只变更中间内容的情况无法检出。使用录制完成的原片，不要分析仍在写入的直播文件。

## 模块接口

人工标记、ASR、视觉识别、游戏 HUD 可独立部署，输出统一 JSON 列表：

```json
[
  {"start": 1234.5, "end": 1252.0, "score": 0.85, "label": "manual_combat"},
  {"start": 3020.0, "end": 3036.0, "score": 0.9, "label": "reviewed_highlight"}
]
```

`score` 为 0–1；时间为原片绝对秒数；越界、倒置、非有限数值会拒绝。外部文件可以包含多个分析模块合并后的事件：

```bash
python AgentCut/run.py roughcut replay.mp4 cuts --events events.json
```

`--events` 替代音频检测，仍用 ffprobe 检查原片。Python 扩展实现 `agentcut.roughcut.Detector`，通过 `analyze_recording(..., detector=...)` 注入；每次返回当前块内的绝对时间事件。`cache_key` 必须包含算法版本、模型及参数身份。计划不会加载或执行外部代码。

## 接入原编辑器

`project.json` 仍是编辑项目唯一真相，粗剪计划只是前处理文件。旧编辑器不自动保留视频原声，因此目前对接为**视觉时间线**；有声粗剪用 `roughcut-export`。

```bash
python -m pip install -e './AgentCut[render]'
python AgentCut/run.py quickstart PROJECT --create
python AgentCut/run.py add-asset PROJECT replay.mp4 --id roughcut_source --no-copy
python AgentCut/run.py roughcut-operations cuts/plan.json cuts/operations.json
python AgentCut/run.py agent-preflight PROJECT cuts/operations.json
python AgentCut/run.py apply PROJECT cuts/operations.json
```

`--no-copy` 引用原片，原片需保持可访问；旧资产注册仍做全文件 SHA-256，长视频会有顺序读取开销。操作文件仅添加场景，复用 preflight/apply、历史和撤销。重复 ID 报错；多个粗剪可用不同 `--asset-id` 并注册相同 ID 的素材。

## 部署档位

| 档位 | 安装 | 范围 |
|---|---|---|
| Core | 直接运行或 `pip install -e ./AgentCut` | 发现、纯事件选片逻辑 |
| 粗剪 | Core + 外部 FFmpeg/ffprobe | 音频分析、计划、原声预览 |
| Render | `pip install -e './AgentCut[render]'` | 原完整编辑器、图像与渲染 |
| API | `pip install -e './AgentCut[api]'` | Render + HTTP 服务 |

**1.0.1 升级注意：**基础安装不再自动安装 NumPy/Pillow；旧编辑器、quickstart、渲染请选 `[render]`。已安装依赖不会卸载，API 档位包含编辑依赖。ASR、Remotion、GPU 增强继续外置。

可选容器：仓库根目录执行 `docker build -f AgentCut/Dockerfile --target core -t agentcut-core .`；`render`、`api` 构建目标按需加依赖。原片和任务目录需挂载，计划中的路径对应容器路径。无需常驻服务。容器定义尚待具备 Docker 的环境构建验收。

下一步：用真实战地回放和人工精彩片段标注，评估召回、误选、上下文、处理速度和峰值内存，再决定 HUD/视觉模块。合成媒体和六小时调度测试不能替代实片验收。

媒体剪点和流选择参考 [FFmpeg 官方文档](https://ffmpeg.org/ffmpeg.html)。
