import json
import sqlite3
import time

from playwright.sync_api import sync_playwright,expect
from tests.e2e.test_desktop_runtime import start_desktop,stop_desktop,post_close
from tests.e2e.test_effects import pixels
from tests.backend.test_charts import chart_bytes
from .conftest import BUNDLE


def test_bundle_contains_its_own_engine_and_chart_editor_template():
    assert list(BUNDLE.rglob('QtWebEngineProcess.exe'))
    assert list(BUNDLE.rglob('Qt6WebEngineCore.dll'))
    assert list(BUNDLE.rglob('icudtl.dat'))
    assert list(BUNDLE.rglob('qtwebengine_resources.pak'))
    assert (BUNDLE/'_internal/experiments/static_track_editor.html').is_file()
    assert not list(BUNDLE.rglob('msedge.exe'))
    assert not (BUNDLE/'_internal/icuuc.dll').exists(), 'Qt must use Windows ICU, not a foreign developer-tool DLL'


def test_frozen_desktop_without_browser_runs_chart_generation_and_flushes_close(tmp_path):
    host=start_desktop(tmp_path,binary=BUNDLE/'ADOFAI-Cover-Studio.exe')
    try:
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{host["debug"]}',no_defaults=True,timeout=15000)
            page=browser.contexts[0].pages[0]
            page.set_viewport_size({'width':1440,'height':1000})
            expect(page.get_by_label('标题内容',exact=True)).to_be_visible(timeout=30000)
            assert 'QtWebEngine' in page.evaluate('navigator.userAgent')
            page.get_by_role('button',name='从谱面生成',exact=True).click()
            page.get_by_label('谱面文件',exact=True).set_input_files({'name':'frozen.adofai','mimeType':'application/json','buffer':chart_bytes()})
            frame=page.frame_locator('iframe[title="轨道选段工具"]')
            expect(frame.locator('#track-style')).to_have_value('gold')
            frame.locator('#resolution').select_option('1920')
            frame.get_by_role('button',name='生成并预览',exact=True).click()
            expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=30000)
            page.get_by_role('button',name='导出轨道 PNG',exact=True).click()
            track_file=host['downloads']/'轨道-0-14-1920.png'
            deadline=time.monotonic()+20
            while not track_file.is_file():
                assert time.monotonic()<deadline,'Frozen native track download missing'
                time.sleep(.1)
            from PIL import Image
            with Image.open(track_file) as image:assert max(image.size)==1920
            page.get_by_role('button',name='应用到封面',exact=True).click();pixels(page)
            page.locator('[data-object-id=title1]').click()
            page.get_by_label('标题内容',exact=True).fill('分发包关闭前输入')
            post_close(host);host['process'].wait(timeout=30)
            assert host['process'].returncode==0
        with sqlite3.connect(host['data']/'project.sqlite3') as db:
            document=json.loads(db.execute('SELECT document FROM project').fetchone()[0])
        assert document['titles'][0]['text']=='分发包关闭前输入'
        assert document['generatedTrack']['style']=='gold'
        assert list((host['data']/'charts').glob('*.adofai'))
    finally:stop_desktop(host)
