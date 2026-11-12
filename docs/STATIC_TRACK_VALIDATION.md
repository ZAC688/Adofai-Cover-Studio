# 从 .adofai 生成静态轨道：首轮验证

日期：2026-11-10。范围：用户提供的四组主谱；不还原轨道动画、镜头、装饰和特效。

后续已增加交互选段、裁切、自动适配、默认轨道色、矢量图标和 4K 导出，当前试用入口及 105 项相关验证记录见 [静态轨道选段与缩略图试验](STATIC_TRACK_EDITOR_PROGRESS.md)。下文保留首轮验证结果。

## 结论

四份主谱都能离线读取，并生成透明 PNG、SVG、局部放大图和可追溯的节点坐标。基础方向数据生成静态图片的链路已验证可行。

当前是独立实验，尚未接入封面编辑器，未改变 0.6.0 程序或分发包。采用自绘的统一简化砖块、旋转和中旋示意图标，不复刻 Neon、NeonLight、Gems 材质，也没有复制游戏图片资源。测试证明方向计算和导出契约通过，**不代表已通过与游戏截图的视觉一致性验收**。

Heaven’s Gateway 的静态缩放和粘性轨道语义还未还原；Crystallized 的粘性轨道位移也需核对。两者应先作为对照试算查看，不能宣称完整还原。

## 实际输入与结果

输入目录：项目根目录下的 `generate_test/`。四个顶层文件夹含 10 份 .adofai 文件，包括备份和 Inferno 变体。本轮优先选择每组的 `main.adofai`，Crystallized 使用同名主谱，没有把备份当成额外验收样本。

| 主谱 | 编码 | 方向数 | 节点数（含起点） | 中旋 | 应用静态位移事件 | PNG 尺寸 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Heaven’s Gateway | angleData | 3354 | 3355 | 56 | 60 | 2198 × 2015 |
| The Limit Does Not Exist | pathData | 1360 | 1361 | 0 | 0 | 1253 × 2198 |
| Inferno | angleData | 1795 | 1796 | 36 | 0 | 2198 × 1694 |
| Crystallized | pathData | 2040 | 2041 | 108 | 1 | 2198 × 611 |

三个主谱有普通 JSON 解析器不接受的尾逗号。实验解析器支持 BOM、尾逗号、注释和旧谱字符串中的换行，按字符串边界处理，保留网址、引号和歌曲信息；不执行谱面内容。不支持的方向字符和无效数值会明确失败。

全部 10 份谱面在生成前后的 SHA-256 一致。选中主谱的具体路径、哈希、事件数量及导出尺寸记录在 `manifest.json`；其余音乐、背景图片等素材不读取、不复制、不修改。

## 输出与检查入口

双击 `artifacts/static-track-validation/index.html` 可在浏览器离线查看全部结果。`overview.png` 是四图总览。每份主谱各有一个子目录：

- `track.png`：透明底整图，方向数据加非 editorOnly 的 PositionTrack 位移试算。
- `track.svg`：同一砖块多边形的矢量版本，可放大检查。
- `base-layout.png` / `.svg`：只使用方向数据、不应用 PositionTrack 的基础布局。
- `preview.png`：深色背景的整图阅读版。
- `detail-*.png`、`detail-*-preview.png`：开头、中段和中旋／静态位移附近的局部图，标注部分节点编号，便于对照。
- `geometry.json`：逐节点坐标、进出方向、示意图标和元数据。

编号从 0 开始。局部图直接复用整图坐标和方向，不重新推算截取段的起点。整图尺寸受限，长谱砖块较小；检查砖块形状请查看局部图或 SVG。

## 当前计算范围与已知差异

已覆盖本轮样本出现的 24 种绝对方向字符、普通角度、负角度和超过 360 度的角度；999 / `!` 中旋将上一条已解析方向反转 180 度，后续节点回到前一位置。连续中旋交替反转。Twirl 只影响示意图标，不镜像方向数据；Checkpoint 使用简化旗标。

PositionTrack 仅应用 `relativeTo=[0,"ThisTile"]`（或缺省）、rotation=0 的平移，支持单块位移和向后传播的位移。editorOnly=true / Enabled 不应用于游戏布局试算。位移产生间隔时不会凭空画出长连接线。

以下差异均在预览页和元数据中明示：

1. Heaven’s Gateway 的 62 个 PositionTrack 中有 2 个仅编辑器可见，本轮忽略；60 个应用位移。其中 56 个还带 scale=120，该缩放尚未应用。
2. Heaven’s Gateway 的 4 个 ScaleRadius 事件没有应用；半径、间距和粘性轨道组合语义仍需用游戏画面核对，不能先假定效果。
3. Heaven’s Gateway 与 Crystallized 的 stickToFloors 已启用，最终游戏静态位置尚未确认。
4. MoveTrack（包括 duration=0）、AnimateTrack、MoveCamera、速度、暂停、色彩动画、滤镜、背景、球体及装饰不参与当前静态布局。本轮没有尝试生成某一播放时刻的截图。
5. 砖块是统一示意材质；填充色、轨道皮肤、游戏原版图标、重叠时的最终显示关系均未与游戏逐像素核验。
6. 不在本轮样本中的相对方向编码、特殊轨道尺寸、Hold／FreeRoam 等布局，未作为支持项验收。未知方向编码会报错，不静默生成猜测结果。

## 自动测试与人工检查

执行结果：**52 项通过，0 失败、0 跳过**，8.29 秒。

- 42 项可分发的单元／导出测试：手算方形与斜线坐标、旧新编码等价、中旋回折、连续中旋、负角度、位移传播、编辑器专属位移排除、忽略范围、错误数据失败保护、无跨空隙连接线、PNG 透明度和边缘、SVG 节点与向上坐标等。
- 10 项私有样本验收：四份主谱的固定哈希、节点／中旋数量、有限坐标、SVG 砖块数量、透明且无裁切的 PNG、真实谱面的每步单位距离与中旋回折、全部源文件不变、已知差异可见。
- 已检查四图总览及每组局部图，能够看到独立砖块、转角和中旋／旋转标记。

首次运行发现长谱使用世界坐标留白时像素边缘不足，已增加固定像素边距；原裁切断言保留并通过。字符串测试夹具因 Windows 自动转换换行产生差异，改为写入明确的 UTF-8 字节，不改变解析器对原字符串的保留要求。

证据：`artifacts/static-track-validation/tests.xml`、`manifest.json`、各组图片及 `geometry.json`。本轮仅执行实验相关验证；生产程序未改动，未重跑完整应用与冻结分发包测试。

## 重现

在项目根目录执行，使用已有 Python 环境，无需安装新依赖：

```powershell
.\.venv\Scripts\python.exe -m experiments.static_track_probe
.\.venv\Scripts\python.exe -m pytest tests/experiments/test_static_track_probe.py experiments/test_static_track_samples.py --junitxml=artifacts/static-track-validation/tests.xml -q
```

生成器支持 `--input` 和 `--output`。私有样本验收文件位于 experiments，需显式运行；缺少或变更验收样本会失败，不通过跳过来隐藏。默认测试目录下的 42 项测试使用自建数据，不依赖用户私有谱面。

下一步应对照实际游戏编辑器中的相同节点，确认基础方向和位移；优先核对 Heaven’s Gateway 的 1282 附近、Crystallized 的 925 附近。随后才能确定静态缩放与粘性轨道的实现，再考虑把谱面导入、选取轨道段和输出接入封面编辑器。

## 格式语义参考

查阅了 [ADOFAI-JS 的方向表](https://github.com/adofaiex/ADOFAI-JS/blob/main/src/pathdata/index.ts)，用于核对旧版 pathData 的绝对方向编码；中旋方向和节点数量另参考 [SharpFAI 的 CreateFloors](https://github.com/adofaiex/SharpFAI/blob/main/SharpFAI/Util/LevelUtils.cs)。本实验没有引入这些库或复制其渲染实现，砖块几何与示意图标独立实现。库列出某类事件不等于已完整实现其游戏行为，因此没有将其当成缩放／粘性轨道已正确的证据。
