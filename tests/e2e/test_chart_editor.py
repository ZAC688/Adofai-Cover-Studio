from playwright.sync_api import expect
from tests.backend.test_charts import chart_bytes
from .test_effects import pixels
from .test_export import export
from PIL import Image
import numpy as np


def open_new(page):
    page.get_by_role('button',name='从谱面生成',exact=True).click()
    page.get_by_label('谱面文件',exact=True).set_input_files({'name':'demo.adofai','mimeType':'application/json','buffer':chart_bytes()})
    frame=page.frame_locator('iframe[title="轨道选段工具"]')
    expect(frame.locator('#range-summary')).to_contain_text('块')
    return frame


def test_chart_preview_apply_reopen_edit_undo_and_exact_composition_export(edge_page,running_app,tmp_path):
    page=edge_page;client=running_app['client'];before=client.get('/api/project').json()
    frame=open_new(page)
    expect(frame.locator('#track-style')).to_have_value('gold')
    frame.locator('#start').fill('1');frame.locator('#end').fill('9')
    frame.locator('#resolution').select_option('1920')
    frame.get_by_role('button',name='生成并预览',exact=True).click()
    expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=20000)
    assert client.get('/api/project').json()==before
    page.get_by_role('button',name='应用到封面',exact=True).click()
    expect(page.get_by_text('已保存到本机',exact=True)).to_be_visible()
    original=pixels(page);saved=client.get('/api/project').json()['project'];old_asset=saved['trackAsset']
    assert saved['generatedTrack']['start']==1 and saved['generatedTrack']['end']==9
    page.reload();pixels(page)
    page.get_by_label('轨道图形操作',exact=True).click();page.get_by_role('menuitem',name='编辑谱面选段').click()
    frame=page.frame_locator('iframe[title="轨道选段工具"]')
    expect(frame.locator('#start')).to_have_value('1');expect(frame.locator('#end')).to_have_value('9')
    frame.locator('#track-style').select_option('chart')
    frame.get_by_role('button',name='生成并预览',exact=True).click()
    expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=20000)
    page.get_by_role('button',name='应用到封面',exact=True).click()
    changed=pixels(page);assert np.any(changed!=original)
    assert client.get('/api/project').json()['project']['generatedTrack']['style']=='chart'
    page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),original)
    assert client.get('/api/project').json()['project']['trackAsset']==old_asset
    export(page,tmp_path/'cover.png');np.testing.assert_array_equal(np.asarray(Image.open(tmp_path/'cover.png')),original)
    page.screenshot(path='artifacts/upgrade-07/01-tracks/editor.png')
    replacement=tmp_path/'replacement.png';Image.new('RGBA',(32,32),'red').save(replacement)
    page.get_by_label('轨道文件',exact=True).set_input_files(str(replacement))
    expect(page.locator('.properties-content')).to_contain_text('32 × 32');pixels(page)
    assert client.get('/api/project').json()['project'].get('generatedTrack') is None
    page.get_by_role('button',name='撤销',exact=True).click();pixels(page)
    assert client.get('/api/project').json()['project']['generatedTrack']['style']=='gold'


def test_cancel_chart_preview_and_failed_import_leave_project_unchanged(edge_page,running_app):
    page=edge_page;client=running_app['client'];before=client.get('/api/project').json()
    page.get_by_role('button',name='从谱面生成',exact=True).click()
    page.get_by_label('谱面文件',exact=True).set_input_files({'name':'bad.adofai','mimeType':'application/json','buffer':b'{broken'})
    expect(page.get_by_role('alert')).to_contain_text('谱面格式无法读取')
    page.get_by_label('关闭谱面生成',exact=True).click()
    assert client.get('/api/project').json()==before

    frame=open_new(page);frame.locator('#resolution').select_option('1920')
    frame.get_by_role('button',name='生成并预览',exact=True).click()
    expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=20000)
    page.get_by_label('关闭谱面生成',exact=True).click()
    assert client.get('/api/project').json()==before


def test_generated_track_is_independent_and_respects_five_track_limit(edge_page,running_app,tmp_path):
    page=edge_page;client=running_app['client']
    original=tmp_path/'original.png';Image.new('RGBA',(20,20),'blue').save(original)
    page.get_by_label('轨道文件',exact=True).set_input_files(str(original))
    expect(page.locator('.properties-content')).to_contain_text('20 × 20');pixels(page)
    old=client.get('/api/project').json()['project']['trackAsset']
    frame=open_new(page);frame.locator('#resolution').select_option('1920')
    frame.get_by_role('button',name='生成并预览',exact=True).click()
    expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=20000)
    page.get_by_role('button',name='应用到封面',exact=True).click();pixels(page)
    document=client.get('/api/project').json()['project']
    assert document['trackAsset']==old
    assert document['extraTracks']['track2']['generatedTrack']['style']=='gold'
    for _ in range(3):page.get_by_role('button',name='添加轨道',exact=False).click()
    pixels(page)
    # Empty slots can still be filled without creating a sixth object.
    expect(page.get_by_role('button',name='从谱面生成',exact=True)).to_be_enabled()
    for key in ['track3','track4','track5']:
        page.locator('[data-object-id='+key+']').click()
        page.get_by_label('轨道文件',exact=True).set_input_files(str(original))
        expect(page.locator('.properties-content')).to_contain_text('20 × 20');pixels(page)
    expect(page.get_by_role('button',name='从谱面生成',exact=True)).to_be_disabled()
