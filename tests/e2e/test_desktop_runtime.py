"""Real bundled-engine tests: no installed browser is launched for these pages."""
import ctypes
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time

import httpx
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright,expect
import pytest

from .conftest import ROOT
from .test_effects import pixels
from .test_filters import panel,add_filter
from tests.backend.test_charts import chart_bytes


def post_close(host):
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.IsWindow.argtypes=[ctypes.c_void_p]
    deadline=time.monotonic()+10
    while True:
        state=json.loads(host['ready'].read_text(encoding='utf-8'))
        handle=state['windowHandle']
        if user.IsWindow(handle):break
        assert time.monotonic()<deadline,'Desktop window handle was not refreshed after initialization'
        time.sleep(.1)
    function=user.PostMessageW
    function.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    assert function(handle,0x0010,0,0)


def start_desktop(directory,*,binary=None,visible=False):
    directory.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));debug=sock.getsockname()[1]
    data=directory/'本机作品 with spaces';ready=directory/'ready.json';downloads=directory/'downloads'
    ready.unlink(missing_ok=True)
    executable=[str(binary)] if binary else [sys.executable,'-m','backend.launcher']
    command=executable+['--data-dir',str(data),'--ready-file',str(ready),
        '--desktop-debug-port',str(debug),'--download-dir',str(downloads)]
    if not visible:command.append('--desktop-hidden')
    environment=dict(os.environ);environment['PATH']=r'C:\Windows\System32;C:\Windows'
    log=(directory/'desktop.log').open('wb')
    process=subprocess.Popen(command,cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    client=httpx.Client(trust_env=False,timeout=5)
    deadline=time.monotonic()+75
    try:
        while True:
            if process.poll() is not None:
                log.flush();pytest.fail('Desktop stopped: '+(directory/'desktop.log').read_text(encoding='utf-8',errors='replace'))
            assert time.monotonic()<deadline,'Desktop failed to start; '+str(directory/'desktop.log')
            try:
                state=json.loads(ready.read_text(encoding='utf-8'))
                if state.get('windowHandle') and client.get(f'http://127.0.0.1:{debug}/json/version').status_code==200:break
            except (OSError,ValueError,httpx.HTTPError):pass
            time.sleep(.1)
        return {'process':process,'data':data,'ready':ready,'state':state,'debug':debug,'downloads':downloads,
                'url':f'http://127.0.0.1:{state["port"]}','log':log,'client':client}
    except Exception:
        process.terminate();process.wait(timeout=15);log.close();client.close();raise


def stop_desktop(host):
    process=host['process']
    if process.poll() is None:
        try:
            token=host['client'].get(host['url']+'/api/session').json()['token']
            host['client'].post(host['url']+'/api/shutdown',headers={'x-editor-token':token})
            process.wait(timeout=20)
        except (httpx.HTTPError,subprocess.TimeoutExpired):process.terminate();process.wait(timeout=15)
    host['log'].close();host['client'].close()


@pytest.fixture
def desktop(tmp_path):
    host=start_desktop(tmp_path)
    try:
        with sync_playwright() as p:
            host['playwright']=p
            browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{host["debug"]}',no_defaults=True,timeout=15000)
            context=browser.contexts[0]
            page=next((page for page in context.pages if page.url.startswith(host['url'])),context.pages[0])
            page.set_viewport_size({'width':1440,'height':1000})
            page.wait_for_url(host['url']+'/',timeout=30000)
            expect(page.get_by_label('标题内容',exact=True)).to_be_visible(timeout=30000)
            yield host,page
    finally:stop_desktop(host)


def test_native_close_flushes_pending_edits_and_relaunch_restores(desktop,tmp_path):
    host,page=desktop
    assert 'QtWebEngine' in page.evaluate('navigator.userAgent')
    page.get_by_label('标题内容',exact=True).fill('关闭窗口前立即输入的内容')
    post_close(host)
    host['process'].wait(timeout=30)
    assert host['process'].returncode==0
    with sqlite3.connect(host['data']/'project.sqlite3') as db:
        document=json.loads(db.execute('SELECT document FROM project').fetchone()[0])
    assert document['titles'][0]['text']=='关闭窗口前立即输入的内容'
    # Reuse the same actual data directory through the normal source entry.
    host['log'].close()
    again=start_desktop(tmp_path)
    try:
        browser=host['playwright'].chromium.connect_over_cdp(f'http://127.0.0.1:{again["debug"]}',no_defaults=True,timeout=15000)
        other=browser.contexts[0].pages[0]
        other.set_viewport_size({'width':1440,'height':1000})
        expect(other.get_by_label('标题内容',exact=True)).to_have_value('关闭窗口前立即输入的内容',timeout=30000)
        post_close(again);again['process'].wait(timeout=30)
    finally:stop_desktop(again)


def test_native_close_refuses_to_discard_failed_save(desktop):
    host,page=desktop
    page.route('**/api/project',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"测试保存失败"}') if route.request.method=='PUT' else route.continue_())
    page.get_by_label('标题内容',exact=True).fill('保存失败也必须保留')
    post_close(host)
    page.wait_for_function('window.__desktopCloseFailed===true',timeout=30000,polling=100)
    assert host['process'].poll() is None
    expect(page.get_by_label('标题内容',exact=True)).to_have_value('保存失败也必须保留')
    page.unroute('**/api/project')
    page.get_by_role('button',name='重试保存',exact=True).click()
    expect(page.get_by_text('已保存到本机',exact=True)).to_be_visible()
    post_close(host);host['process'].wait(timeout=30)


def test_embedded_engine_supports_3d_filters_chart_preview_and_native_png_download(desktop,tmp_path):
    host,page=desktop
    page.get_by_label('标题内容',exact=True).fill('DESKTOP 冰与火')
    plain=pixels(page)
    page.get_by_role('button',name='3D文字模式',exact=True).click()
    three=pixels(page);assert np.any(three!=plain)
    panel(page);add_filter(page,'GrayscaleFilter');filtered=pixels(page);assert np.any(filtered!=three)
    page.get_by_role('button',name='从谱面生成',exact=True).click()
    page.get_by_label('谱面文件',exact=True).set_input_files({'name':'desktop.adofai','mimeType':'application/json','buffer':chart_bytes()})
    frame=page.frame_locator('iframe[title="轨道选段工具"]')
    expect(frame.locator('#track-style')).to_have_value('gold')
    frame.locator('#resolution').select_option('1920');frame.get_by_role('button',name='生成并预览',exact=True).click()
    expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=30000)
    page.get_by_role('button',name='导出轨道 PNG',exact=True).click()
    track_file=host['downloads']/'轨道-0-14-1920.png'
    deadline=time.monotonic()+20
    while not track_file.is_file():
        assert time.monotonic()<deadline,'Native track PNG download was not created'
        time.sleep(.1)
    with Image.open(track_file) as track_image:assert max(track_image.size)==1920
    page.get_by_role('button',name='应用到封面',exact=True).click();expected=pixels(page)
    page.get_by_role('button',name='导出图片',exact=False).click()
    dialog=page.get_by_role('dialog',name='导出图片')
    dialog.get_by_label('导出文件名').fill('desktop-export')
    dialog.get_by_role('button',name='导出到电脑').click()
    target=host['downloads']/'desktop-export.png'
    deadline=time.monotonic()+20
    while not target.is_file() or target.stat().st_size<100:
        assert time.monotonic()<deadline,'Native download was not created'
        time.sleep(.1)
    # Qt download completion is separate from file creation.
    for _ in range(50):
        try:
            with Image.open(target) as image:actual=np.array(image);break
        except OSError:time.sleep(.1)
    np.testing.assert_array_equal(actual,expected)
    page.screenshot(path='artifacts/upgrade-07/02-desktop/embedded-window.png')
    post_close(host);host['process'].wait(timeout=30)


def test_exit_button_flushes_and_closes_native_window(desktop):
    host,page=desktop
    page.get_by_label('标题内容',exact=True).fill('退出按钮保存检查')
    page.get_by_role('button',name='退出程序',exact=True).click()
    host['process'].wait(timeout=30)
    assert host['process'].returncode==0
    with sqlite3.connect(host['data']/'project.sqlite3') as db:
        document=json.loads(db.execute('SELECT document FROM project').fetchone()[0])
    assert document['titles'][0]['text']=='退出按钮保存检查'
