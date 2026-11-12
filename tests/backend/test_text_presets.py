import base64
import hashlib
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.app.storage import Store
from backend.app.api import create_app
from backend.app.schema import Title,Text3D,Shadow
from backend.app.text_presets import TextPresets,SaveTextPreset
from backend.app.filter_presets import Presets
from tests.backend.test_filter_presets import resource_preset
from tests.backend.test_fonts import font_bytes
from tests.backend.test_effects import effect


def style_body(store,with_resources=True,font_format='ttf'):
    title=Title(text='私有文案不应进入预设',color='#f184ca',glow=15,text3d=Text3D(enabled=True,depth=44,rotationZ=22),shadow=Shadow(enabled=True),effects={'outerGlow':effect()})
    filters=[]
    if with_resources:
        title.fontId=store.put_font(font_bytes(font_format))['id']
        filters=resource_preset(store).filters
    return SaveTextPreset(name='完整文字样式',style=title.model_dump(exclude={'text'}),fontSize=112,fontSizes={'16:9':112,'4:3':84},filters=filters)


@pytest.mark.parametrize('font_format',['ttf','otf','woff','woff2'])
def test_export_import_fresh_store_restores_font_3d_all_effects_and_filter_assets(tmp_path,font_format):
    source=Store(tmp_path/'source');library=TextPresets(source);body=style_body(source,font_format=font_format);before=source.load()
    saved=library.save(body);file=library.get(saved['id'])
    assert file['format']=='adofai-text-preset' and 'text' not in file['style']
    assert not {'position','rotation','x','y'}&file.keys()
    assert file['style']['text3d']['rotationZ']==22
    assert file['style']['effects']['outerGlow']==effect()
    assert len(file['assets'])==2 and file['font']
    assert source.load()==before and TextPresets(Store(tmp_path/'source')).list()==[saved]
    other=Store(tmp_path/'fresh');target=TextPresets(other)
    imported=target.import_file(json.dumps(file,ensure_ascii=False).encode('utf-8'))
    assert other.load()['revision']==0 and other.list_fonts()==[]
    prepared=target.prepare(imported['id']);newfont=prepared['style']['fontId']
    assert newfont!=body.style.fontId
    assert other.font_info(newfont)['path'].read_bytes()==source.font_info(body.style.fontId)['path'].read_bytes()
    assert prepared['style']=={**file['style'],'fontId':newfont}
    assert prepared['fontSizes']==file['fontSizes'] and prepared['fontSize']==112
    for old,new in zip(file['filters'],prepared['filters']):
        assert old['type']==new['type'] and old['enabled']==new['enabled'] and old['id']!=new['id']
    for old,new in [(body.filters[0].params['lightMap'],prepared['filters'][0]['params']['lightMap']),(body.filters[0].regions['16:9'].maskAsset,prepared['filters'][0]['regions']['16:9']['maskAsset'])]:
        assert source.asset_path(old).read_bytes()==other.asset_path(new).read_bytes()
    assert target.prepare(imported['id'])['style']['fontId']==newfont
    assert len(other.list_fonts())==1
    assert other.load()['revision']==0


def test_style_without_filters_or_3d_is_valid_and_old_filter_library_is_unchanged(tmp_path):
    store=Store(tmp_path);old=Presets(store);old_saved=old.save(resource_preset(store));old_file=old.get(old_saved['id'])
    body=style_body(store,False);body.style.text3d=None
    library=TextPresets(store);saved=library.save(body);file=library.get(saved['id'])
    assert file['filters']==[] and file['assets']=={} and file['font'] is None
    assert library.prepare(saved['id'])['style']['color']=='#f184ca'
    assert library.prepare(saved['id'])['style']['text3d'] is None
    assert old.list()==[old_saved] and old.get(old_saved['id'])==old_file


@pytest.mark.parametrize('bad',['version','content','placement','bad-size','invalid-style','missing-font','font-hash','font-data','missing-image','image-hash','filter-type','extra-image'])
def test_invalid_import_leaves_project_libraries_and_resources_unchanged(tmp_path,bad):
    store=Store(tmp_path);library=TextPresets(store);saved=library.save(style_body(store));file=library.get(saved['id'])
    before=store.load();items=library.list();assets=set((tmp_path/'assets').iterdir());fonts=set((tmp_path/'fonts').iterdir())
    if bad=='version':file['schemaVersion']=2
    elif bad=='content':file['style']['text']='must not restore this'
    elif bad=='placement':file['position']={'x':100,'y':100}
    elif bad=='bad-size':file['fontSizes']['4:3']=0
    elif bad=='invalid-style':file['style']['text3d']['depth']=999
    elif bad=='missing-font':file['font']=None
    elif bad=='font-hash':file['font']['sha256']='0'*64
    elif bad=='font-data':
        raw=b'not a font';file['font']={'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(raw).decode()}
    elif bad=='missing-image':file['assets'].pop(next(iter(file['assets'])))
    elif bad=='image-hash':file['assets'][next(iter(file['assets']))]['sha256']='0'*64
    elif bad=='filter-type':file['filters'][0]['type']='MissingFilter'
    elif bad=='extra-image':file['assets']['f'*32]=deepcopy(next(iter(file['assets'].values())))
    with pytest.raises(ValueError):library.import_file(json.dumps(file).encode())
    assert store.load()==before and library.list()==items
    assert set((tmp_path/'assets').iterdir())==assets and set((tmp_path/'fonts').iterdir())==fonts


def test_api_save_import_export_prepare_and_restart_without_project_changes(tmp_path):
    store=Store(tmp_path);body=style_body(store,False).model_dump()
    with TestClient(create_app(tmp_path)) as client:
        client.headers['x-editor-token']=client.get('/api/session').json()['token']
        before=client.get('/api/project').json()
        saved=client.post('/api/text-presets',json=body);assert saved.status_code==200,saved.text
        key=saved.json()['id'];exported=client.get('/api/text-presets/'+key).json()
        assert client.post('/api/text-presets/'+key+'/prepare').json()['style']['text3d']['depth']==44
        assert client.post('/api/text-presets/import',files={'file':('preset.json',json.dumps(exported).encode())}).status_code==200
        assert client.get('/api/project').json()==before
    assert len(TextPresets(Store(tmp_path)).list())==2
