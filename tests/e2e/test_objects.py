import re
import io
import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .conftest import ROOT
from .test_editor import saved
from .test_effects import pixels,color,open_effects
from .test_export import export
from .test_mask import recognize,paint


def row(page,id):return page.locator(f'.object-row[data-object-id="{id}"]')
def add(page,kind):page.get_by_role('button',name=re.compile('^添加'+kind)).click()
def number(page,label,value):
    page.get_by_label(label,exact=True).fill(str(value));page.locator('.panel-heading').first.click()


def test_five_of_each_limit_delete_readd_undo_and_layout_persistence(edge_page,running_app,tmp_path):
    page=edge_page
    image=tmp_path/'square.png';Image.new('RGBA',(64,64),'#2266aa').save(image)
    for i in range(1,6):
        if i>=3:add(page,'标题')
        row(page,f'title{i}').click();page.get_by_label('标题内容',exact=True).fill(f'标题 {i}')
        number(page,'旋转角度',i*7);page.get_by_label('字体',exact=True).select_option('noto-sans-sc')
    expect(page.get_by_role('button',name=re.compile('^添加标题'))).to_be_disabled()
    for i in range(1,6):
        if i>=2:add(page,'轨道')
        row(page,'track' if i==1 else f'track{i}').click()
        page.get_by_label('轨道文件',exact=True).set_input_files(str(image))
        expect(page.locator('.asset-meta')).to_contain_text('64 × 64')
        number(page,'旋转角度',-i*5);color(page,'图形颜色',f'#{i*40:02x}7799')
    pixels(page)
    expect(page.locator('.object-row')).to_have_count(11)
    expect(page.get_by_role('button',name=re.compile('^添加轨道'))).to_be_disabled()
    doc=running_app['client'].get('/api/project').json()['project']
    assert len(doc['titles'])==5 and len(doc['extraTracks'])==4
    assert len({doc['trackAsset'],*(v['trackAsset'] for v in doc['extraTracks'].values())})==5
    assert doc['titles'][4]['fontId']=='noto-sans-sc'
    page.get_by_role('button',name='删除对象',exact=True).click();expect(page.locator('.object-row')).to_have_count(10)
    page.get_by_role('button',name='撤销',exact=True).click();expect(page.locator('.object-row')).to_have_count(11)
    row(page,'track5').click();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('-25')
    page.get_by_role('button',name='删除对象',exact=True).click();add(page,'轨道')
    expect(row(page,'track5')).to_have_attribute('aria-pressed','true');expect(page.get_by_label('旋转角度',exact=True)).to_have_value('0')
    expect(page.get_by_role('button',name='上传图片',exact=True)).to_be_visible()
    row(page,'title5').click();page.get_by_role('button',name='4:3',exact=True).click();number(page,'旋转角度',-43)
    add_button=page.get_by_role('button',name='删除对象',exact=True)
    add_button.click();expect(row(page,'title5')).to_have_count(0)
    page.get_by_role('button',name='撤销',exact=True).click();row(page,'title5').click()
    expect(page.get_by_label('标题内容',exact=True)).to_have_value('标题 5')
    expect(page.get_by_label('旋转角度',exact=True)).to_have_value('-43')
    saved(page);page.reload();row(page,'title5').click();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('-43')
    page.get_by_role('button',name='16:9',exact=True).click();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('35')
    row(page,'bg').click();expect(page.get_by_role('button',name='删除对象',exact=True)).to_be_disabled()
    expect(row(page,'bg')).to_have_attribute('draggable','false')
    assert page.locator('.editor-layout').bounding_box()['height']<=page.viewport_size['height']-80+1
    final=pixels(page);assert np.count_nonzero(np.any(final[:,:,:3]!=[8,13,22],axis=2))>10000
    page.screenshot(path=str(ROOT/'artifacts/upgrade/06-objects/five-each.png'))


def test_drag_mixed_layers_changes_pixels_hit_priority_undo_and_export(edge_page,running_app,tmp_path):
    page=edge_page
    for id,shade in [('track','#ff0000'),('track2','#0000ff')]:
        if id=='track2':add(page,'轨道')
        row(page,id).click();path=tmp_path/f'{id}.png';Image.new('RGBA',(64,64),shade).save(path)
        page.get_by_label('轨道文件',exact=True).set_input_files(str(path));expect(page.locator('.asset-meta')).to_contain_text('64 × 64')
        number(page,'发光强度',0)
    row(page,'title1').click();page.get_by_label('标题内容',exact=True).fill('MMMM');number(page,'发光强度',0)
    number(page,'水平位置',800);number(page,'垂直位置',450)
    before=pixels(page);assert np.array_equal(before[540,960,:3],[0,0,255])
    row(page,'title1').drag_to(row(page,'track2'))
    after=pixels(page);white=np.all(after[:,:,:3]==255,axis=2)
    assert white.sum()>500
    y,x=np.argwhere(white)[len(np.argwhere(white))//2]
    rect=page.get_by_label('封面画布').bounding_box()
    row(page,'bg').click();page.mouse.click(rect['x']+int(x)/1920*rect['width'],rect['y']+int(y)/1080*rect['height'])
    expect(row(page,'title1')).to_have_attribute('aria-pressed','true')
    page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),before)
    page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),after)
    export(page,tmp_path/'mixed.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'mixed.png')),after)
    saved(page);expected=running_app['client'].get('/api/project').json()['project']['layerOrder']
    page.reload();pixels(page);assert [v.get_attribute('data-object-id') for v in page.locator('.object-row').all()]==expected
    page.screenshot(path=str(ROOT/'artifacts/upgrade/06-objects/mixed-layers.png'))
    row(page,'track2').drag_to(row(page,'title1'));top=pixels(page);assert np.array_equal(top[y,x,:3],[0,0,255])
    row(page,'bg').click();page.mouse.click(rect['x']+int(x)/1920*rect['width'],rect['y']+int(y)/1080*rect['height'])
    expect(row(page,'track2')).to_have_attribute('aria-pressed','true')


def test_all_objects_can_be_removed_and_primary_slots_added_back(edge_page,tmp_path):
    page=edge_page
    for id in ['title1','title2','track']:
        row(page,id).click();page.get_by_role('button',name='删除对象',exact=True).click()
    expect(page.locator('.object-row')).to_have_count(1)
    blank=pixels(page);assert np.all(blank[:,:,:3]==[8,13,22])
    # Global upload must recreate a track even when all track slots were removed.
    image=tmp_path/'recreated.png';Image.new('RGBA',(40,40),'#00cc88').save(image)
    page.get_by_label('轨道文件',exact=True).set_input_files(str(image))
    expect(row(page,'track')).to_have_attribute('aria-pressed','true')
    expect(page.locator('.asset-meta')).to_contain_text('40 × 40')
    assert np.any(pixels(page)!=blank)
    add(page,'标题');expect(row(page,'title1')).to_have_attribute('aria-pressed','true')
    page.get_by_label('标题内容',exact=True).fill('重新添加');saved(page);page.reload()
    expect(page.get_by_label('标题内容',exact=True)).to_have_value('重新添加')


def test_extra_track_effects_recognition_and_brush_do_not_modify_first_track(edge_page,running_app):
    page=edge_page;client=running_app['client'];recognize(page)
    first=client.get('/api/project').json()['project']
    add(page,'轨道');page.get_by_label('轨道文件',exact=True).set_input_files(str(ROOT/'test-assets/reference/sample-09.png'))
    expect(page.locator('.asset-meta')).to_contain_text('1406 × 1123')
    page.get_by_label('自动去除背景',exact=True).check()
    expect(page.get_by_role('button',name='修正轨道',exact=True)).to_be_enabled(timeout=45000)
    open_effects(page);page.get_by_label('水平模糊开关',exact=True).check();color(page,'水平模糊颜色','#ff0099')
    page.get_by_role('button',name='修正轨道',exact=True).click()
    expect(page.get_by_role('dialog',name='轨道修正工作区').get_by_role('status')).to_have_text('修正已保存')
    paint(page,1000,320);page.get_by_role('button',name='返回构图',exact=True).click();saved(page)
    after=client.get('/api/project').json()['project'];extra=after['extraTracks']['track2']
    for key in ['trackAsset','maskAsset','baseMaskAsset','removeBackground','trackColor','trackGlow','trackEffects']:assert after[key]==first[key]
    assert extra['maskAsset']!=extra['baseMaskAsset']
    raw=client.get('/api/assets/'+extra['maskAsset']).content
    assert Image.open(io.BytesIO(raw)).convert('L').getpixel((1000,320))==0
    assert extra['trackEffects']['horizontalBlur']['enabled'] and extra['trackEffects']['horizontalBlur']['color']=='#ff0099'
    page.reload();row(page,'track2').click();page.get_by_role('button',name='去背景与轨道修正').click()
    expect(page.get_by_label('自动去除背景',exact=True)).to_be_checked()
    open_effects(page);expect(page.get_by_label('水平模糊开关',exact=True)).to_be_checked()
