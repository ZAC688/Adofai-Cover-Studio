import json,io
import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .test_filters import fixture_track,panel,add_filter
from .test_effects import pixels
from .test_objects import row
from .test_export import export
from tests.backend.test_filters import spec


def test_preset_save_export_import_apply_history_and_exact_masked_render(edge_page,running_app,tmp_path):
    page=edge_page;client=running_app['client'];fixture_track(page,tmp_path)
    def upload(image,url):
        raw=io.BytesIO();image.save(raw,'PNG');return client.post(url,files={'file':('image.png',raw.getvalue(),'image/png')}).json()['id']
    texture=upload(Image.new('RGB',(64,64),(90,180,210)),'/api/assets')
    mask=Image.new('L',(1920,1080));mask.paste(255,(0,0,960,1080));mask_id=upload(mask,'/api/filter-masks/16-9')
    first=spec('SimpleLightmapFilter');first['params']['lightMap']=texture;first['regions']={'16:9':{'mode':'paint','maskAsset':mask_id},'4:3':{'mode':'rect','x':.1,'y':.1,'width':.6,'height':.7,'feather':17}}
    second=spec('AdjustmentFilter');second['id']='b'*32;second['params']['brightness']=.43;second['enabled']=False
    document=client.get('/api/project').json();document['project']['filters']=[first,second]
    assert client.put('/api/project',json={'baseRevision':document['revision'],'project':document['project']}).status_code==200
    page.reload();row(page,'track').click();expected=pixels(page);panel(page)
    page.get_by_label('滤镜预设名称',exact=True).fill('便携冷色')
    page.get_by_role('button',name='保存为滤镜预设',exact=True).click()
    expect(page.get_by_text('预设已保存到本机',exact=True)).to_be_visible()
    with page.expect_download() as download:page.get_by_role('button',name='导出滤镜预设',exact=True).click()
    path=tmp_path/'portable.json';download.value.save_as(path)
    data=json.loads(path.read_text(encoding='utf-8'));assert len(data['assets'])==2 and len(data['filters'])==2
    for _ in range(2):
        entry=page.locator('.filter-entry').first
        if not entry.evaluate('node=>node.open'):entry.locator('summary').click()
        entry.get_by_role('button',name='删除滤镜',exact=True).click()
    cleared=pixels(page);assert np.any(cleared!=expected)
    page.get_by_label('滤镜预设文件',exact=True).set_input_files(str(path))
    expect(page.get_by_label('本机滤镜预设').locator('option')).to_have_count(3)
    page.get_by_role('button',name='应用滤镜预设',exact=True).click()
    expect(page.get_by_text('已应用预设，可撤销',exact=True)).to_be_visible()
    np.testing.assert_array_equal(pixels(page),expected)
    saved=client.get('/api/project').json()['project']['filters']
    assert saved[0]['params']['lightMap']!=texture and saved[0]['regions']['16:9']['maskAsset']!=mask_id
    assert saved[1]['enabled'] is False
    page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),cleared)
    page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),expected)
    export(page,tmp_path/'preset.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'preset.png')),expected)
    page.reload();row(page,'track').click();np.testing.assert_array_equal(pixels(page),expected);panel(page)
    expect(page.get_by_label('本机滤镜预设').locator('option')).to_have_count(3)
    before=client.get('/api/project').json()
    page.get_by_label('滤镜预设文件',exact=True).set_input_files({'name':'bad.json','mimeType':'application/json','buffer':b'{broken'})
    expect(page.get_by_role('alert')).to_contain_text('无法读取滤镜预设')
    assert client.get('/api/project').json()==before


def test_preset_failed_save_retains_name_and_applies_only_to_selected_object(edge_page,running_app,tmp_path):
    page=edge_page;client=running_app['client'];fixture_track(page,tmp_path);panel(page)
    entry=add_filter(page,'AdjustmentFilter');entry.get_by_label('亮度',exact=True).fill('.6');pixels(page)
    page.get_by_label('滤镜预设名称',exact=True).fill('可重试')
    page.route('**/api/filter-presets',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"测试保存失败"}'),times=1)
    page.get_by_role('button',name='保存为滤镜预设',exact=True).click();expect(page.get_by_role('alert')).to_contain_text('测试保存失败')
    expect(page.get_by_label('滤镜预设名称',exact=True)).to_have_value('可重试')
    assert client.get('/api/filter-presets').json()==[]
    page.get_by_role('button',name='保存为滤镜预设',exact=True).click();expect(page.get_by_text('预设已保存到本机',exact=True)).to_be_visible()
    key=page.get_by_label('本机滤镜预设').input_value();track=client.get('/api/project').json()['project']['filters']
    row(page,'title1').click();page.get_by_label('本机滤镜预设').select_option(key)
    page.get_by_role('button',name='应用滤镜预设',exact=True).click();expect(page.get_by_text('已应用预设，可撤销',exact=True)).to_be_visible();pixels(page)
    filters=client.get('/api/project').json()['project']['filters']
    assert filters[0]==track[0] and filters[1]['targets']==['title1'] and filters[1]['params']['brightness']==.6
