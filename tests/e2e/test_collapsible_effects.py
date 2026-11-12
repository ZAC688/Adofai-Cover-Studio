import numpy as np
import pytest
from PIL import Image
from playwright.sync_api import expect
from .test_editor import upload_track
from .test_effects import pixels,open_effects,color
from .test_export import export


@pytest.mark.parametrize('target',['text','track'])
def test_collapsing_parameters_keeps_effect_pixels_settings_and_switches(edge_page,running_app,tmp_path,target):
    page=edge_page
    if target=='track':upload_track(page)
    else:page.get_by_label('标题内容',exact=True).fill('折叠仍然发光')
    page.get_by_label('发光强度',exact=True).fill('42');page.locator('.panel-heading').first.click()
    basic=pixels(page)
    page.get_by_role('button',name='基础发光设置',exact=False).click()
    expect(page.get_by_label('发光强度',exact=True)).to_have_count(0)
    np.testing.assert_array_equal(pixels(page),basic)
    page.get_by_role('button',name='基础发光设置',exact=False).click()
    expect(page.get_by_label('发光强度',exact=True)).to_have_value('42')
    open_effects(page);page.get_by_label('多尺度 Bloom开关',exact=True).check()
    page.get_by_label('多尺度 Bloom强度',exact=True).fill('81')
    page.get_by_label('多尺度 Bloom半径',exact=True).fill('27');color(page,'多尺度 Bloom颜色','#dd44aa')
    page.locator('.panel-heading').first.click();before=pixels(page)
    saved=running_app['client'].get('/api/project').json()
    page.get_by_role('button',name='多尺度 Bloom参数',exact=True).click()
    expect(page.get_by_role('button',name='多尺度 Bloom参数',exact=True)).to_have_attribute('aria-expanded','false')
    expect(page.get_by_label('多尺度 Bloom强度',exact=True)).to_have_count(0)
    expect(page.get_by_label('多尺度 Bloom开关',exact=True)).to_be_checked()
    expect(page.get_by_label('外发光强度',exact=True)).to_be_visible()
    np.testing.assert_array_equal(pixels(page),before)
    assert running_app['client'].get('/api/project').json()==saved
    export(page,tmp_path/f'{target}-folded.png')
    np.testing.assert_array_equal(np.array(Image.open(tmp_path/f'{target}-folded.png')),before)
    page.get_by_label('多尺度 Bloom开关',exact=True).uncheck();assert np.any(pixels(page)!=before)
    page.get_by_label('多尺度 Bloom开关',exact=True).check()
    expect(page.get_by_label('多尺度 Bloom强度',exact=True)).to_have_value('81')
    expect(page.get_by_label('多尺度 Bloom半径',exact=True)).to_have_value('27')
    np.testing.assert_array_equal(pixels(page),before)
