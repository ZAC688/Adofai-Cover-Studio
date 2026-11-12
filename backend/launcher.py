from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import socket
import sys
import threading
import time
from urllib.request import urlopen

import uvicorn
from experiments.p0 import resource_root, validate_model
from backend.app.api import create_app


def default_data_dir() -> Path:
    if os.name != "nt":
        raise RuntimeError("第一版仅支持 Windows")
    buffer = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 28, None, 0, buffer) != 0:
        raise RuntimeError("无法找到 Windows 本地应用数据目录")
    return Path(buffer.value) / "AdofaiThumbnailGenerator"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument('--desktop-hidden',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--desktop-debug-port',type=int,default=0,help=argparse.SUPPRESS)
    parser.add_argument('--download-dir',type=Path,help=argparse.SUPPRESS)
    args = parser.parse_args()
    data_dir = (args.data_dir or default_data_dir()).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    runtime = data_dir / "runtime.json"
    mutex_name = "Local\\AdofaiCover_" + hashlib.sha256(str(data_dir).encode()).hexdigest()[:24]
    kernel = ctypes.windll.kernel32
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = kernel.CreateMutexW(None, False, mutex_name)
    if not mutex:
        raise RuntimeError("无法创建本地程序实例")
    already_started = kernel.GetLastError() == 183
    try:
        if already_started:
            for _ in range(100):
                try:
                    existing = json.loads(runtime.read_text(encoding="utf-8"))
                    with urlopen(f"http://127.0.0.1:{existing['port']}/api/health", timeout=1) as response:
                        health = json.load(response)
                    if health.get("application") == "adofai-cover-editor" and health.get("instance") == existing["instance"]:
                        if args.ready_file:
                            args.ready_file.write_text(json.dumps(existing), encoding="utf-8")
                        if not args.no_browser:
                            from backend.desktop import activate_window
                            if not activate_window(existing['pid']):raise RuntimeError('已有本机服务正在运行，请先从旧版窗口点击“退出程序”')
                        return 0
                except (OSError, ValueError, KeyError):
                    time.sleep(.1)
            raise RuntimeError("已有实例未响应；请从原窗口退出后重试")
        root = resource_root()
        frontend = root / "frontend/dist"
        if not (frontend / "index.html").is_file():
            raise RuntimeError("界面资源缺失，请使用完整程序包")
        try:
            validate_model(root / "models/u2netp.onnx")
        except (FileNotFoundError, ValueError) as error:
            raise RuntimeError("本地识别资源缺失或校验失败，请使用完整程序包") from error
        app = create_app(data_dir, frontend)
        instance = secrets.token_hex(16)
        app.state.instance = instance
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False, log_config=None))
        app.state.shutdown = lambda: setattr(server, "should_exit", True)
        state = {"port": port, "pid": os.getpid(), "instance": instance,'desktop':not args.no_browser}
        state_lock=threading.Lock()
        def publish():
            if not server.started:return
            with state_lock:
                runtime.write_text(json.dumps(state),encoding='utf-8')
                if args.ready_file:
                    args.ready_file.parent.mkdir(parents=True,exist_ok=True)
                    args.ready_file.write_text(json.dumps(state),encoding='utf-8')
        def announce():
            while not server.started and not server.should_exit:
                time.sleep(.02)
            if not server.started:
                return
            publish()
        thread = threading.Thread(target=announce, daemon=True)
        thread.start()
        try:
            if args.no_browser:
                server.run(sockets=[listener])
            else:
                from backend.desktop import run_desktop
                service=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True)
                service.start()
                def window_ready(handle):state['windowHandle']=handle;publish()
                try:
                    return run_desktop(port,data_dir,is_ready=lambda:server.started,stop=lambda:setattr(server,'should_exit',True),on_window=window_ready,
                        hidden=args.desktop_hidden,debug_port=args.desktop_debug_port,download_dir=args.download_dir)
                finally:
                    server.should_exit=True;service.join(timeout=30)
        finally:
            listener.close()
            runtime.unlink(missing_ok=True)
        return 0
    finally:
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
