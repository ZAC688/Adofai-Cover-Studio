import io,json
from PIL import Image
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.app.api import create_app
from backend.app.schema import ChartRecipe


def chart_bytes():
    return json.dumps({'pathData':'RRRRUULLDDRRRR','settings':{'bpm':100,'trackColor':'336699'},'actions':[
        {'floor':2,'eventType':'SetSpeed','speedType':'Bpm','beatsPerMinute':200},
        {'floor':5,'eventType':'SetSpeed','speedType':'Multiplier','bpmMultiplier':.5},
        {'floor':7,'eventType':'Twirl'}]}).encode()


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        c.headers['x-editor-token']=c.get('/api/session').json()['token']
        yield c


def imported(client):
    response=client.post('/api/charts',files={'file':('map.adofai',chart_bytes(),'application/json')})
    assert response.status_code==200,response.text
    return response.json()


def recipe(source,**changes):
    return ChartRecipe(sourceId=source['id'],start=1,end=9,resolution=1920,**changes).model_dump()


def test_source_import_raw_bytes_and_recipe_survive_service_restart(client,tmp_path):
    source=imported(client);settings=recipe(source)
    rendered=client.post('/api/charts/render',json=settings)
    assert rendered.status_code==200,rendered.text
    result=rendered.json();doc=client.get('/api/project').json()
    doc['project'].update(trackAsset=result['asset']['id'],generatedTrack=result['recipe'])
    assert client.put('/api/project',json={'baseRevision':doc['revision'],'project':doc['project']}).status_code==200
    assert (tmp_path/'charts'/f'{source["id"]}.adofai').read_bytes()==chart_bytes()
    with TestClient(create_app(tmp_path)) as other:
        loaded=other.get('/api/project').json()
        assert loaded['project']['generatedTrack']==settings
        assert loaded['assets'][result['asset']['id']]==result['asset']


def test_gold_stone_texture_and_reference_icons_are_real_pixels(client):
    result=client.post('/api/charts/render',json=recipe(imported(client),style='gold')).json()
    image=Image.open(io.BytesIO(client.get('/api/assets/'+result['asset']['id']).content)).convert('RGBA')
    data=np.asarray(image);opaque=data[data[:,:,3]==255,:3]
    gold=opaque[(opaque[:,0]>170)&(opaque[:,1]>140)&(opaque[:,2]<160)]
    assert len(gold)>1000 and gold[:,0].std()>3
    assert np.any(np.all(opaque==[223,73,60],axis=1)) # reference-inspired red rabbit
    assert image.getchannel('A').getextrema()==(0,255)


def test_palette_mode_preserves_chart_color_and_exact_selection(client):
    source=imported(client);result=client.post('/api/charts/render',json=recipe(source,style='chart')).json()
    data=np.asarray(Image.open(io.BytesIO(client.get('/api/assets/'+result['asset']['id']).content)))
    assert np.any(np.all(data==[51,102,153,255],axis=2))
    assert result['recipe']['start']==1 and result['recipe']['end']==9


def test_embedded_editor_has_gold_default_safe_inline_data_and_source(client):
    source=imported(client)
    response=client.post('/api/charts/'+source['id']+'/editor',json=None)
    assert response.status_code==200
    html=response.json()['html']
    assert '"defaultStyle":"gold"' in html and 'data:image/png;base64,' in html
    assert '"embedded":true' in html and source['id'] in html
    assert '/*__TRACK_DATA__*/' not in html


@pytest.mark.parametrize('name,data',[('wrong.png',b'{}'),('broken.adofai',b'{bad'),('empty.adofai',b'{"angleData":[]}'),('huge.adofai',b'x'*10_000_001)])
def test_import_failure_keeps_original_project_and_leaves_no_source(client,tmp_path,name,data):
    before=client.get('/api/project').json()
    assert client.post('/api/charts',files={'file':(name,data)}).status_code in (400,413)
    assert client.get('/api/project').json()==before
    assert list((tmp_path/'charts').iterdir())==[]


def test_invalid_crop_or_missing_source_cannot_replace_saved_project(client):
    source=imported(client);value=recipe(source);value['crop']=[2,0,1,1]
    assert client.post('/api/charts/render',json=value).status_code==422
    value=recipe(source);value['sourceId']='f'*32
    assert client.post('/api/charts/render',json=value).status_code==404
    assert client.get('/api/project').json()['revision']==0


def test_generated_recipe_references_are_checked_on_save(client):
    source=imported(client);rendered=client.post('/api/charts/render',json=recipe(source)).json()
    doc=client.get('/api/project').json();doc['project'].update(trackAsset=rendered['asset']['id'],generatedTrack=recipe(source))
    doc['project']['generatedTrack']['end']=200
    assert client.put('/api/project',json={'baseRevision':0,'project':doc['project']}).status_code==400
    assert client.get('/api/project').json()['revision']==0
