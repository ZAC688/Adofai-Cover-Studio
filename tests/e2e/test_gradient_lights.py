import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .test_effects import pixels,open_effects,color
from .test_editor import select,upload_track
from .test_export import export


def number(page,label,value):
    page.get_by_label(label,exact=True).fill(str(value));page.locator('.panel-heading').first.click()


def configure_gradient(page):
    open_effects(page);page.get_by_label('渐变填充开关',exact=True).check()
    color(page,'渐变填充颜色','#ff0000');color(page,'渐变终点颜色','#0000ff');number(page,'渐变方向',0)
    page.get_by_label('渐变填充开关',exact=True).uncheck()


def test_all_six_lights_follow_gradient_colors_direction_with_fill_disabled(edge_page):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('MMMMMMMM')
    number(page,'发光强度',0);color(page,'文字颜色','#505050');configure_gradient(page)
    for name in ['外发光','内发光','多尺度 Bloom','发光描边','斜面高光','水平模糊']:
        page.get_by_label(name+'开关',exact=True).check();color(page,name+'颜色','#00ff00');flat=pixels(page)
        page.get_by_label(name+'跟随渐变填充',exact=True).check();horizontal=pixels(page)
        assert np.count_nonzero(np.any(horizontal!=flat,axis=2))>20,name
        page.get_by_label('渐变填充开关',exact=True).check();number(page,'渐变方向',90)
        page.get_by_label('渐变填充开关',exact=True).uncheck();vertical=pixels(page)
        assert np.count_nonzero(np.any(vertical!=horizontal,axis=2))>20,name+' direction'
        page.get_by_label(name+'跟随渐变填充',exact=True).uncheck()
        expect(page.get_by_label(name+'颜色',exact=True)).to_have_value('#00ff00')
        np.testing.assert_array_equal(pixels(page),flat)
        page.get_by_label(name+'开关',exact=True).uncheck()
        page.get_by_label('渐变填充开关',exact=True).check();number(page,'渐变方向',0)
        page.get_by_label('渐变填充开关',exact=True).uncheck()


def test_track_gradient_light_persists_independently_and_matches_export(edge_page,running_app,tmp_path):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('独立标题');upload_track(page)
    configure_gradient(page);page.get_by_label('多尺度 Bloom开关',exact=True).check()
    page.get_by_label('多尺度 Bloom跟随渐变填充',exact=True).check();before=pixels(page)
    saved=running_app['client'].get('/api/project').json()['project']
    assert saved['trackEffects']['bloom']['followGradient']
    assert saved['titles'][0]['effects'] is None
    page.reload();select(page,'轨道图形');open_effects(page)
    expect(page.get_by_label('多尺度 Bloom跟随渐变填充',exact=True)).to_be_checked()
    expect(page.get_by_label('渐变填充开关',exact=True)).not_to_be_checked()
    np.testing.assert_array_equal(pixels(page),before)
    export(page,tmp_path/'gradient-glow.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'gradient-glow.png')),before)
