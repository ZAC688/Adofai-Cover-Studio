from copy import deepcopy
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app.api import create_app
from backend.app.schema import Project,Text3D,default_project
from backend.app.storage import Store
from tests.backend.test_fonts import font_bytes
from tests.backend.test_objects import full_project

ROOT=Path(__file__).resolve().parents[2]


def test_3d_parameters_roundtrip_all_title_slots_and_legacy_defaults(tmp_path):
    document=full_project()
    for index,title in enumerate(document['titles']):
        title['text3d']=Text3D(enabled=True,depth=20+index,rotationY=index*10,sideColor='#336699').model_dump()
    Store(tmp_path).save(0,Project.model_validate(document))
    assert Store(tmp_path).load()['project']==document
    for title in document['titles']:title.pop('text3d')
    restored=Project.model_validate(document)
    assert all(t.text3d is None for t in restored.titles)
    assert [t.text for t in restored.titles]==[t['text'] for t in document['titles']]


@pytest.mark.parametrize('field,value',[('depth',-1),('depth',201),('bevel',11),('rotationX',181),('rotationY',float('nan')),('rotationZ',-181),('perspective',101),('sideColor','red'),('lightElevation',91),('lightIntensity',9),('ambientIntensity',-1)])
def test_invalid_3d_configuration_is_rejected(field,value):
    document=default_project();document['titles'][0]['text3d']={field:value}
    with pytest.raises(ValidationError):Project.model_validate(document)


@pytest.mark.parametrize('extension',['ttf','otf','woff','woff2'])
def test_uploaded_font_real_outlines_and_chinese_fallback_without_mutating_project(tmp_path,extension):
    with TestClient(create_app(tmp_path,frontend=ROOT/'frontend/dist')) as client:
        client.headers['x-editor-token']=client.get('/api/session').json()['token']
        font=client.post('/api/fonts',files={'file':('font.'+extension,font_bytes(extension),'application/octet-stream')}).json()
        before=client.get('/api/project').json()
        response=client.post('/api/text-outline',json={'text':'AO 冰','color':'#ffffff','glow':0,'fontId':font['id']})
        assert response.status_code==200,response.text
        data=response.json();assert len(data['paths'])==3 and data['width']>500 and data['height']>500
        assert all('M' in path and 'Z' in path.upper() for path in data['paths'])
        assert data['missingCharacters']==[] and '冰' in data['fallbackCharacters']
        assert client.get('/api/project').json()==before
        assert client.post('/api/text-outline',json={'text':'A','color':'#ffffff','glow':0,'fontId':'../../secret'}).status_code==422


def test_all_bundled_faces_provide_distinct_vector_outlines(tmp_path):
    catalog=__import__('json').loads((ROOT/'frontend/public/fonts/manifest.json').read_text(encoding='utf-8'))
    with TestClient(create_app(tmp_path,frontend=ROOT/'frontend/dist')) as client:
        client.headers['x-editor-token']=client.get('/api/session').json()['token']
        paths=[]
        for font in catalog['fonts']:
            response=client.post('/api/text-outline',json={'text':'AVATAR 0123 冰','color':'#ffffff','glow':0,'fontId':font['id']})
            assert response.status_code==200,response.text
            data=response.json();assert data['paths'] and data['missingCharacters']==[]
            assert data['width']>0;paths.append(tuple(data['paths']))
        assert len(set(paths))==10
