from pathlib import Path
from copy import deepcopy
import io
import hashlib
import pytest
import numpy as np
from PIL import Image
from pydantic import ValidationError
from backend.app.schema import Project,default_project
from backend.app.storage import Store
from tests.backend.test_api import client

ROOT=Path(__file__).resolve().parents[2]


def test_catalog_preserves_every_folder_and_animated_frame(client):
    items=client.get('/api/stickers').json();files=[p for p in (ROOT/'Logos').rglob('*') if p.suffix.lower() in {'.png','.gif'}]
    assert len(items)==len(files)==253
    byid={item['id']:item for item in items}
    for path in files:
        relative=path.relative_to(ROOT/'Logos');id=hashlib.sha256(relative.as_posix().encode()).hexdigest()[:32]
        item=byid[id];assert item['category']==list(relative.parts[:-1])
        assert item['name']==path.stem and 'path' not in item
        with Image.open(path) as original:
            assert item['frames']==getattr(original,'n_frames',1)
            if item['frames']>1:
                frame=item['frames']-1;original.seek(frame)
                response=client.post(f'/api/stickers/{id}/import',json={'frame':frame});assert response.status_code==200
                saved=client.get('/api/assets/'+response.json()['asset']['id'])
                np.testing.assert_array_equal(np.array(Image.open(io.BytesIO(saved.content)).convert('RGBA')),np.array(original.convert('RGBA')))
                np.testing.assert_array_equal(np.array(Image.open(io.BytesIO(client.get(f'/api/stickers/{id}/frames/{frame}').content)).convert('RGBA')),np.array(original.convert('RGBA')))


def test_invalid_preset_and_frame_do_not_change_project(client):
    before=client.get('/api/project').json();item=client.get('/api/stickers').json()[0]
    assert client.post('/api/stickers/'+'a'*32+'/import',json={'frame':0}).status_code==404
    assert client.post(f"/api/stickers/{item['id']}/import",json={'frame':item['frames']}).status_code==400
    assert client.get(f"/api/stickers/{item['id']}/frames/-1").status_code==400
    assert client.get('/api/project').json()==before


def test_more_than_eleven_layers_reopen_with_independent_sticker_layouts_and_assets(tmp_path):
    store=Store(tmp_path);asset=store.put_pixels(Image.new('RGBA',(20,30),'red'),'image');p=default_project()
    for i in range(100):
        key=f'sticker_{i:032x}';p['stickers'][key]={'asset':asset['id'],'name':f'贴纸{i}','presetId':'f'*32,'frame':0,'shadow':None}
        p['layerOrder'].insert(0,key);p['layouts']['16:9']['stickers'][key]={'x':i,'y':50,'scale':1,'rotation':i}
    p['layouts']['4:3']=deepcopy(p['layouts']['16:9']);store.save(0,Project.model_validate(p))
    assert Store(tmp_path).load()['project']==p
    invalid=deepcopy(p);invalid['layerOrder'].append('track6')
    with pytest.raises(ValidationError):Project.model_validate(invalid)
    invalid=deepcopy(p);invalid['layouts']['4:3']['stickers'].pop(next(iter(p['stickers'])))
    with pytest.raises(ValidationError):Project.model_validate(invalid)
    missing=deepcopy(p);missing['stickers'][next(iter(p['stickers']))]['asset']='b'*32
    with pytest.raises(FileNotFoundError):store.save(1,Project.model_validate(missing))
    assert Store(tmp_path).load()['project']==p
