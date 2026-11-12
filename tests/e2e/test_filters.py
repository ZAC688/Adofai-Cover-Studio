import json
import base64
import io
import numpy as np
from PIL import Image,ImageDraw
from playwright.sync_api import expect
from .test_effects import pixels,color
from .test_objects import number,row
from .test_export import export
from .conftest import ROOT

CATALOG=json.loads((ROOT/'frontend/public/filter-catalog.json').read_text(encoding='utf-8'))['filters']

def fixture_track(page,tmp_path):
    image=Image.new('RGBA',(512,512));draw=ImageDraw.Draw(image)
    colors=['#ff0000','#00ff55','#2266ff','#ffffff','#ffaa00','#8833dd']
    for i in range(48):draw.rectangle((32,32+i*9,480,41+i*9),fill=colors[i%len(colors)])
    mask=Image.new('L',image.size);ImageDraw.Draw(mask).ellipse((32,32,480,480),fill=255);image.putalpha(mask)
    path=tmp_path/'filter-source.png';image.save(path)
    page.get_by_label('轨道文件',exact=True).set_input_files(str(path));expect(page.locator('.asset-meta')).to_contain_text('512 × 512');number(page,'发光强度',0)
    return pixels(page)

def panel(page):page.get_by_role('button',name='滤镜',exact=True).click()
def add_filter(page,kind):
    page.get_by_label('选择滤镜',exact=True).select_option(kind);page.get_by_role('button',name='添加滤镜',exact=True).click()
    return page.locator('.filter-entry').last

def test_every_upstream_filter_runs_real_webgl_and_has_visible_effect(edge_page,running_app,tmp_path):
    page=edge_page;baseline=fixture_track(page,tmp_path);panel(page)
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    for item in CATALOG:
        print('Rendering',item['type'],flush=True)
        entry=add_filter(page,item['type'])
        if item['type']=='AdjustmentFilter':entry.get_by_label('亮度',exact=True).fill('.6')
        if item['type']=='HslAdjustmentFilter':entry.get_by_label('饱和度',exact=True).fill('.6')
        page.locator('.panel-heading').first.click()
        output=pixels(page)
        assert page.locator('.error-banner').count()==0,(item['type'],page.locator('.error-banner').all_text_contents())
        assert np.count_nonzero(np.any(output!=baseline,axis=2))>50,item['type']
        entry.get_by_label('启用滤镜',exact=True).uncheck();np.testing.assert_array_equal(pixels(page),baseline,err_msg=item['type'])
        entry.get_by_label('启用滤镜',exact=True).check();np.testing.assert_array_equal(pixels(page),output,err_msg=item['type']+' deterministic')
        entry.get_by_role('button',name='删除滤镜',exact=True).click()
    assert errors==[]
    assert len(CATALOG)==38

def test_object_canvas_scope_order_persist_and_export(edge_page,running_app,tmp_path):
    page=edge_page;baseline=fixture_track(page,tmp_path)
    row(page,'title1').click();page.get_by_label('标题内容',exact=True).fill('FILTERS');number(page,'发光强度',0)
    panel(page);entry=add_filter(page,'GrayscaleFilter');on_title=pixels(page)
    # Only a white title changes nothing: the colorful track must remain unchanged.
    np.testing.assert_array_equal(on_title[550:650,800:1200],baseline[550:650,800:1200])
    entry.get_by_label('滤镜作用范围',exact=True).select_option('canvas');gray=pixels(page)
    assert np.count_nonzero(np.any(gray!=on_title,axis=2))>1000
    np.testing.assert_array_equal(gray[:,:,0],gray[:,:,1]);np.testing.assert_array_equal(gray[:,:,1],gray[:,:,2])
    second=add_filter(page,'ColorOverlayFilter');second.get_by_label('滤镜作用范围',exact=True).select_option('canvas')
    second.get_by_label('颜色',exact=True).evaluate("input=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'#ff0000');input.dispatchEvent(new Event('input',{bubbles:true}));}")
    before=pixels(page);second.get_by_role('button',name='上移滤镜',exact=True).click();after=pixels(page);assert np.any(before!=after)
    export(page,tmp_path/'filters.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'filters.png')),after)
    page.reload();np.testing.assert_array_equal(pixels(page),after);panel(page)
    page.get_by_label('滤镜管理范围',exact=True).select_option('canvas')
    expect(page.locator('.filter-entry')).to_have_count(2)

def range_pixels(page):
    canvas=page.get_by_label('滤镜范围画布',exact=True);expect(canvas).to_have_attribute('aria-busy','false',timeout=20000)
    return np.array(Image.open(io.BytesIO(base64.b64decode(canvas.evaluate("canvas=>canvas.toDataURL().split(',')[1]")))))

def test_rectangle_scope_cancel_apply_and_export_pixels(edge_page,running_app,tmp_path):
    page=edge_page;baseline=fixture_track(page,tmp_path);panel(page);entry=add_filter(page,'GrayscaleFilter')
    entry.get_by_label('滤镜作用范围',exact=True).select_option('canvas');entry.get_by_label('滤镜局部区域',exact=True).select_option('rect');before=pixels(page)
    stored=running_app['client'].get('/api/project').json()
    entry.get_by_role('button',name='编辑滤镜范围',exact=True).click();dialog=page.get_by_role('dialog',name='滤镜局部范围')
    for label,value in [('范围水平位置',0),('范围垂直位置',0),('范围宽度',50),('范围高度',100)]:dialog.get_by_label(label,exact=True).fill(str(value))
    expected=range_pixels(page);assert np.any(expected[:,:950]!=baseline[:,:950]);np.testing.assert_array_equal(expected[:,970:],baseline[:,970:])
    dialog.get_by_role('button',name='取消',exact=True).click();np.testing.assert_array_equal(pixels(page),before);assert running_app['client'].get('/api/project').json()==stored
    entry.get_by_role('button',name='编辑滤镜范围',exact=True).click()
    dialog=page.get_by_role('dialog',name='滤镜局部范围');range_pixels(page);canvas=dialog.get_by_label('滤镜范围画布');rect=canvas.bounding_box()
    page.mouse.move(rect['x']+1,rect['y']+1);page.mouse.down();page.mouse.move(rect['x']+rect['width']*.5,rect['y']+rect['height']-1,steps=3);page.mouse.up()
    assert 45<float(dialog.get_by_label('范围宽度',exact=True).input_value())<55
    expected=range_pixels(page);dialog.get_by_role('button',name='应用滤镜范围',exact=True).click();expect(dialog).to_have_count(0)
    np.testing.assert_array_equal(pixels(page),expected)
    export(page,tmp_path/'filter-region.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'filter-region.png')),expected)
    page.reload();np.testing.assert_array_equal(pixels(page),expected)

def test_painted_scope_soft_transition_failed_save_retry_and_ratio_memory(edge_page,running_app,tmp_path):
    page=edge_page;baseline=fixture_track(page,tmp_path);panel(page);entry=add_filter(page,'GrayscaleFilter')
    entry.get_by_label('滤镜作用范围',exact=True).select_option('canvas');entry.get_by_label('滤镜局部区域',exact=True).select_option('paint');np.testing.assert_array_equal(pixels(page),baseline)
    entry.get_by_role('button',name='编辑滤镜范围',exact=True).click();dialog=page.get_by_role('dialog',name='滤镜局部范围');range_pixels(page)
    dialog.get_by_label('范围画笔大小',exact=True).fill('300');dialog.get_by_label('范围画笔柔和度',exact=True).fill('100')
    canvas=dialog.get_by_label('滤镜范围画布');rect=canvas.bounding_box();page.mouse.click(rect['x']+rect['width']/2,rect['y']+rect['height']/2)
    expected=range_pixels(page);assert np.any(expected!=baseline);np.testing.assert_array_equal(expected[:300],baseline[:300])
    page.route('**/api/filter-masks/*',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"test write failure"}'),times=1)
    dialog.get_by_role('button',name='应用滤镜范围',exact=True).click();expect(dialog.get_by_role('alert')).to_contain_text('草稿仍保留');np.testing.assert_array_equal(range_pixels(page),expected)
    dialog.get_by_role('button',name='应用滤镜范围',exact=True).click();expect(dialog).to_have_count(0);np.testing.assert_array_equal(pixels(page),expected)
    stored=running_app['client'].get('/api/project').json()['project'];mask_id=stored['filters'][0]['regions']['16:9']['maskAsset']
    mask=Image.open(io.BytesIO(running_app['client'].get('/api/assets/'+mask_id).content));assert mask.size==(1920,1080) and len(np.unique(np.array(mask)))>100
    page.get_by_role('button',name='4:3',exact=True).click();pixels(page);page.get_by_role('button',name='16:9',exact=True).click();np.testing.assert_array_equal(pixels(page),expected)
    page.reload();np.testing.assert_array_equal(pixels(page),expected)

def test_array_controls_and_uploaded_filter_texture_persist(edge_page,running_app,tmp_path):
    page=edge_page;baseline=fixture_track(page,tmp_path);panel(page);entry=add_filter(page,'ColorGradientFilter');before=pixels(page)
    color(page,'色标1颜色','#00ff00');entry.get_by_label('渐变类型',exact=True).select_option('1');after=pixels(page);assert np.any(after!=before)
    entry.get_by_role('button',name='添加色标',exact=True).click();pixels(page)
    p=running_app['client'].get('/api/project').json()['project'];assert len(p['filters'][0]['params']['stops'])==3 and p['filters'][0]['params']['type']==1
    entry.get_by_role('button',name='删除滤镜',exact=True).click();entry=add_filter(page,'ConvolutionFilter');entry.get_by_label('卷积矩阵 5',exact=True).fill('1');pixels(page)
    assert running_app['client'].get('/api/project').json()['project']['filters'][0]['params']['matrix'][4]==1
    entry.get_by_role('button',name='删除滤镜',exact=True).click();entry=add_filter(page,'SimpleLightmapFilter');lit=pixels(page);assert np.any(lit!=baseline)
    texture=tmp_path/'white-lightmap.png';Image.new('RGB',(64,64),'white').save(texture)
    entry.get_by_label('光照贴图图片',exact=True).set_input_files(str(texture));expect(entry.get_by_text('已选择本机图片',exact=False)).to_be_visible();uploaded=pixels(page)
    assert np.mean(np.abs(uploaded.astype(int)-baseline.astype(int)))<1
    p=running_app['client'].get('/api/project').json()['project'];assert p['filters'][0]['params']['lightMap']
    texture.unlink();page.reload();np.testing.assert_array_equal(pixels(page),uploaded)
