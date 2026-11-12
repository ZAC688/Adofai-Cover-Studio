import numpy as np
from playwright.sync_api import sync_playwright,expect

from .test_desktop_runtime import start_desktop,stop_desktop,post_close
from .test_effects import pixels,color
from .test_filters import panel,add_filter
from .test_objects import number


def assert_native_text_presets(tmp_path,binary=None):
    host=start_desktop(tmp_path,binary=binary)
    try:
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{host["debug"]}',no_defaults=True,timeout=15000)
            page=browser.contexts[0].pages[0];page.set_viewport_size({'width':1440,'height':1000})
            expect(page.get_by_label('标题内容',exact=True)).to_be_visible(timeout=30000)
            page.get_by_label('标题内容',exact=True).fill('NATIVE PRESET')
            page.get_by_label('字体',exact=True).select_option('inter');number(page,'字号',95)
            color(page,'文字颜色','#c87ef5')
            page.get_by_role('button',name='3D文字模式',exact=True).click();number(page,'3D厚度 (%)',38)
            panel(page);entry=add_filter(page,'AdjustmentFilter');entry.get_by_label('亮度',exact=True).fill('.8')
            expected=pixels(page)
            page.get_by_label('文字预设名称').fill('原生三维样式')
            page.get_by_role('button',name='保存为文字预设',exact=True).click()
            expect(page.get_by_text('文字预设已保存到本机',exact=True)).to_be_visible()
            key=page.get_by_label('本机文字预设').input_value()
            page.get_by_role('button',name='对象属性',exact=True).click()
            page.get_by_role('button',name='3D文字模式',exact=True).click();number(page,'字号',45)
            changed=pixels(page);assert np.any(changed!=expected)
            panel(page);page.get_by_label('本机文字预设').select_option(key)
            page.get_by_role('button',name='应用文字预设',exact=True).click()
            expect(page.get_by_text('已应用文字预设，可撤销',exact=True)).to_be_visible()
            np.testing.assert_array_equal(pixels(page),expected)
            page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),changed)
            page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),expected)
            post_close(host);host['process'].wait(timeout=30);assert host['process'].returncode==0
        stop_desktop(host);host=start_desktop(tmp_path,binary=binary)
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{host["debug"]}',no_defaults=True,timeout=15000)
            page=browser.contexts[0].pages[0];page.set_viewport_size({'width':1440,'height':1000})
            expect(page.get_by_label('标题内容',exact=True)).to_be_visible(timeout=30000)
            np.testing.assert_array_equal(pixels(page),expected)
            panel(page);expect(page.get_by_label('本机文字预设').locator('option')).to_have_count(2)
            page.screenshot(path='artifacts/upgrade-08/04-text-presets/native-window.png')
        token=host['client'].get(host['url']+'/api/session').json()['token']
        item=host['client'].get(host['url']+'/api/text-presets/'+key).json()
        assert item['style']['text3d']['depth']==38 and 'text' not in item['style']
        assert host['client'].get(host['url']+'/api/project',headers={'x-editor-token':token}).json()['project']['titles'][0]['text']=='NATIVE PRESET'
    finally:stop_desktop(host)


def test_native_engine_text_presets_render_undo_and_restart_exactly(tmp_path):
    assert_native_text_presets(tmp_path)
