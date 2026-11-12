import base64
import io
import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .test_effects import pixels
from .test_editor import saved
from .test_objects import number,row,add
from .test_export import export
from .conftest import ROOT

BACK=np.array([20,100,180]);FRONT=np.array([180,60,20])


def setup_images(page,tmp_path):
    bg=tmp_path/'fusion-bg.png';track=tmp_path/'fusion-source.png'
    Image.new('RGB',(1920,1080),tuple(BACK)).save(bg);Image.new('RGB',(256,256),tuple(FRONT)).save(track)
    page.get_by_label('底图文件',exact=True).set_input_files(str(bg));expect(page.locator('.asset-meta')).to_contain_text('1920 × 1080')
    page.get_by_label('轨道文件',exact=True).set_input_files(str(track));expect(page.locator('.asset-meta')).to_contain_text('256 × 256')
    number(page,'发光强度',0);number(page,'缩放 (%)',200)
    pixels(page)  # Establish a durable baseline before testing cross-track isolation.
    return track


def open_fusion(page,menu=False):
    if menu:page.get_by_role('button',name='轨道图形操作',exact=True).click();page.get_by_role('menuitem',name='融合',exact=True).click()
    else:page.get_by_role('button',name='融合图片',exact=True).click()
    dialog=page.get_by_role('dialog',name='图片融合',exact=True)
    expect(dialog.get_by_role('button',name='应用融合',exact=True)).to_be_enabled()
    return dialog


def preview(page):
    canvas=page.get_by_label('融合效果预览',exact=True);expect(canvas).to_have_attribute('aria-busy','false',timeout=20000)
    raw=canvas.evaluate("canvas=>canvas.toDataURL().split(',')[1]")
    return np.array(Image.open(io.BytesIO(base64.b64decode(raw))))


def setting(page,label,value):
    dialog=page.get_by_role('dialog',name='图片融合',exact=True)
    dialog.get_by_label(label,exact=True).fill(str(value));dialog.get_by_role('heading',name='图片融合',exact=True).click()


def soft_gradient(page):
    # The user replaced the brush with a gradient; retain the real pixel ramp,
    # cancel, persistence, failure and isolation checks against the new controls.
    setting(page,'过渡宽度 (%)',50)


def test_smooth_gradient_reverse_reset_cancel_and_no_project_writes_before_apply(edge_page,running_app,tmp_path):
    page=edge_page;setup_images(page,tmp_path);baseline=pixels(page);before=running_app['client'].get('/api/project').json()
    dialog=open_fusion(page,menu=True);soft_gradient(page);soft=preview(page)
    np.testing.assert_allclose(soft[540,750,:3],BACK,atol=1)
    np.testing.assert_allclose(soft[540,1170,:3],FRONT,atol=1)
    ramp=soft[540,832:1088,0].astype(int)
    assert len(np.unique(ramp))>100 and np.max(np.abs(np.diff(ramp)))<=3
    dialog.get_by_label('反转渐变',exact=True).check();assert preview(page)[540,750,0]>soft[540,750,0]+100
    dialog.get_by_role('button',name='重置融合',exact=True).click();np.testing.assert_array_equal(preview(page),soft)
    for label in ['图片混合模式','融合不透明度','融合画笔大小']:expect(dialog.get_by_label(label,exact=True)).to_have_count(0)
    assert running_app['client'].get('/api/project').json()==before
    dialog.get_by_role('button',name='取消',exact=True).click();np.testing.assert_array_equal(pixels(page),baseline)
    open_fusion(page);np.testing.assert_array_equal(preview(page),soft)
    page.get_by_role('button',name='取消',exact=True).click()


def test_legacy_all_blend_modes_and_gradient_apply_undo_refresh_and_png_match_preview(edge_page,running_app,tmp_path):
    page=edge_page;setup_images(page,tmp_path);number(page,'旋转角度',25);pixels(page)
    values={}
    for mode in ['normal','multiply','screen','overlay','soft-light','add']:
        doc=running_app['client'].get('/api/project').json();doc['project']['fusion']={'enabled':True,'maskAsset':None,'mode':mode,'opacity':100}
        assert running_app['client'].put('/api/project',json={'baseRevision':doc['revision'],'project':doc['project']}).status_code==200
        page.reload();row(page,'track').click();values[mode]=pixels(page)[540,960,:3].astype(int)
    np.testing.assert_array_equal(values['normal'],FRONT)
    np.testing.assert_allclose(values['multiply'],FRONT*BACK/255,atol=1)
    np.testing.assert_allclose(values['screen'],255-(255-FRONT)*(255-BACK)/255,atol=1)
    np.testing.assert_array_equal(values['add'],np.minimum(255,FRONT+BACK))
    assert len({tuple(value) for value in values.values()})==6
    baseline=pixels(page);before=running_app['client'].get('/api/project').json();dialog=open_fusion(page)
    np.testing.assert_array_equal(preview(page),baseline)
    dialog.get_by_role('button',name='应用融合',exact=True).click();saved(page);assert running_app['client'].get('/api/project').json()==before
    dialog=open_fusion(page);setting(page,'过渡位置 (%)',35);setting(page,'过渡宽度 (%)',75);setting(page,'过渡角度',90)
    vertical=preview(page);dialog.get_by_label('反转渐变',exact=True).check();assert np.any(preview(page)!=vertical)
    expected=preview(page);page.screenshot(path=str(ROOT/'artifacts/upgrade-03/05-fusion/window.png'))
    dialog.get_by_role('button',name='应用融合',exact=True).click();expect(dialog).to_have_count(0)
    np.testing.assert_array_equal(pixels(page),expected)
    doc=running_app['client'].get('/api/project').json()['project'];assert doc['fusion']['kind']=='gradient' and doc['fusion']['position']==35
    page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),baseline)
    page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),expected)
    assert doc['maskAsset'] is None and not doc['removeBackground']
    mask=Image.open(io.BytesIO(running_app['client'].get('/api/assets/'+doc['fusion']['maskAsset']).content))
    assert len(np.unique(np.array(mask)))>150
    export(page,tmp_path/'fusion.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'fusion.png')),expected)
    page.reload();row(page,'track').click();np.testing.assert_array_equal(pixels(page),expected)
    dialog=open_fusion(page);expect(dialog.get_by_label('过渡宽度 (%)',exact=True)).to_have_value('75')
    dialog.get_by_role('button',name='重置融合',exact=True).click();assert np.any(preview(page)!=expected)
    dialog.get_by_role('button',name='取消',exact=True).click();np.testing.assert_array_equal(pixels(page),expected)
    page.get_by_role('button',name='4:3',exact=True).click();other=pixels(page)
    export(page,tmp_path/'fusion43.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'fusion43.png')),other)


def test_failed_mask_save_keeps_preview_draft_until_retry(edge_page,running_app,tmp_path):
    page=edge_page;setup_images(page,tmp_path);before=running_app['client'].get('/api/project').json();dialog=open_fusion(page);soft_gradient(page);draft=preview(page)
    page.route('**/api/masks/*',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"test disk error"}'),times=1)
    dialog.get_by_role('button',name='应用融合',exact=True).click();expect(dialog.get_by_role('alert')).to_contain_text('草稿仍保留')
    assert running_app['client'].get('/api/project').json()==before
    np.testing.assert_array_equal(preview(page),draft)
    dialog.get_by_role('button',name='应用融合',exact=True).click();expect(dialog).to_have_count(0)
    np.testing.assert_array_equal(pixels(page),draft)


def test_second_track_fusion_stays_independent_and_rotation_pivot_survives_asymmetric_mask(edge_page,running_app,tmp_path):
    page=edge_page;track=setup_images(page,tmp_path);first=running_app['client'].get('/api/project').json()['project']
    add(page,'轨道');page.get_by_label('轨道文件',exact=True).set_input_files(str(track));number(page,'发光强度',0);number(page,'缩放 (%)',200);number(page,'旋转角度',30)
    dialog=open_fusion(page);dialog.get_by_role('button',name='应用融合',exact=True).click();expect(dialog).to_have_count(0);pixels(page)
    p=running_app['client'].get('/api/project').json();assert p['project']['fusion'] is None
    assert p['project']['extraTracks']['track2']['fusion']['kind']=='gradient'
    for key in ['trackAsset','maskAsset','baseMaskAsset','removeBackground','trackColor','trackGlow','trackEffects','trackShadow']:assert p['project'][key]==first[key]
    # Half-image transparency must not move the original rotation center.
    image=Image.new('L',(256,256));image.paste(255,(128,0,256,256));buffer=io.BytesIO();image.save(buffer,'PNG')
    asset=running_app['client'].post('/api/masks/'+p['project']['extraTracks']['track2']['trackAsset'],files={'file':('mask.png',buffer.getvalue(),'image/png')}).json()
    p['project']['extraTracks']['track2']['fusion']={'enabled':True,'maskAsset':asset['id'],'mode':'normal','opacity':100}
    assert running_app['client'].put('/api/project',json={'baseRevision':p['revision'],'project':p['project']}).status_code==200
    page.reload();row(page,'track2').click();pixels(page)
    expect(page.get_by_label('轨道选中轮廓').locator('g').first).to_have_attribute('transform','rotate(30 960 540)')
    canvas=page.get_by_label('封面画布',exact=True);rect=canvas.bounding_box()
    for x,y,expected_id in [(960+128*3**.5/2,604,'track2'),(960-128*3**.5/2,476,'track')]:
        page.mouse.click(rect['x']+x/1920*rect['width'],rect['y']+y/1080*rect['height'])
        expect(row(page,expected_id)).to_have_attribute('aria-pressed','true')
    row(page,'track2').click();knob=page.get_by_label('旋转手柄',exact=True).bounding_box()
    cx=rect['x']+960/1920*rect['width'];cy=rect['y']+540/1080*rect['height'];kx=knob['x']+knob['width']/2;ky=knob['y']+knob['height']/2
    page.mouse.move(kx,ky);page.mouse.down();page.mouse.move(cx-(ky-cy),cy+(kx-cx),steps=6);page.mouse.up()
    assert abs(float(page.get_by_label('旋转角度',exact=True).input_value())-120)<3
    page.get_by_role('button',name='撤销',exact=True).click();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('30')
    page.screenshot(path=str(ROOT/'artifacts/upgrade-03/05-fusion/editor.png'))
