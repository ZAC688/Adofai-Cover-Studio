import io
import json
from copy import deepcopy
from pathlib import Path
import pytest
from PIL import Image
from pydantic import ValidationError
from backend.app.schema import Project,default_project
from backend.app.storage import Store
from tests.backend.test_api import client

CATALOG=json.loads((Path(__file__).resolve().parents[2]/'frontend/public/filter-catalog.json').read_text(encoding='utf-8'))['filters']
def spec(kind='GrayscaleFilter'):
    entry=next(item for item in CATALOG if item['type']==kind)
    return dict(id='a'*32,type=kind,enabled=True,targets=['track'],params={field['key']:deepcopy(field['value']) for field in entry['fields']},regions={})

def test_all_filter_parameters_validate_and_old_projects_have_none(tmp_path):
    store=Store(tmp_path);p=default_project();p.pop('filters');assert Project.model_validate(p).filters==[]
    p=default_project()
    for i,item in enumerate(CATALOG):
        value=spec(item['type']);value['id']=f'{i:032x}';p['filters'].append(value)
    store.save(0,Project.model_validate(p));assert Store(tmp_path).load()['project']==p

@pytest.mark.parametrize('bad',['unknown','duplicate','target','number','missing_mask'])
def test_invalid_filter_data_does_not_overwrite_project(tmp_path,bad):
    store=Store(tmp_path);before=store.load();p=default_project();value=spec('AdjustmentFilter');p['filters']=[value]
    if bad=='unknown':value['type']='UnknownFilter'
    if bad=='duplicate':p['filters'].append(deepcopy(value))
    if bad=='target':value['targets']=['not-an-object']
    if bad=='number':value['params']['brightness']=float('inf')
    if bad=='missing_mask':value['regions']={'16:9':{'mode':'paint','maskAsset':'b'*32}}
    with pytest.raises((ValidationError,ValueError,FileNotFoundError)):store.save(0,Project.model_validate(p))
    assert store.load()==before

def test_filter_mask_requires_exact_canvas_coordinates(client):
    raw=io.BytesIO();Image.new('L',(1920,1080),128).save(raw,'PNG')
    asset=client.post('/api/filter-masks/16-9',files={'file':('mask.png',raw.getvalue(),'image/png')});assert asset.status_code==200
    assert client.post('/api/filter-masks/4-3',files={'file':('mask.png',raw.getvalue(),'image/png')}).status_code==400
