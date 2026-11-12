"""Bundled Qt WebEngine desktop host. No installed browser or WebView2 dependency."""
from __future__ import annotations

import os
from pathlib import Path
import time
from urllib.parse import urlsplit


def permitted_url(url: str, port: int) -> bool:
    parsed=urlsplit(url)
    if parsed.scheme in {'about','data','blob','qrc'}:return True
    try:return parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port==port
    except ValueError:return False


def activate_window(pid: int) -> bool:
    import ctypes
    user=ctypes.windll.user32;found=[]
    callback_type=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
    user.EnumWindows.argtypes=[callback_type,ctypes.c_void_p]
    user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    user.IsWindowVisible.argtypes=[ctypes.c_void_p]
    user.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]
    user.SetForegroundWindow.argtypes=[ctypes.c_void_p]
    @callback_type
    def visit(handle,_):
        owner=ctypes.c_ulong();user.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        if owner.value==pid and user.IsWindowVisible(handle):found.append(handle)
        return True
    user.EnumWindows(visit,0)
    if not found:return False
    user.ShowWindow(found[0],9);user.SetForegroundWindow(found[0]);return True


def run_desktop(port: int, data_dir: Path, *, is_ready, stop, on_window=lambda _:None,
                hidden=False, debug_port=0, download_dir:Path|None=None) -> int:
    if debug_port:
        os.environ['QTWEBENGINE_REMOTE_DEBUGGING']=f'127.0.0.1:{debug_port}'
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS','--disable-background-networking --disable-component-update --no-first-run')
    from PySide6.QtCore import Qt,QTimer,QUrl,QStandardPaths,QEvent
    from PySide6.QtGui import QCloseEvent,QIcon
    from PySide6.QtWidgets import QApplication,QMainWindow,QFileDialog,QMessageBox
    from PySide6.QtWebEngineCore import QWebEnginePage,QWebEngineProfile,QWebEngineUrlRequestInterceptor,QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView

    from experiments.p0 import resource_root
    icon_path=resource_root()/'frontend/dist/app-icon.ico'
    if not icon_path.is_file():raise FileNotFoundError('程序图标缺失，请完整解压程序包')
    if os.name=='nt':
        import ctypes
        set_id=ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes=[ctypes.c_wchar_p];set_id.restype=ctypes.c_long
        if set_id('ZAC688.ADOFAICoverStudio')!=0:raise OSError('无法设置应用任务栏标识')
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    application=QApplication.instance() or QApplication([])
    application.setApplicationName('ADOFAI Cover Studio')
    icon=QIcon(str(icon_path));application.setWindowIcon(icon)

    class LocalOnly(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self,info):
            if not permitted_url(info.requestUrl().toString(),port):info.block(True)

    class LocalPage(QWebEnginePage):
        def acceptNavigationRequest(self,url,kind,is_main):
            return permitted_url(url.toString(),port)

    profile=QWebEngineProfile('adofai-cover',application)
    profile.setPersistentStoragePath(str(data_dir/'desktop-profile'))
    profile.setCachePath(str(data_dir/'desktop-cache'))
    interceptor=LocalOnly(profile);profile.setUrlRequestInterceptor(interceptor)
    page=LocalPage(profile)
    page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,False)
    page.settings().setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled,True)

    class Window(QMainWindow):
        def event(self,event):
            result=super().event(event)
            if event.type()==QEvent.Type.WinIdChange:
                handle=int(self.effectiveWinId() or 0)
                if handle:on_window(handle)
            return result
        def __init__(self):
            super().__init__();self.allow_close=False;self.pending_close=False;self.started=0
            self.setWindowTitle('ADOFAI 封面制作器');self.resize(1440,1000);self.setMinimumSize(1050,760)
            self.setWindowIcon(icon)
            self.view=QWebEngineView(self);self.view.setPage(page);self.setCentralWidget(self.view)
            self.poll=QTimer(self);self.poll.setInterval(100);self.poll.timeout.connect(self.check_close)
        def closeEvent(self,event:QCloseEvent):
            if self.allow_close:event.accept();QTimer.singleShot(0,application.quit);return
            event.ignore()
            if self.pending_close:return
            self.pending_close=True;self.started=time.monotonic()
            page.runJavaScript("window.__adofaiCloseState='pending';Promise.resolve(typeof window.adofaiCloseRequest==='function'?window.adofaiCloseRequest():true).then(ok=>window.__adofaiCloseState=ok?'saved':'failed').catch(()=>window.__adofaiCloseState='failed');")
            self.poll.start()
        def check_close(self):
            page.runJavaScript('window.__adofaiCloseState',self.close_result)
        def close_result(self,result):
            if not self.pending_close:return
            if result=='saved':
                self.pending_close=False;self.poll.stop();self.allow_close=True;stop();self.close()
            elif result=='failed' or time.monotonic()-self.started>25:
                self.pending_close=False;self.poll.stop()
                if hidden:page.runJavaScript('window.__desktopCloseFailed=true')
                else:QMessageBox.warning(self,'作品尚未保存','本机保存尚未成功，窗口已保留。请检查错误提示并重试保存，再关闭窗口。')

    window=Window()
    def loaded(_):
        on_window(int(window.winId()))
        if hidden:page.setVisible(True)
    page.loadFinished.connect(loaded)
    def download(request):
        suggested=Path(request.suggestedFileName().replace('\\','/')).name or '封面.png'
        if download_dir:
            download_dir.mkdir(parents=True,exist_ok=True);target=download_dir/suggested
        else:
            directory=QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
            chosen,_=QFileDialog.getSaveFileName(window,'保存文件',str(Path(directory)/suggested))
            if not chosen:request.cancel();return
            target=Path(chosen)
        request.setDownloadDirectory(str(target.parent));request.setDownloadFileName(target.name);request.accept()
    profile.downloadRequested.connect(download)
    page.windowCloseRequested.connect(window.close)
    if not hidden:window.show()
    else:
        # Exercise a real compositor without placing a test window on the user's
        # screen or taskbar. Merely keeping a QWidget hidden gives it no surface.
        window.setWindowFlag(Qt.WindowType.Tool,True)
        window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating,True)
        window.move(-20000,-20000);window.show();page.setVisible(True)
    on_window(int(window.winId()))
    boot=QTimer(application);boot.setInterval(50)
    exit_watch=QTimer(application);exit_watch.setInterval(500)
    def watch():
        if hidden:page.setVisible(True)
        page.runJavaScript('window.adofaiShutdownComplete === true',lambda done:window.close() if done else None)
    exit_watch.timeout.connect(watch)
    deadline=time.monotonic()+40
    def load():
        if is_ready():boot.stop();page.setUrl(QUrl(f'http://127.0.0.1:{port}/'));exit_watch.start()
        elif time.monotonic()>deadline:
            boot.stop();QMessageBox.critical(window,'启动失败','本机编辑服务未能启动，请查看数据目录中的启动日志。');window.allow_close=True;window.close()
    boot.timeout.connect(load);boot.start()
    application.aboutToQuit.connect(stop)
    result=application.exec()
    window.view.setPage(QWebEnginePage(window.view))
    page.deleteLater();profile.deleteLater();application.processEvents()
    return result
