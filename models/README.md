# P0 模型候选

此处仅存放实验候选，不表示已选定正式轨道识别模型。

- 文件：`u2netp.onnx`
- 用途：通用显著物体分割对照，不具备已验证的 ADOFAI 专用语义能力。
- 下载来源：https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx
- 上游模型：https://github.com/xuebinqin/U-2-Net
- 上游说明：https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2netp.py
- 字节数：4574861
- SHA-256：`309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8`
- 上游仓库许可：Apache-2.0；附上游 LICENSE，正式分发前仍需完成全部依赖及模型资源的归档核对。

推理只读取显式指定的本地文件，缺失或校验不符会报错，不自动联网下载。

参考截图的候选结果仍包含球体和拖尾；当前未获得完整参考蒙版，不能据此声称达到 90%／5% 的正式验收标准。
