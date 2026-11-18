# 安卓版开发与验收记录

## 已确认范围

基于 0.8.1，保留现有用户功能并交付可直接安装的测试 APK。主要验收机型为 OPPO Reno12，系统版本待实机核对。横屏、竖屏自动调整布局；预览与底部功能标签组合，对象、属性、光效、滤镜可切换，参数可滚动。保留离线、免登录、本机保存和正常退出、重启后的恢复行为。不包含应用商店上架、账号和云同步。Windows 版继续维护。

## 执行顺序与阶段验收

1. **运行基础**：确认 Android 原生依赖；建立可复现构建、独立应用数据目录、离线页面和处理服务。验证实际 Android 引擎启动、依赖导入、健康检查、完整资源和无远程依赖。当前进行中。
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

## 官方资料

- [Android WebView](https://developer.android.com/develop/ui/views/layout/webapps/webview)
- [Chaquopy 插件](https://chaquo.com/chaquopy/doc/current/android.html)
- [Chaquopy 原生包仓库](https://chaquo.com/pypi-13.1/)
- [Android 命令行工具](https://developer.android.com/studio#command-tools)
