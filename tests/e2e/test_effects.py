import base64
import io

import cv2
import numpy as np
from PIL import Image
from playwright.sync_api import expect

from .test_editor import saved,select,upload_track
from .test_export import export
from .conftest import ROOT


def color(page,label,value):
    page.get_by_label(label,exact=True).evaluate('''(input,value)=>{
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,value);
      input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
    }''',value)


def pixels(page):
    saved(page)
    expect(page.get_by_label('封面画布',exact=True)).to_have_attribute('aria-busy','false',timeout=20000)
    raw=page.get_by_label('封面画布',exact=True).evaluate("canvas=>canvas.toDataURL('image/png').split(',')[1]")
    return np.array(Image.open(io.BytesIO(base64.b64decode(raw))))


def open_effects(page):
    summary=page.locator('.effects-panel summary')
    if not page.locator('.effects-panel').evaluate('element=>element.open'):summary.click()


def test_each_effect_has_real_pixel_output_and_independent_toggle(edge_page,running_app):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('MASK 光效')
    page.get_by_label('发光强度',exact=True).fill('0')
    color(page,'文字颜色','#505050');page.locator('.panel-heading').first.click()
    baseline=pixels(page);open_effects(page)
    for name in ['外发光','内发光','多尺度 Bloom','发光描边','渐变填充','斜面高光','水平模糊']:
        page.get_by_label(name+'开关',exact=True).check()
        color(page,name+'颜色','#00ddff')
        enabled=pixels(page)
        assert np.count_nonzero(np.any(enabled!=baseline,axis=2))>20,name
        if name in ['外发光','多尺度 Bloom','发光描边','水平模糊']:
            background=np.all(baseline[:,:,:3]==[8,13,22],axis=2)
            assert np.any(enabled[background]!=baseline[background]),name+' must produce light outside the clear body'
        page.get_by_label(name+'开关',exact=True).uncheck()
        disabled=pixels(page)
        np.testing.assert_array_equal(disabled,baseline,err_msg=name+' must switch off independently')
    effects=running_app['client'].get('/api/project').json()['project']['titles'][0]['effects']
    assert all(not value['enabled'] for value in effects.values())


def test_external_stack_preserves_clear_body_and_gradient_direction_and_blends(edge_page,tmp_path):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('MMMM')
    page.get_by_label('发光强度',exact=True).fill('0')
    color(page,'文字颜色','#505050');page.locator('.panel-heading').first.click()
    baseline=pixels(page)
    core=cv2.erode(np.all(baseline[:,:,:3]==80,axis=2).astype('uint8'),np.ones((7,7),'uint8'))>0
    assert core.sum()>100
    open_effects(page)
    for name in ['外发光','多尺度 Bloom','发光描边','水平模糊']:
        page.get_by_label(name+'开关',exact=True).check();color(page,name+'颜色','#00ff88')
    screen=pixels(page)
    np.testing.assert_array_equal(screen[core],baseline[core])
    page.get_by_label('外发光混合模式').select_option('add')
    additive=pixels(page)
    assert np.any(additive!=screen)
    page.get_by_label('渐变填充开关').check();color(page,'渐变填充颜色','#ff0000');color(page,'渐变终点颜色','#0000ff')
    page.get_by_label('渐变方向',exact=True).fill('0');page.locator('.panel-heading').first.click()
    horizontal=pixels(page)
    page.get_by_label('渐变方向',exact=True).fill('90');page.locator('.panel-heading').first.click()
    vertical=pixels(page)
    assert np.count_nonzero(np.any(horizontal!=vertical,axis=2))>100
    export(page,tmp_path/'effects.png')
    np.testing.assert_array_equal(np.array(Image.open(tmp_path/'effects.png')),vertical)


def test_title_and_track_effects_are_separate_and_persist(edge_page,running_app):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('独立光效')
    open_effects(page);page.get_by_label('多尺度 Bloom开关').check();color(page,'多尺度 Bloom颜色','#ff0088')
    upload_track(page)
    open_effects(page);page.get_by_label('水平模糊开关').check();color(page,'水平模糊颜色','#00ffcc')
    pixels(page)
    document=running_app['client'].get('/api/project').json()['project']
    assert document['trackEffects']['horizontalBlur']['enabled']
    assert document['titles'][0]['effects']['bloom']['color']=='#ff0088'
    page.reload();select(page,'轨道图形');open_effects(page)
    expect(page.get_by_label('水平模糊开关')).to_be_checked()
    expect(page.get_by_label('水平模糊颜色')).to_have_value('#00ffcc')
    directory=ROOT/'artifacts/upgrade/02-effects';directory.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(directory/'editor.png'))
