# ADOFAI 封面制作器

ADOFAI Cover Studio 是用于制作《冰与火之舞》音游视频封面的 Windows 本地桌面工具。当前版本 **0.8.0**，作者 **ZAC688**。

## 项目解决什么问题

制作音游视频封面时，通常需要组合底图、轨道、曲名、标题和贴纸，再反复调整文字、光效与排版。本项目把这些操作放到同一个编辑器中，支持从截图提取轨道，或直接从 `.adofai` 谱面生成静态轨道，并复用文字与滤镜预设。

程序在当前电脑运行，自动保存上次作品，输出静态封面图片。使用成品程序无需账号、联网、浏览器或云数据库。

## 主要功能

| 功能 | 当前支持内容 |
| --- | --- |
| 素材与图层 | 上传底图和轨道图片；标题、轨道各最多 5 个；对象可拖动排序、移动、旋转，轨道可缩放；支持撤销、重做和 Delete 删除对象。 |
| 标题与字体 | 编辑文案、颜色、字号和位置；内置中英文字体，也可上传 TTF、OTF、WOFF、WOFF2；新建标题默认零发光。 |
| 光效与阴影 | 独立开关并叠加外发光、内发光、多尺度 Bloom、发光描边、渐变填充、斜面高光和水平模糊；支持渐变颜色与方向跟随、Screen／Add 混合及阴影。 |
| 3D 文字 | 使用 three.js 生成静态 3D 文字，调整厚度、倒角、三轴朝向、透视、正面／侧面颜色和光照。 |
| 轨道去背景 | 在本机识别纯色或暗色规则纹理背景中的轨道；保留原图，可用擦除／保留画笔修正结果。 |
| 谱面生成轨道 | 导入 `.adofai`，选择包含两端的起止砖块、裁切、自动适配；金黄色石砖／谱面配色可选，显示兔子、乌龟和旋转图标；预览后应用，已应用轨道可再次编辑选段。 |
| 曲目信息 | 从谱面读取曲名和音乐作者，分别勾选是否新增独立白色标题，默认不勾选，仍计入 5 个标题的限制。 |
| 贴纸与图片融合 | 253 份预设贴纸按目录分类，可选 GIF 静态帧、缩放、旋转并加阴影；贴纸数量不限。轨道图片可用渐变蒙版调整融合位置、宽度和角度。 |
| 滤镜与预设 | 38 种 PixiJS 滤镜，支持按对象、整画布及局部区域管理，可折叠、排序及恢复默认参数；滤镜预设可保存、导入和导出。 |
| 文字预设 | 保存字体、字号、颜色、光效、阴影、3D 配置和滤镜；应用时保留当前文案、位置与对象旋转角度。导出的预设携带所用上传字体、滤镜贴图和蒙版。 |
| 画布与保存 | 16:9／4:3 两种画幅分别保存排版；自动保存到本机，退出后恢复；导出静态封面 PNG，或单独导出高分辨率轨道 PNG／SVG。 |

## 安装方法

### 使用 Windows 成品包

目标系统为 **Windows 10（1809 或更高）／Windows 11 x64**。

1. 获取完整的 `ADOFAI-Cover-Studio-0.8.0-windows-x64.zip`。
2. 将 ZIP **完整解压**到一个目录。
3. 双击其中的 `ADOFAI-Cover-Studio.exe`，程序会打开独立桌面窗口。

成品包自带 Qt WebEngine 运行组件，无需另装浏览器、WebView2、Python 或 Node.js。请保留 EXE 旁边的完整 `_internal` 文件夹，移动或分发时一起复制整个程序目录。

当前工作区已经生成：

- 分发包：[release/ADOFAI-Cover-Studio-0.8.0-windows-x64.zip](release/ADOFAI-Cover-Studio-0.8.0-windows-x64.zip)。
- 启动程序：[dist/0.8.0/ADOFAI-Cover-Studio/ADOFAI-Cover-Studio.exe](dist/0.8.0/ADOFAI-Cover-Studio/ADOFAI-Cover-Studio.exe)。
- 校验文件：[ZIP SHA-256](release/ADOFAI-Cover-Studio-0.8.0-windows-x64.zip.sha256)。

`dist/`、`release/` 是本机构建产物，不随 Git 源码提交；其他源码检出需要另行取得成品包或按下文自行构建。

升级时先在旧版点击“退出程序”，退出后再打开新包。新包继续使用原本的本机数据目录；0.6.0 及更早版本仅关闭浏览器可能仍保留后台服务。

### 从源码准备并运行

以下命令在 **Windows 项目根目录的 PowerShell** 中执行。已验证的开发环境为 Python **3.10.6 x64**、Node.js **24.22.1**；需先准备 Python 3.10 和 Node.js／npm。安装依赖时需要网络，完成后源码版也可在本机离线运行。

```powershell
# 创建 Python 环境并安装锁定依赖
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt

# 安装前端依赖并生成正式界面
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build

# 启动源码版的独立桌面窗口
.\.venv\Scripts\python.exe -m backend.launcher
```

源码运行需要 `models/u2netp.onnx`、`Logos/`、`frontend/public/fonts/` 等项目资源，以及刚构建的 `frontend/dist/`。依赖分别锁定于 [requirements.lock.txt](requirements.lock.txt) 和 [frontend/package-lock.json](frontend/package-lock.json)。

## 使用方法

### 用图片制作封面

1. 点击顶部“上传底图”，选择背景图片。
2. 点击“上传轨道”，选择透明轨道 PNG 或轨道截图；先在左侧选中对象，再上传可替换该对象的图片。
3. 若要去背景，展开“去背景与轨道修正”，开启“自动去除背景”；完成后可用“修正轨道”中的画笔修正。
4. 选中标题，输入文字并设置字体、字号、颜色、位置、旋转及光效；需要时切换 3D 文字模式。
5. 在左侧添加标题、轨道或贴纸，拖动对象行调整遮挡顺序。右侧“滤镜”按当前对象管理效果。
6. 切换 16:9／4:3，分别调整排版。
7. 点击顶部“导出图片”，检查预览、填写文件名，再点击“导出到电脑”，选择保存位置。

### 从谱面生成轨道

1. 点击“从谱面生成”，导入 `.adofai` 文件；无需提供音乐文件。
2. 输入起止砖块编号，编号从 **0** 开始，**起点和终点都包含**；也可通过整图定位和点选选择。
3. 设置轨道外观、图标、画幅、导出分辨率和留白，按需框选裁切。
4. 如需曲目信息，分别勾选“生成音乐名称标题”“生成音乐作者标题”。字段缺失时相应选项不可用；标题名额不足时会提示。
5. 点击“生成并预览”。可返回调整、单独“导出轨道 PNG”，或“应用到封面”；选段窗口内还可导出 SVG。
6. 已应用的轨道可从对象行“⋯”菜单中的“编辑谱面选段”再次调整。取消生成窗口不改变原作品。

### 复用文字或滤镜样式

选中标题，进入右侧“滤镜”，在“文字预设”中填写名称并保存。之后可应用到其他标题，或导出 `.adofai-text.json` 文件供另一份本机数据目录使用；应用保留当前文案、位置和对象旋转，3D 内部朝向随样式恢复，可撤销。

原“滤镜预设”继续可用，保存当前目标的整套滤镜和作用范围，导出文件为 `.adofai-filters.json`。导入、保存预设本身不会改变当前画面。

完整操作与参数说明见 [使用说明](docs/使用说明.md)，也可在程序顶部“信息”中离线阅读。

## 输入输出示例

### 示例一：图片素材合成封面

输入文件名仅作示意，可使用自己的图片：

```text
输入：background.jpg（底图）＋ track.png（透明轨道）
文字：第一行“示例曲目”，第二行“全连演示”
设置：16:9 画布、文字光效、轨道位置和大小
导出文件名：示例封面
输出：示例封面.png，1920 × 1080
```

切换到 4:3 并调整排版后，可再导出 **1440 × 1080 PNG**。操作框、手柄和编辑器界面不会进入封面图片。

### 示例二：由 `.adofai` 生成轨道与曲目信息

以下是本制作器可读取的最小静态轨道示例，保存为 UTF-8 文件 `demo.adofai`：

```json
{
  "angleData": [0, 0, 90, 180, 270],
  "settings": {
    "song": "示例曲目",
    "artist": "示例音乐作者",
    "bpm": 100,
    "trackColor": "336699"
  },
  "actions": [
    {
      "floor": 1,
      "eventType": "SetSpeed",
      "speedType": "Bpm",
      "beatsPerMinute": 200
    },
    { "floor": 3, "eventType": "Twirl" }
  ]
}
```

导入后选择砖块 **0—5**，共 6 块，设置 16:9、长边 3840，然后“生成并预览”：

- 单独导出轨道 PNG：`轨道-0-5-3840.png`，**3840 × 2160**，背景透明；也可从选段窗口导出 SVG。
- 勾选两个曲目信息选项并应用：新增“示例曲目”和“示例音乐作者”两个独立白色标题，可继续编辑。
- 将轨道用于封面后，顶部“导出图片”仍按封面画布输出 **1920 × 1080**；轨道素材的 4K 分辨率不改变最终封面尺寸。

### 支持的输入与输出范围

| 类型 | 格式与限制 |
| --- | --- |
| 上传图片 | PNG、JPEG；每个原始文件最大 10 MB（10,000,000 字节）。 |
| 上传字体 | TTF、OTF、WOFF、WOFF2；每个文件最大 50 MB（50,000,000 字节）。 |
| 导入谱面 | `.adofai`；最大 10 MB，最多 20000 段。曲名读取 `settings.song`，音乐作者读取 `settings.artist`。 |
| 预设交换 | 文字预设／滤镜预设 JSON；每个文件最大 100 MB（100,000,000 字节），携带各自使用的资源。 |
| 最终封面 | PNG；16:9 为 1920 × 1080，4:3 为 1440 × 1080。 |
| 独立轨道素材 | 透明 PNG／SVG；长边可选 1920、2560、3840、4096，画幅可选 16:9、4:3 或紧贴内容。 |

## 数据保存与恢复

作品保存在当前 Windows 用户的 `%LOCALAPPDATA%\AdofaiThumbnailGenerator`，其中包括作品数据库、图片、蒙版、上传字体、源谱面、生成参数及两类预设。程序目录与作品数据目录分开，重新启动或更换程序目录后继续恢复上次作品，不依赖原素材路径或浏览器缓存。

顶部显示“已保存到本机”表示最新修改已写入。关闭桌面窗口或点击“退出程序”时会先保存；保存失败会保留窗口和内容，供重试。需要备份时，退出程序后复制整个数据目录。

## 已知范围与验证记录

- 去背景主要面向纯色／暗色规则纹理背景。当前 9 张已确认标注的 `test_2` 截图逐张自动结果 IoU≥90%；这是该组样本的验收结果，不代表任意复杂背景截图都有相同效果。复杂背景可使用候选结果和画笔修正。
- 谱面生成目前还原基础静态方向和 PositionTrack 位移；静态缩放、粘性轨道尚未完整还原，不重现轨道动画、镜头、装饰、特效和色彩动画。石纹与图标为参考图风格重绘，外观需对照验收。
- 当前实际测试主机为 Windows 11 x64。Windows 10、第二台电脑、实际系统重启及操作系统断网的完整流程仍需按 [实机验收清单](docs/MANUAL_ACCEPTANCE.md) 检查。
- 0.8.0 在 2026-11-11 的完整验证记录为：前端 45 项、Python 463 项、额外用户谱面 15 项，共 523 项通过，无失败、无跳过。详见 [开发与验收报告](docs/DEVELOPMENT_STATUS.md) 和 [0.8.0 开发记录](docs/UPGRADE_080_PROGRESS.md)。

## 源码打包与检查

前端使用 React／TypeScript、Canvas、PixiJS Filters 和 three.js，后端使用 Python／FastAPI／SQLite，桌面窗口使用 PySide6／Qt WebEngine，Windows 打包使用 PyInstaller。

### 构建 Windows 分发包

仓库的打包和全量检查脚本使用 `tools/npm/package/bin/npm-cli.js`。当前工作区已准备该工具；新检出可先按下面的固定版本准备，再执行打包：

```powershell
# 在项目内准备脚本所需的 npm 工具（需要 Node.js 和可用的 npm）
New-Item -ItemType Directory -Force tools/npm | Out-Null
npm.cmd pack npm@12.2.2 --pack-destination tools/npm
tar -xf tools/npm/npm-12.2.2.tgz -C tools/npm

# 已完成前文 Python／前端依赖安装后，构建完整 EXE 目录及 ZIP
.\packaging\build-windows.ps1
```

默认输出为 `dist/0.8.0/ADOFAI-Cover-Studio/` 和 `release/ADOFAI-Cover-Studio-0.8.0-windows-x64.zip`，同时生成 SHA-256 文件。构建时收集依赖许可，首次准备依赖与许可资料需要网络；成品运行不下载组件。

### 运行检查

```powershell
# 使用已安装的 npm 检查前端
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run test
npm.cmd --prefix frontend run build

# 完整测试仍保留历史 P0 冻结程序检查，先构建对应原型
.\packaging\build-p0.ps1

# 已构建正式包、准备项目内 npm 工具及验收素材后，运行全部常规检查
.\tools\test-all.ps1

# 额外验证本机 generate_test/ 中的四份用户谱面
.\.venv\Scripts\python.exe -m pytest experiments/test_static_track_samples.py experiments/test_static_track_editor_samples.py -q
```

测试使用临时作品目录。开发测试需要已安装的 Microsoft Edge；内置引擎测试直接运行 Qt，成品用户无需安装 Edge。完整测试还依赖本机验收原图及批准标注，原图需与 [历史素材清单](test-assets/manifest.json) 和 [当前九张识别样本清单](test-assets/solid/manifest.json) 匹配；额外 15 项测试需要 `generate_test/` 中的四份原谱面。准备说明见 [验收素材说明](test-assets/README.md)。这些私人原图、原谱面和构建产物不随 Git 提交或成品分发；新检出缺少时不能视为已经具备完整测试环境。

`tools/test-all.ps1` 会运行类型检查、lint、前端测试、生产构建和全部常规 pytest，并把结果写入 `artifacts/final/`；任何一项失败均返回非零退出码。

## 项目文档

- [使用说明](docs/使用说明.md)：具体操作步骤与参数。
- [PRD](PRD.md)：产品范围和验收标准。
- [开发计划](DEVELOPMENT_PLAN.md)：早期阶段任务及验证方法。
- [开发与验收报告](docs/DEVELOPMENT_STATUS.md)：各版本实现、测试结果和已知限制。
- [0.8.0 开发记录](docs/UPGRADE_080_PROGRESS.md)：本版四项功能的测试与提交记录。
- [实机验收清单](docs/MANUAL_ACCEPTANCE.md)：需要真实 Windows 环境检查的项目。
