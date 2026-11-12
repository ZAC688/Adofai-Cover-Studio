import json
import cv2
import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .test_effects import pixels,open_effects,color
from .test_objects import number,row
from .test_export import export
from .test_filters import panel,add_filter
from .conftest import ROOT


def toggle(page):page.get_by_role('button',name='3D文字模式',exact=True).click()


def test_3d_switch_preserves_2d_and_all_configuration_changes_real_pixels(edge_page,running_app,tmp_path):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('3D 冰与火之舞')
    page.get_by_label('字体',exact=True).select_option('noto-sans-sc');number(page,'字号',140)
    original=pixels(page);toggle(page);three=pixels(page)
    assert np.count_nonzero(np.any(three!=original,axis=2))>500
    assert not page.locator('.error-banner').count()
    toggle(page);np.testing.assert_array_equal(pixels(page),original)
    toggle(page);np.testing.assert_array_equal(pixels(page),three)
    settings=[('3D厚度 (%)',45),('3D倒角 (%)',2),('3D旋转 X',-20),('3D旋转 Y',25),('3D旋转 Z',12),('3D透视强度',75),('3D光照方向',65),('3D光照高度',20),('3D光照强度',3),('3D环境光强度',.25)]
    for label,value in settings:
        number(page,label,value);after=pixels(page)
        assert np.count_nonzero(np.any(after!=three,axis=2))>20,label
        three=after
    color(page,'3D侧面颜色','#ff2255');sides=pixels(page);assert np.any(sides!=three)
    color(page,'文字颜色','#33ccff');front=pixels(page);assert np.any(front!=sides)
    page.reload();np.testing.assert_array_equal(pixels(page),front)
    expect(page.get_by_role('button',name='3D文字模式',exact=True)).to_have_attribute('aria-pressed','true')
    document=running_app['client'].get('/api/project').json()['project']
    assert len(document['titles'])==2 and document['titles'][1]['text3d'] is None
    assert document['titles'][0]['text3d']['depth']==45
    export(page,tmp_path/'3d.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'3d.png')),front)
    directory=ROOT/'artifacts/upgrade-05/06-text3d';directory.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(directory/'editor.png'))


def test_3d_supports_all_fonts_uploads_and_preserves_glyph_holes(edge_page,running_app,tmp_path):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('AVATAR 冰与火')
    toggle(page);results=[]
    for font_id in ['system']+[font['id'] for font in json.loads((ROOT/'frontend/public/fonts/manifest.json').read_text(encoding='utf-8'))['fonts']]:
        page.get_by_label('字体',exact=True).select_option(font_id);image=pixels(page)
        assert np.count_nonzero(np.any(image[:,:,:3]!=[8,13,22],axis=2))>500,font_id
        assert not page.locator('.error-banner').count(),font_id
        results.append(image)
    assert len({image.tobytes() for image in results})==11
    previous_font=page.get_by_label('字体',exact=True).input_value()
    page.get_by_label('字体文件',exact=True).set_input_files(str(ROOT/'frontend/public/fonts/inter.ttf'))
    expect(page.get_by_label('字体',exact=True)).not_to_have_value(previous_font);uploaded=pixels(page)
    font_id=page.get_by_label('字体',exact=True).input_value();assert len(font_id)==32
    page.reload();expect(page.get_by_label('字体',exact=True)).to_have_value(font_id);np.testing.assert_array_equal(pixels(page),uploaded)
    page.get_by_label('字体',exact=True).select_option('space-mono');page.get_by_label('标题内容',exact=True).fill('O')
    for label in ['3D厚度 (%)','3D倒角 (%)','3D旋转 X','3D旋转 Y','3D旋转 Z','3D透视强度']:number(page,label,0)
    image=pixels(page);body=np.any(image[:,:,:3]!=[8,13,22],axis=2).astype('uint8')
    contours,hierarchy=cv2.findContours(body,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
    assert any(h[3]>=0 and cv2.contourArea(contours[i])>20 for i,h in enumerate(hierarchy[0])),'O must retain a transparent hole'


def test_3d_effects_filters_undo_and_both_ratios_export_exactly(edge_page,running_app,tmp_path):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('3D LIGHT')
    page.get_by_label('字体',exact=True).select_option('russo-one');toggle(page);base=pixels(page)
    number(page,'3D旋转 Y',40);changed=pixels(page)
    page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),base)
    page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),changed)
    open_effects(page)
    for name in ['多尺度 Bloom','渐变填充','发光描边']:page.get_by_label(name+'开关',exact=True).check()
    page.get_by_label('阴影开关',exact=True).check();lit=pixels(page);assert np.any(lit!=changed)
    panel(page);entry=add_filter(page,'GrayscaleFilter');filtered=pixels(page);assert np.any(filtered!=lit)
    entry.get_by_label('启用滤镜',exact=True).uncheck();np.testing.assert_array_equal(pixels(page),lit)
    for ratio in ['16:9','4:3']:
        page.get_by_role('button',name=ratio,exact=True).click();expected=pixels(page)
        export(page,tmp_path/f'3d-{ratio.replace(":","-")}.png')
        np.testing.assert_array_equal(np.array(Image.open(tmp_path/f'3d-{ratio.replace(":","-")}.png')),expected)
    page.reload();np.testing.assert_array_equal(pixels(page),expected)


def test_3d_outline_failure_retains_title_and_can_retry(edge_page,running_app):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('RETRY')
    page.route('**/api/text-outline',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"测试临时读取失败"}'),times=1)
    toggle(page);expect(page.get_by_role('alert')).to_contain_text('临时读取失败')
    expect(page.get_by_label('标题内容',exact=True)).to_have_value('RETRY')
    toggle(page);pixels(page);toggle(page);rendered=pixels(page)
    assert np.count_nonzero(np.any(rendered[:,:,:3]!=[8,13,22],axis=2))>100
    assert running_app['client'].get('/api/project').json()['project']['titles'][0]['text']=='RETRY'


def test_3d_titles_keep_five_slots_independent_and_can_be_dragged(edge_page,running_app):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('DRAG 3D');toggle(page);pixels(page)
    box=page.locator('.selection-box').bounding_box();canvas=page.get_by_label('封面画布').bounding_box()
    before=running_app['client'].get('/api/project').json()['project']['layouts']['16:9']['title1']
    row(page,'title2').click()
    x,y=box['x']+box['width']/2,box['y']+box['height']/2
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+25,y+10,steps=4)
    expect(row(page,'title1')).to_have_attribute('aria-pressed','true')
    expect(page.locator('.canvas-stage')).to_have_class('canvas-stage manipulating')
    page.mouse.up();pixels(page)
    moved=running_app['client'].get('/api/project').json()['project']['layouts']['16:9']['title1']
    assert abs(moved['x']-before['x']-25*1920/canvas['width'])<1
    page.get_by_role('button',name='撤销',exact=True).click();pixels(page)
    assert running_app['client'].get('/api/project').json()['project']['layouts']['16:9']['title1']==before
    for i in range(3,6):
        page.get_by_role('button',name='添加标题',exact=False).click()
        page.get_by_label('标题内容',exact=True).fill('TITLE '+str(i))
        toggle(page);number(page,'3D厚度 (%)',i*10);pixels(page)
    expect(page.get_by_role('button',name='添加标题',exact=False)).to_be_disabled()
    page.reload();document=running_app['client'].get('/api/project').json()['project']
    assert len(document['titles'])==5
    assert document['titles'][0]['text3d']['depth']==18 and document['titles'][1]['text3d'] is None
    assert [title['text3d']['depth'] for title in document['titles'][2:]]==[30,40,50]
