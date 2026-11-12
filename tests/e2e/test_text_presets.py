import json
from copy import deepcopy

import numpy as np
from PIL import Image
from playwright.sync_api import expect

from backend.app.schema import Text3D,Shadow
from backend.app.storage import Store
from backend.app.text_presets import TextPresets
from tests.backend.test_text_presets import style_body
from tests.backend.test_filters import spec
from .test_effects import pixels
from .test_export import export
from .test_filters import panel
from .test_objects import row


def test_save_export_import_apply_preserves_content_position_rotation_and_other_objects(edge_page,running_app,tmp_path):
    page=edge_page;client=running_app['client']
    record=client.get('/api/project').json();project=record['project']
    project['titles'][0].update(text='SOURCE private',color='#f184ca',fontId='inter',glow=0,text3d=Text3D(enabled=True,depth=35).model_dump(),shadow=Shadow(enabled=True,blur=8).model_dump())
    project['titles'][1]['text']='KEEP CONTENT'
    project['layouts']['16:9']['title1'].update(fontSize=105,rotation=10)
    project['layouts']['16:9']['title2'].update(x=260,y=650,fontSize=60,rotation=-20)
    project['layouts']['4:3']=deepcopy(project['layouts']['16:9'])
    project['layouts']['4:3']['title1']['fontSize']=80
    project['layouts']['4:3']['title2']['rotation']=35
    filter=spec('AdjustmentFilter');filter['targets']=['title1'];filter['params']['brightness']=.8;project['filters']=[filter]
    assert client.put('/api/project',json={'baseRevision':record['revision'],'project':project}).status_code==200
    page.reload();pixels(page);panel(page)
    page.get_by_label('文字预设名称',exact=True).fill('3D 粉色')
    page.get_by_role('button',name='保存为文字预设',exact=True).click()
    expect(page.get_by_text('文字预设已保存到本机',exact=True)).to_be_visible()
    with page.expect_download() as event:page.get_by_role('button',name='导出文字预设',exact=True).click()
    path=tmp_path/'style.json';event.value.save_as(path);file=json.loads(path.read_text(encoding='utf-8'))
    assert file['format']=='adofai-text-preset' and 'text' not in file['style']
    assert 'SOURCE private' not in path.read_text(encoding='utf-8')
    row(page,'title2').click();before=pixels(page);saved_before=client.get('/api/project').json()['project']
    page.get_by_label('文字预设文件',exact=True).set_input_files(str(path))
    expect(page.get_by_label('本机文字预设').locator('option')).to_have_count(3)
    page.get_by_role('button',name='应用文字预设',exact=True).click()
    expect(page.get_by_text('已应用文字预设，可撤销',exact=True)).to_be_visible()
    rendered=pixels(page);assert np.count_nonzero(np.any(rendered!=before,axis=2))>1000
    applied=client.get('/api/project').json()['project']
    assert applied['titles'][0]==saved_before['titles'][0]
    assert applied['titles'][1]=={**applied['titles'][0],'text':'KEEP CONTENT'}
    assert applied['filters'][0]==saved_before['filters'][0]
    assert applied['filters'][1]['targets']==['title2']
    for ratio,size in [('16:9',105),('4:3',80)]:
        assert applied['layouts'][ratio]['title2']=={**saved_before['layouts'][ratio]['title2'],'fontSize':size}
    page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),before)
    page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),rendered)
    export(page,tmp_path/'preset.png');np.testing.assert_array_equal(np.asarray(Image.open(tmp_path/'preset.png')),rendered)
    page.reload();np.testing.assert_array_equal(pixels(page),rendered);panel(page)
    expect(page.get_by_label('本机文字预设').locator('option')).to_have_count(3)


def test_portable_custom_font_texture_and_mask_render_without_source_store(edge_page,running_app,tmp_path):
    external=Store(tmp_path/'different-data-directory');library=TextPresets(external);body=style_body(external)
    saved=library.save(body);file=library.get(saved['id']);old_font=file['style']['fontId']
    path=tmp_path/'portable.json';path.write_text(json.dumps(file),encoding='utf-8')
    page=edge_page;client=running_app['client']
    page.get_by_label('标题内容',exact=True).fill('PORTABLE AVATAR');pixels(page)
    assert client.get('/api/fonts').json()==[]
    panel(page);page.get_by_label('文字预设文件',exact=True).set_input_files(str(path))
    expect(page.get_by_text('文字预设已保存到本机',exact=True)).to_be_visible()
    page.get_by_role('button',name='应用文字预设',exact=True).click()
    expect(page.get_by_text('已应用文字预设，可撤销',exact=True)).to_be_visible()
    rendered=pixels(page);document=client.get('/api/project').json()['project']
    new_font=document['titles'][0]['fontId'];assert new_font!=old_font
    assert client.get('/api/fonts/'+new_font).content==external.font_info(old_font)['path'].read_bytes()
    assert document['titles'][0]['text']=='PORTABLE AVATAR' and document['titles'][0]['text3d']['depth']==44
    assert document['filters'][0]['params']['lightMap']!=body.filters[0].params['lightMap']
    assert document['filters'][0]['regions']['16:9']['maskAsset']!=body.filters[0].regions['16:9'].maskAsset
    assert np.count_nonzero(np.any(rendered[:,:,:3]!=[8,13,22],axis=2))>1000
    page.get_by_role('button',name='对象属性',exact=True).click()
    expect(page.get_by_label('字体',exact=True)).to_have_value(new_font)
    export(page,tmp_path/'portable.png');np.testing.assert_array_equal(np.asarray(Image.open(tmp_path/'portable.png')),rendered)
    page.reload();np.testing.assert_array_equal(pixels(page),rendered)


def test_failed_save_apply_and_corrupt_import_preserve_work_and_support_retry(edge_page,running_app):
    page=edge_page;client=running_app['client']
    page.get_by_label('标题内容',exact=True).fill('KEEP');pixels(page);panel(page)
    page.get_by_label('文字预设名称',exact=True).fill('可重试文字')
    before=client.get('/api/project').json()
    page.route('**/api/text-presets',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"测试文字保存失败"}'),times=1)
    page.get_by_role('button',name='保存为文字预设',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('测试文字保存失败')
    expect(page.get_by_label('文字预设名称')).to_have_value('可重试文字')
    assert client.get('/api/text-presets').json()==[] and client.get('/api/project').json()==before
    page.get_by_role('button',name='保存为文字预设',exact=True).click()
    expect(page.get_by_text('文字预设已保存到本机',exact=True)).to_be_visible()
    page.route('**/api/text-presets/*/prepare',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"测试文字读取失败"}'),times=1)
    page.get_by_role('button',name='应用文字预设',exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('测试文字读取失败')
    assert client.get('/api/project').json()==before
    page.get_by_label('文字预设文件').set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{broken'})
    expect(page.get_by_role('alert')).to_contain_text('无法读取文字预设')
    assert client.get('/api/project').json()==before
