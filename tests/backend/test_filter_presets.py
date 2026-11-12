import io,json,base64,hashlib
from copy import deepcopy
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.api import create_app
from backend.app.storage import Store
from backend.app.filter_presets import Presets,SavePreset
from tests.backend.test_filters import spec,CATALOG


def resource_preset(store):
    texture=store.put_pixels(Image.new('RGBA',(64,64),(80,140,210,255)),'image')
    mask=store.put_pixels(Image.new('L',(1920,1080),127),'mask')
    first=spec('SimpleLightmapFilter');first['params']['lightMap']=texture['id'];first['targets']=['track','title1']
    first['regions']={'16:9':{'mode':'paint','maskAsset':mask['id']},'4:3':{'mode':'rect','x':.1,'y':.2,'width':.6,'height':.7,'feather':17}}
    second=spec('AdjustmentFilter');second['id']='b'*32;second['enabled']=False;second['params']['brightness']=.37
    return SavePreset(name='带贴图和范围',filters=[first,second])


def test_export_import_into_fresh_store_is_self_contained_and_pixel_exact(tmp_path):
    source=Store(tmp_path/'source');presets=Presets(source);before=source.load();body=resource_preset(source)
    saved=presets.save(body);file=presets.get(saved['id']);assert len(file['assets'])==2
    assert all(f['targets']==['track'] for f in file['filters'])
    assert source.load()==before
    assert Presets(Store(tmp_path/'source')).list()==[saved]
    other=Store(tmp_path/'new-computer');library=Presets(other)
    imported=library.import_file(json.dumps(file).encode('utf-8'));prepared=library.prepare(imported['id'])
    assert len(prepared['assets'])==2 and len(prepared['filters'])==2
    assert other.load()['revision']==0
    for old,new in zip(file['filters'],prepared['filters']):
        assert old['id']!=new['id'];assert old['type']==new['type'] and old['enabled']==new['enabled']
    new=prepared['filters'][0];assert new['regions']['4:3']==file['filters'][0]['regions']['4:3']
    for old_id,new_id in [(body.filters[0].params['lightMap'],new['params']['lightMap']),(body.filters[0].regions['16:9'].maskAsset,new['regions']['16:9']['maskAsset'])]:
        assert old_id!=new_id
        assert source.asset_path(old_id).read_bytes()==other.asset_path(new_id).read_bytes()
    assert library.prepare(imported['id'])['filters'][0]['id']!=new['id']


@pytest.mark.parametrize('bad',['version','missing','corrupt','size','extra','filter','duplicate','json'])
def test_invalid_import_preserves_presets_project_and_assets(tmp_path,bad):
    store=Store(tmp_path);library=Presets(store);saved=library.save(resource_preset(store));file=library.get(saved['id'])
    before=store.load();existing=library.list();files=set((tmp_path/'assets').iterdir())
    first=next(iter(file['assets']))
    if bad=='version':file['schemaVersion']=2
    elif bad=='missing':del file['assets'][first]
    elif bad=='corrupt':file['assets'][first]['sha256']='0'*64
    elif bad=='size':
        key=file['filters'][0]['regions']['16:9']['maskAsset'];raw=io.BytesIO();Image.new('L',(10,10)).save(raw,'PNG');data=raw.getvalue()
        file['assets'][key].update(png=base64.b64encode(data).decode(),sha256=hashlib.sha256(data).hexdigest())
    elif bad=='extra':file['assets']['f'*32]=deepcopy(file['assets'][first])
    elif bad=='filter':file['filters'][0]['type']='Unknown'
    elif bad=='duplicate':file['filters'][1]['id']=file['filters'][0]['id']
    with pytest.raises(ValueError):library.import_file(b'not json' if bad=='json' else json.dumps(file).encode())
    assert store.load()==before and library.list()==existing and set((tmp_path/'assets').iterdir())==files


def test_all_38_filter_defaults_roundtrip_through_api_and_presets_reopen(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        client.headers['x-editor-token']=client.get('/api/session').json()['token']
        filters=[]
        for i,entry in enumerate(CATALOG):
            item=spec(entry['type']);item['id']=f'{i:032x}';filters.append(item)
        saved=client.post('/api/filter-presets',json={'name':'全部38种','filters':filters})
        assert saved.status_code==200,saved.text
        key=saved.json()['id'];export=client.get('/api/filter-presets/'+key).json()
        imported=client.post('/api/filter-presets/import',files={'file':('preset.json',json.dumps(export).encode(),'application/json')});assert imported.status_code==200
        prepared=client.post('/api/filter-presets/'+key+'/prepare').json()
        assert [f['params'] for f in prepared['filters']]==[f['params'] for f in filters]
        assert len(client.get('/api/filter-presets').json())==2
    assert len(Presets(Store(tmp_path)).list())==2
