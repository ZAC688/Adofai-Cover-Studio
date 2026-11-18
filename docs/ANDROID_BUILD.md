# 安卓构建与测试

此文档面向开发者。用户安装 APK 不需要安装这些工具。当前原生运行验收尚未完成，结果以 `ANDROID_PROGRESS.md` 为准。

## 构建准备

使用 JDK 17、项目现有 Python 3.10 虚拟环境与 Node.js。先按项目锁文件安装前端及 Windows 开发依赖。构建脚本读取 `ADOFAI_JAVA_HOME`／`JAVA_HOME`，或已安装的 JDK 17。

1. 运行 `.venv/Scripts/python.exe tools/bootstrap_android.py`，下载并按固定官方 SHA-256 校验 Android 命令行工具和 Gradle 8.11.1。可用 `--proxy` 指定仅本次下载使用的代理。
2. 设置 `ANDROID_HOME` 为当前项目下的 `tools/android-sdk`，用其中的 `cmdline-tools/latest/bin/sdkmanager.bat` 接受许可并安装 `platform-tools`、`platforms;android-35`、`build-tools;35.0.0`。
3. 运行 `./tools/build-android.ps1 -Task assembleDebug`。输出位于 `android/app/build/outputs/apk/debug/app-debug.apk`，包名带 `.debug`，与用户版数据隔离。
4. 运行 `./tools/build-android.ps1 -Task assembleRelease`。输出位于 `android/app/build/outputs/apk/release/app-release.apk`，包名为 `com.zac688.adofaicoverstudio`，版本 `0.8.1-android.1`，最低 Android 10，包含 ARM64／x86_64。

首次 release 构建会创建本地专用签名密钥，以后验证并复用；不完整或不匹配时停止构建，不能静默换新密钥。请离线备份整个 `android/signing` 目录。它被 Git 忽略，密码不会打印，不能放入源码、APK 或公开附件；丢失密钥会影响以后覆盖升级。

构建需要联网获取官方依赖，成品应用离线运行。可按环境设置进程级 `HTTPS_PROXY`；不得关闭证书验证。Java 网络若需要固定协议，可设置进程级 `JAVA_TOOL_OPTIONS=-Dhttps.protocols=TLSv1.2 -Djdk.tls.client.protocols=TLSv1.2`。

## 自动化检查

- `./tools/test-all.ps1 -VisiblePerformanceTests`：前端类型、lint、单测、构建，以及全部 Python、浏览器和 Windows 成品回归；可见窗口只编辑临时作品。
- `./tools/build-android.ps1 -Task testDebugUnitTest`：真实 Java 文件字节、分块顺序、大小、文件名、取消、缓存和重建恢复测试。
- `./tools/build-android.ps1 -Task lintDebug`：安卓静态检查。
- `.venv/Scripts/python.exe -m pytest tests/android/test_packaging.py`：两架构 ELF、两个 APK 签名、完整离线资源 SHA、私人素材排除和 release 签名身份；需先构建两个包。

前端构建会替换 `frontend/dist`，不能与读取该目录的浏览器测试并发执行。Windows 已发布成品包不因安卓构建而重打包；其回归使用原成品和独立临时数据目录。

## 原生模拟器检查

安装 SDK `emulator` 与 `system-images;android-35;google_apis;x86_64`，使用项目专属 AVD 数据目录 `.testdata/android-avd`。Windows 建议使用 WHPX；更改 Windows 组件后可能需要用户手动重启。不要为了测试自动重启电脑。

1. 用 `emulator -accel-check` 验证加速可用；启动专用 `adofai-api35`，等待 `adb shell getprop sys.boot_completed` 为 `1`。本机已有的 AVD 位于上述隔离目录，设置 `ANDROID_AVD_HOME` 后使用。
2. 运行 `./tools/build-android.ps1 -Task assembleDebugAndroidTest`，生成私有原生测试 APK。此包含已批准的九组识别验收截图与蒙版，**不能向用户交付或公开上传**。
3. 执行 `.venv/Scripts/python.exe tools/test_android_device.py --serial emulator-5562`，将编号替换为专用模拟器实际编号。脚本拒绝物理手机，只安装隔离 `.debug` 应用，运行八项 Android 原生测试并验证真实进程停止／重开后的 SQLite 作品恢复。

原生用例包括 Python 原生依赖导入、WebView／WebGL 2、真实 three.js／Pixi 全分辨率像素变化、内嵌谱面窗口实际生成金色透明轨道、Java ONNX Runtime 与原模型数值对照、九张标注各自 IoU ≥90%、实际系统保存 PNG 及取消、真实数据库读回。日志和失败状态保存在本地 `artifacts/android/native`，不具备运行条件时明确失败，不能算作通过或跳过。

最终在 OPPO Reno12 上按 [实机清单](ANDROID_ACCEPTANCE.md) 验收，模拟器结果不能代替手机实测。
