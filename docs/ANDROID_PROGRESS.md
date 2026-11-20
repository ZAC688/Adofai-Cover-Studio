# 安卓版开发与验收记录

## 已确认范围

基于 0.8.1，保留现有用户功能并交付可直接安装的测试 APK。主要验收机型为 OPPO Reno12，系统版本待实机核对。横屏、竖屏自动调整布局；预览与底部功能标签组合，对象、属性、光效、滤镜可切换，参数可滚动。保留离线、免登录、本机保存和正常退出、重启后的恢复行为。不包含应用商店上架、账号和云同步。Windows 版继续维护。

## 执行顺序与阶段验收

1. **运行基础**：确认 Android 原生依赖；建立可复现构建、独立应用数据目录、离线页面和处理服务。验证实际 Android 引擎启动、依赖导入、健康检查、完整资源和无远程依赖。已完成，见原生补验和最终交付记录。
2. **全部处理接口**：复用作品、素材、字体、贴纸、预设、谱面、识别与轮廓处理；替换桌面进程和文件对话框。逐项验证接口、非法输入、持久化、识别质量及谱面输出，不能用占位成功代替真实功能。
3. **手机界面与触屏**：横竖屏、底部标签、弹窗、软键盘、安全区域、对象排序及画布操作。验证小屏没有横向溢出、全部入口可达、切换布局不丢状态、编辑可撤销。
4. **手机文件与生命周期**：系统文件选择、保存图片及预设、退后台和退出前保存、重启恢复。验证取消不改作品、字体/谱面/预设可导入、导出文件有效且像素和尺寸正确。
5. **整体验收与 APK**：运行所有适用的旧回归和新增 Android 测试；检查离线、全部滤镜和 3D、识别基准、选段和高分辨率导出。生成签名测试包、验证签名与 SHA-256，提供安装说明和 OPPO 实机验收清单。

每阶段通过对应有效测试后保存独立 Git 提交。失败先定位和修复，保留失败证据，不删除、跳过用例或降低标准。设备尚未执行的检查明确列为待实机验收，不宣称已通过。

## 初步技术检查

- 当前前端可复用；桌面专用 Qt WebEngine、保存对话框和识别子进程需要替换。
- 谱面生成是 Python/Pillow/NumPy 实现，可以研究复用，不需要下载音乐或执行谱面脚本。
- 采用 Android WebView 承载离线页面，研究在 APK 内嵌 Python 以复用已验收算法，避免把识别或保存转移到云端。
- 构建环境存在 JDK 17 和 Python 3.10；尚无项目 Android SDK/Gradle，需要从官方来源安装到本地忽略目录。
- Chaquopy 官方仓库有 Python 3.10 的 NumPy、Pillow、OpenCV 原生包；当前 Pydantic Core、ONNX Runtime Python 包没有找到直接可用的 Android wheel，正在验证兼容方案。未据此删减功能。

## 阶段 1A：工具与校验基础

- 已固定并校验 Google 命令行工具和 Gradle 官方 SHA-256，安装在项目忽略目录；Android 平台与模拟器镜像正在安装。
- 业务模型增加双运行时验证入口，Windows 继续使用原 Pydantic 2；安卓可使用纯 Python Pydantic 1，保留字段约束、嵌套模型、全部现有 after-validator、未知字段拒绝、有限数值和整数不截断规则。仅新增兼容入口，没有另写一套简化作品格式。
- 新增 7 项下载/解压测试与 23 项模型验证测试。原桌面环境运行 66 项通过；隔离兼容依赖环境运行同一组模型与业务用例 59 项通过。这里是 Windows 主机上的依赖兼容验证，不代替实际安卓原生包与 WebView 测试。
- 报告保存在本机 `artifacts/android/bootstrap/desktop-regression.xml` 和 `compatibility.xml`。APK 运行、手机布局与文件交互尚未完成，不能据此宣告安卓阶段全部通过。

## 阶段 1B / 2A：原生包与离线处理接口

- 已建立 Android WebView + APK 内嵌 Python 原生工程，ARM64 与 x86_64 两架构均编译成功，测试版本 `0.8.1-android.1`。当前 APK 为开发中间产物，尚未完成手机界面与文件导出，不作为最终验收包。
- Android 使用只监听 `127.0.0.1` 的处理适配器，复用原 Store、谱面渲染、字体轮廓、两类预设、253 份贴纸和识别算法。保留同源与随机会话检查、文件限制和保存冲突；识别用独立工作线程，取消后不得写入晚到结果。
- 官方 Android ONNX Runtime 用于原候选模型的本机推理，前后处理共用原实现。已增加前后处理一致性测试；JNI 真机执行尚待安卓运行测试。
- 初轮 HTTP 验证发现空贴图 JSON 参数兼容问题和无效会话请求体未消费导致的连接重置，已修复；保留失败 XML，未降低原断言。修复后，桌面与隔离兼容环境各 33 项 HTTP / 模型用例通过。
- 全部原后端回归与新增安卓测试共 239 项通过（报告 `artifacts/android/bootstrap/backend-and-android.xml`）；随后新增 APK 签名、离线资源哈希、ELF 架构检查 3 项通过。包内资源 296 份，私人原谱、图片、音乐、数据库和签名密钥未打包。
- Android SDK、平台 35、Build Tools 35.0.0、模拟器和 API 35 镜像已安装。主机 WHPX 尚未启用，已尝试无界面软件模拟，设备仍为 offline；已向用户请求是否启用 Windows 自带加速平台，等待答复。没有更改 Windows 虚拟化功能或重启电脑。等待期间继续与此无依赖的手机界面工作，原生运行验收保留为未通过。

## 阶段 3：手机界面与触屏

- 增加对象、属性、光效、滤镜四个底部栏目，竖屏上下布局、横屏左右布局，参数独立滚动；保留完整画布分辨率，仅适配显示尺寸。
- 增加触摸图层排序把手、取消排序与一键撤销。触摸按钮采用完整手势与重复 click 抑制，修复拖动后快速触摸按钮时浏览器漏发 click 的情况；不改变桌面鼠标和键盘路径。
- 适配信息、贴纸、融合、蒙版修正、滤镜范围和谱面选段窗口，覆盖短屏与安全区域。初轮发现对象面板继承桌面固定高度遮挡底栏、短屏预览过小和拖动后快速撤销漏触发，已按原断言修复，失败日志与截图仍保留。
- 手机触屏浏览器测试 15 项通过，覆盖 320/360/412 宽竖屏、804×360 横屏、360×420 短屏；包含真实文件导入、谱面 1920×1440 生成、白色曲名标题、蒙版像素变化和全部主要弹窗。
- 原 Windows 编辑、对象、属性切换、拖动轮廓、谱面界面回归 14 项通过。类型、lint 与生产构建通过。记录为 `artifacts/android/mobile-layout-05.xml`、`desktop-layout-regression.xml`；这仍不代替原生 Android 运行测试。

## 阶段 4：系统文件保存与生命周期

- 接入系统文件选择与保存，图片、独立轨道 PNG/SVG、滤镜和文字预设统一通过分块文件传输进入系统保存界面。Java 端限制大小、类型和顺序，文件名不能指定缓存路径；取消只清理本次私有导出缓存，不改作品。
- 保存过程支持 Android 活动重建后的待保存文件恢复；正常返回先保存，返回键优先关闭弹窗；退后台触发刷新待保存队列。Android 使用说明离线内置，“信息”显示安卓测试版本。
- 发现并修复手机提供器流式上传没有 Content-Length 时的读取问题，保留复现失败报告；两套依赖环境各 10 项 HTTP 测试通过。高分辨率砖号使用随包可缩放字体，避免安卓缺少 Windows 系统字体后退回小位图字。
- 修复同版本调试安装时可能复用旧页面资源的问题：资源目录以完整资源清单指纹命名，不依赖版本号重复使用旧缓存。
- 新增导出桥接单测 4 项，前端合计 52 项通过；原生 Java 文件字节、路径、顺序、取消、重建恢复与缓存清理 7 项通过；手机文件桥接契约 4 项、Windows 导出/预设/退出/信息回归 9 项通过。
- 本阶段综合手机流程、真实 HTTP 与轨道/字体回归 72 项通过；更新 APK 的签名、资源哈希、指纹和架构检查 3 项通过。证据在本机 `artifacts/android/stage4-python.xml`、`file-junit-02.log`、`file-apk-integrity.xml` 等。上述主机与 JVM 检查不能替代 Android 系统选择器与 JNI 的实际运行验收。
- 模拟器已尝试单核软件模式与内核日志，仍为 offline；观察到 QEMU 工作线程暂停，不能仅据缺少 WHPX 就断言唯一原因。尚未启用系统虚拟化或重启，继续等待用户对前述加速平台的答复。

## 阶段 5：签名、最终回归与原生验收准备

- 已补充 8 项实际 Android instrumentation 用例，覆盖真实 Python/NumPy/Pillow/OpenCV 导入、WebView/WebGL 2、three.js 与 Pixi 全分辨率像素变化、内嵌谱面窗口生成金色透明轨道、Java ONNX Runtime 数值一致性、九张已批准识别标注各自 IoU ≥90%、系统保存真实 PNG 和取消、SQLite 读回。测试包编译成功，但尚未在安卓系统执行，不能记为通过。
- 新增独立模拟器接续脚本，拒绝物理手机与不合法编号；使用 `.debug` 独立应用，另检验真实 Android 进程停止／重开后的作品与版本号保持。测试素材只进入私有 AndroidTest APK，不进入用户 APK。
- release APK 使用本地专用密钥签名，调试应用与用户应用数据隔离；密钥和凭据被 Git 忽略，重复构建验证并复用原身份，不静默重建。新增真实 keytool 身份复用／错密码保护测试通过。
- 修复手机默认字体和 3D 随包字形不一致的风险：手机普通标题的默认字体也使用随包 Noto Sans SC，Windows 的系统字体规则保留。新增手机导出字体断言通过。
- 签名版与调试版的资源、签名、ELF 架构及用户版签名身份共 7 项检查通过。首轮检查发现调试包仍是旧前端，已重建；权限断言核对到 AndroidX 自动加入的应用私有签名权限，增加精确权限集合和 signature 保护级别断言，未放宽到允许其他系统权限。失败报告保留。
- 手机文件契约与签名测试共 6 项独立重跑通过。初轮浏览器重新加载与前端构建替换 `frontend/dist` 同时发生，已明确禁止这两者并发，保留首轮错误证据。最终 Java 测试 7 项通过，安卓 lint 为 0 错误、1 条需 JavaScript 的提示；应用仅允许本机资源，JS 是编辑器实际依赖，未关闭检查或隐藏提示。
- **2026-11-18 用户批准启用 Windows 虚拟机监控程序平台；已从 Disabled 启用到 Enabled，RestartNeeded=True，没有自动重启。** 当前系统 HypervisorPresent=False，原生测试预检没有找到可用模拟器，结果明确记录 nativePassed=false。还需用户手动重启，再执行模拟器与 OPPO 实机验收。旧软件模拟失败证据仍保留，不能据启用组件就宣称已解决所有模拟器问题。
- 全部主机回归完成：540 项 Python／界面／成品测试、52 项前端单测、7 项 Java 文件测试通过；类型、lint、构建退出码均为 0。540 项用时 1326.47 秒，0 失败、0 错误、0 跳过，源码和冻结 EXE 的可见窗口性能测试均按原门槛通过。保留一条原有依赖弃用提示，未隐藏告警。
- 补充独立的 15 项用户原谱面与 9 项原生测试脚本单测共 24 项通过，其中 3 项目标保护与前述 540 项重复；本轮共 **620 项互不重复的主机／前端／JVM 测试通过**。原生测试结果判定要求八项具体用例都报告成功，跳过、假设失败、进程中断或缺用例均不接受；此判定器的合成协议单测不能替代真实安卓运行。
- 完整证据：本地 `artifacts/android/all-tests-01.log`、`artifacts/final/all-tests.xml`、`artifacts/final/check-results.json`、`artifacts/android/private-charts-and-native-protocol.xml` 与 Gradle XML。原 Windows 0.8.1 最终报告已先复制到 `artifacts/android/pre-android-final-reports`，避免与本轮结果混淆。
- 已保存签名候选包 `release/android-test-0.8.1-android.1/ADOFAI-Cover-Studio-0.8.1-android.1-test.apk`（161575959 字节），SHA-256 `dbbdc3df4604703d8b0a70281c38653abd9649e7bb094455ca4ab68f807ec674`。候选包通过签名、双架构及资源检查，**原生和 OPPO 验收仍未完成，当前不记为全部功能已在安卓通过**。

### 手动重启后的接续点

1. 检查 WHPX／虚拟机监控程序真正可用；以项目专属 `.testdata/android-avd` 启动 `adofai-api35`，等待 Android 完全启动，不触碰物理手机。
2. 运行 `tools/test_android_device.py`，保留原生完整日志；失败先修复，不能减少九张样本或降低 90% IoU、模型数值与文件像素断言。
3. 如修复涉及业务代码，重建 APK 并重跑受影响测试及最终完整回归。原生通过前不把候选包当作完成全部验收的成品。
4. 核验最终用户 APK SHA-256，交付用户安装，并按 `ANDROID_ACCEPTANCE.md` 在 OPPO Reno12 实测。用户未要求向 GitHub 推送本分支或发布安卓 Release。

## 重启后的原生补验

- Windows 重启后 HypervisorPresent=True，官方模拟器加速检查返回 0，WHPX 可用，项目独立 API 35 模拟器成功启动。使用的都是隔离 `.debug` 数据，没有连接或修改物理手机。
- 第一轮实际执行 8 项原生测试：6 项通过，谱面预览和取消保存两项失败。定位到测试选择器仅派发 change、未派发 input，且没有显式设置受断言约束的 16:9；另一个测试只按一次返回，实际只收起键盘。补齐真实选择事件与画幅后，谱面仍按原断言验证 1920×1080、透明区域和金色像素，未降低要求。
- 第二轮 7 项通过，系统返回还会退出目录层级，尚未真正取消。第三轮改为在系统界面内完成有上限的返回导航，并在返回编辑器前停止；断言仍要求系统窗口已关闭、JS 返回 cancelled、没有保存 URI、编辑器保留，不伪造取消结果。
- 第三轮 **8 项安卓原生测试全部通过，0 失败、0 跳过**。真实 three.js／Pixi 像素、Pillow 谱面生成、Java ONNX Runtime 数值对照、九张识别图各自 IoU ≥90%、SQLite、系统保存 PNG 的尺寸和像素、实际取消均通过。随后独立停止并重启 Android 进程，PID 变化、完整作品及 revision 保持的验证通过。
- 模拟器已开启飞行模式并关闭 Wi-Fi。Android 原生服务、处理与文件保存无须联网；最终签名用户 APK 也已在该环境安装并启动，横竖屏的上传入口和四个栏目均在屏幕范围内，真实截图已目视核验。
- 用户 APK 的信息窗口截图实际显示作者 ZAC688、版本 0.8.1-android.1 和手机离线运行方式。附加检查脚本未能从 WebView 的系统无障碍树读取 dl 文本，保留了该断言失败证据；后续使用电脑已有的离线 OCR 直接读取真实截图，精确匹配 `ZAC688` 与 `0.8.1-android.1` 的自动断言通过，并做了目视复核。未宣称系统树自动断言通过，也没有降低作者与版本必须准确显示的要求。
- 原生证据：本机 `artifacts/android/native/instrumentation.log`、`results.json`、两轮 `failed-*` 与完整日志；用户包截图位于 `artifacts/android/release-device`。此前“原生未执行／待重启”的描述为重启前记录，以本节结果为最新状态。
- 已按用户要求重新运行最终完整回归，结果见下一节。OPPO Reno12 的真实系统、键盘和文件管理器体验仍待用户按 `ANDROID_ACCEPTANCE.md` 验收。

## 最终测试包交付 · 2026-11-19

- `tools/test-all.ps1 -VisiblePerformanceTests` 全部通过：546 项 Python／手机浏览器／Windows 界面与成品回归，0 失败、0 错误、0 跳过，用时 1028.89 秒；52 项前端单测、类型检查、lint、生产构建退出码全部为 0。保留原有依赖弃用提示。
- 独立 15 项用户原谱面回归通过；7 项 Java 文件测试通过；Android lint 0 错误，保留编辑器需 JavaScript 的提示。加上 8 项真实安卓原生测试，本轮共 **628 项互不重复的测试通过**。另外，真实 Android 进程停止／重启后的作品与 revision 恢复通过；断网用户包的横竖屏和信息显示已检查。
- 最终 APK：`release/android-test-0.8.1-android.1/ADOFAI-Cover-Studio-0.8.1-android.1-test.apk`，161575959 字节，SHA-256 `dbbdc3df4604703d8b0a70281c38653abd9649e7bb094455ca4ab68f807ec674`。与实际安装验证的签名用户包逐字节一致。最低构建系统 Android 10，含 ARM64 与 x86_64；原生自动测试环境为 API 35 x86_64，ARM64 库的架构／完整性和签名已检查。
- 交付包保留内置字体、253 份贴纸、38 个滤镜、3D、光效、两画幅、谱面工具、去背景、蒙版、融合、预设及本机持久化。包内资源和私人素材排除检查通过；私有测试 APK、九张验收原图、原谱音乐、签名密钥和用户数据库均不交付。已发布 Windows 0.8.1 ZIP 保持原 SHA-256。
- 最终日志与报告：`artifacts/android/all-tests-after-native.log`、`artifacts/final/all-tests.xml`、`artifacts/final/check-results.json`、`artifacts/android/delivery-private-charts.xml`、Gradle Java XML、`artifacts/android/native/results.json` 和原生完整协议。失败证据继续保留，没有删除测试、跳过用例或降低识别／像素／性能断言。
- 开发与测试包交付已完成。下一步由用户把 APK 安装到 OPPO Reno12，按 `ANDROID_ACCEPTANCE.md` 检查真实系统、输入法、文件管理器和使用体验；尚未执行的 OPPO 检查不记为通过。

## 官方资料

- [Android WebView](https://developer.android.com/develop/ui/views/layout/webapps/webview)
- [Chaquopy 插件](https://chaquo.com/chaquopy/doc/current/android.html)
- [Chaquopy 原生包仓库](https://chaquo.com/pypi-13.1/)
- [Android 命令行工具](https://developer.android.com/studio#command-tools)
- [Android 模拟器加速](https://developer.android.com/studio/run/emulator-acceleration)

## 16KB 兼容性修复 · 2026-11-20

- 用户已确认先前 0.8.1-android.1 在 OPPO Reno12 上功能验收通过。跨品牌检查发现，原 APK 外层 ZIP 和 `lib/` 对齐通过，但 `.imy` 内的 Pillow、NumPy、OpenCV、Brotli 及部分传递依赖仍有 4KB 库，另有 RELRO 布局风险；旧版在官方 16KB 镜像中实际无法导入 Pillow。此前外层检查没有覆盖这一缺口，现已补齐，保留基线失败 JSON 与运行日志。
- 安卓版本更新为 **0.8.1-android.2 / 80102**，沿用原包名和签名。升级到 Python 3.13.16、NumPy 1.26.2、Pillow 11.0.0、Brotli 1.1.0、OpenBLAS 0.3.33；使用官方 NDK r28c 从固定源码编译 FreeType 2.9.1、libjpeg-turbo 3.1.3 和 OpenCV 4.12.0 的 ARM64／x86_64 库。不修改轨道识别算法或降低九张样本各自 IoU ≥90% 的门槛。
- 新增完整 APK 审计，递归按内容检查压缩包内全部 ELF，包含 `.imy` 和 `.so.3`：检查各 LOAD 的对齐及地址关系、RELRO 尾部可写数据、SDK `zipalign -P 16`。最终调试／用户包均为 **每架构 99 个 ELF、共 198 个，全部通过**。12 项审计器单测涵盖旧 4KB 库、仅改对齐字段、RELRO 陷阱、嵌套传递依赖及损坏文件。
- 缺少对应官方兼容 wheel 的组件从源码构建；修复 OpenCV Android Python 构建入口和其参数替换破坏 NDK `--no-undefined-version` 的问题。去除调试信息、映射编译路径并清理生成的构建信息中的本机路径，原生构建不通过修改 ELF 头伪造兼容。许可证按完整官方源码字节核验并保留在公共资源归档中。
- 发现 Gradle 只根据 `--find-links` 字符串保留旧 wheel 的缓存问题，已跟踪实际 `install*PythonRequirements` 任务的 wheel 输入，新增 APK 原生库与六份源码构建 wheel 的逐字节哈希对照。首轮路径／缓存失败及许可证归档定位失败报告均保留；许可证检查改为与上游源码完整字节一致，避免错误的文件大小假设。
- API 35 的早期官方 16KB 镜像完成九项功能测试，但随后旧版系统 Chromium 的 MemoryInfra 等组件延迟崩溃；保留系统堆栈，不能把首轮短暂通过当作稳定性通过。改用官方 API 36 的 16KB 镜像，系统 WebView 133.0.6943.137；明确设置并核对 `bionic.linker.16kb.app_compat.enabled=false`、`pm.16kb.app_compat.disabled=true`，`PAGE_SIZE=16384`。
- 最终 API 36／16KB 和 API 35／4KB **各九项原生测试全部通过**，均验证真实 JNI 依赖、NumPy BLAS、字体和 PNG/JPEG 编解码、three.js／Pixi 全分辨率像素、谱面预览、ONNX 数值、九张识别样本、系统保存／取消和数据库；两个环境还各通过真实进程重启、90 秒同进程持续响应与四栏目反复切换（18 次检查）。首次持续检查因 WebView 不支持浏览器下载管理命令失败，测试连接改用 Playwright 的 `no_defaults`，保留全部响应与作品不变断言。
- 4KB 旧版到新版覆盖升级通过，完整作品及 revision、**85 份旧素材文件的哈希**保持一致；随后恢复测试作品。实际签名用户 APK 在断网的 16KB 系统中安装、启动，横竖屏上传入口和底部四栏目均在屏幕内，信息截图目视确认 ZAC688 与 0.8.1-android.2。
- 最终运行 `tools/test-all.ps1 -VisiblePerformanceTests`：**569 项项目回归、52 项前端单测全部通过**，569 项用时 1095.65 秒（18 分 15 秒），0 失败、0 错误、0 跳过；类型、lint、构建退出码均为 0。另有 15 项原谱面回归、7 项 Java 文件测试、4KB／16KB 各 9 项原生测试通过，共 **661 个测试执行结果通过**；跨两种页大小重复执行的九项明确分别统计。包完整性等 11 项检查和原生工具／判定器 28 项单测已计入 569 项，不重复累加。持续响应与覆盖升级另列为集成验收。Android lint 为 0 错误、1 条原有 JavaScript 提示，Python 回归保留一条原有依赖弃用提示。
- 本机交付包：`release/android-test-0.8.1-android.2/ADOFAI-Cover-Studio-0.8.1-android.2-test.apk`，159189872 字节，SHA-256 `57034894264caa267eaf0406113a0b1ffd004c4437754858a0d03e5c0aa861cb`。新版 ARM64 库已全部静态审计，但 16KB 原生运行验证使用 x86_64 模拟器，不能代替不同品牌 ARM64 实机验证。
- 证据位于本机 `artifacts/android/16kb`，包含各轮失败日志、两个最终原生结果、升级结果、签名包截图、完整 ELF 明细、单测和最终回归报告。测试私有截图、AndroidTest APK、签名密钥和用户数据库不进入交付包。

补充官方依据：[Android 16KB 指南](https://developer.android.com/guide/practices/page-sizes)、[Chaquopy 16KB 支持及旧 wheel 限制](https://chaquo.com/chaquopy/chaquopy-version-17-0-0/)、[官方 OpenBLAS 0.3.33 构建](https://github.com/chaquo/chaquopy/pull/1457)、[Python 官方 NuGet 构建工具说明](https://docs.python.org/3.13/using/windows.html#the-nuget-org-packages)。

## GitHub 安卓测试版发布 · 2026-11-20

- 用户授权将安卓版更新发布到现有公开仓库。安卓源码以普通快进推送同步到 `main`，仅包含公开源码基线之后的八次安卓开发提交，不推送旧私有历史或其他本地引用。
- [发布页：v0.8.1-android.2](https://github.com/ZAC688/Adofai-Cover-Studio/releases/tag/v0.8.1-android.2)。附件为上述同一签名 APK 及 `.sha256` 文件，GitHub 服务器端提供的两个 SHA-256 均与本机文件逐字节哈希一致。
- 按安卓测试版发布，说明系统要求、覆盖升级、测试范围和实机复测状态；Windows v0.8.1 仍保留为稳定最新版。私人验收素材、测试 APK 和签名密钥不上传。
