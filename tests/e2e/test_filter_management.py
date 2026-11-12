import json
import numpy as np
from playwright.sync_api import expect
from .test_filters import fixture_track, panel, add_filter
from .test_effects import pixels
from .test_objects import row
from .conftest import ROOT


def test_filter_folding_and_reset_preserve_scope_history_and_pixels(edge_page,running_app,tmp_path):
    page=edge_page;baseline=fixture_track(page,tmp_path);panel(page)
    entry=add_filter(page,'AdjustmentFilter')
    entry.get_by_label('滤镜局部区域',exact=True).select_option('rect')
    defaulted=pixels(page)
    entry.get_by_label('亮度',exact=True).fill('.4')
    changed=pixels(page);assert np.any(changed!=baseline)
    stored=running_app['client'].get('/api/project').json()['project']['filters'][0]
    entry.locator('summary').click()
    expect(entry.get_by_label('亮度',exact=True)).not_to_be_visible()
    np.testing.assert_array_equal(pixels(page),changed)
    page.get_by_role('button',name='滤镜列表',exact=True).click()
    expect(page.locator('.filter-entry')).to_have_count(0)
    np.testing.assert_array_equal(pixels(page),changed)
    page.get_by_role('button',name='滤镜列表',exact=True).click()
    expect(entry).not_to_have_attribute('open','')
    entry.locator('summary').click()
    entry.get_by_role('button',name='恢复默认参数',exact=True).click()
    np.testing.assert_array_equal(pixels(page),defaulted)
    reset=running_app['client'].get('/api/project').json()['project']['filters'][0]
    catalog=json.loads((ROOT/'frontend/public/filter-catalog.json').read_text(encoding='utf-8'))['filters']
    defaults={f['key']:f['value'] for f in next(x for x in catalog if x['type']=='AdjustmentFilter')['fields']}
    assert reset['params']==defaults
    assert {k:v for k,v in reset.items() if k!='params'}=={k:v for k,v in stored.items() if k!='params'}
    page.get_by_role('button',name='撤销',exact=True).click()
    np.testing.assert_array_equal(pixels(page),changed)
    page.get_by_role('button',name='重做',exact=True).click()
    np.testing.assert_array_equal(pixels(page),defaulted)


def test_selected_object_and_canvas_manage_separate_filter_lists(edge_page,running_app,tmp_path):
    page=edge_page;fixture_track(page,tmp_path)
    row(page,'title1').click();panel(page);title=add_filter(page,'AdjustmentFilter')
    title.get_by_label('亮度',exact=True).fill('.3')
    # A shared filter remains visible from each target, with its original ID.
    title.get_by_label('滤镜目标 第二行标题',exact=True).check();pixels(page)
    title_id=title.get_attribute('data-filter-id')
    row(page,'title2').click()
    expect(page.locator('.filter-entry')).to_have_count(1)
    expect(page.locator('.filter-entry')).to_have_attribute('data-filter-id',title_id)
    row(page,'track').click();expect(page.locator('.filter-entry')).to_have_count(0)
    track=add_filter(page,'GrayscaleFilter');track_id=track.get_attribute('data-filter-id')
    page.get_by_label('滤镜管理范围',exact=True).select_option('canvas')
    expect(page.locator('.filter-entry')).to_have_count(0)
    whole=add_filter(page,'EmbossFilter');canvas_id=whole.get_attribute('data-filter-id')
    row(page,'title1').click()
    expect(page.get_by_label('滤镜管理范围',exact=True)).to_have_value('object')
    expect(page.locator('.filter-entry')).to_have_attribute('data-filter-id',title_id)
    expect(page.get_by_label('亮度',exact=True)).to_have_value('0.3')
    row(page,'track').click();expect(page.locator('.filter-entry')).to_have_attribute('data-filter-id',track_id)
    pixels(page);page.reload();panel(page)
    page.get_by_label('滤镜管理范围',exact=True).select_option('canvas')
    expect(page.locator('.filter-entry')).to_have_attribute('data-filter-id',canvas_id)
    assert len(running_app['client'].get('/api/project').json()['project']['filters'])==3
