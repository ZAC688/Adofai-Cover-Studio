import json
from fastapi.testclient import TestClient
from backend.app.api import create_app
from backend.app.charts import metadata_text


def test_metadata_uses_artist_instead_of_chart_author_and_survives_restart(tmp_path):
    chart={'pathData':'RRU','settings':{'song':'<color=#ffaa00>Music &amp; Ice</color>','artist':'<b>Composer</b>\nName','author':'Level creator'}}
    raw=json.dumps(chart).encode()
    with TestClient(create_app(tmp_path)) as client:
        client.headers['x-editor-token']=client.get('/api/session').json()['token']
        before=client.get('/api/project').json()
        item=client.post('/api/charts',files={'file':('demo.adofai',raw)}).json()
        assert item['song']=='Music & Ice' and item['artist']=='Composer Name'
        assert client.get('/api/project').json()==before
        assert (tmp_path/'charts'/f'{item["id"]}.adofai').read_bytes()==raw
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get('/api/charts/'+item['id']).json()==item


def test_absent_metadata_is_empty_and_does_not_use_media_paths_or_mapper(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        client.headers['x-editor-token']=client.get('/api/session').json()['token']
        item=client.post('/api/charts',files={'file':('demo.adofai',json.dumps({'pathData':'RR','settings':{'author':'Mapper','songFilename':'private.ogg'}}).encode())}).json()
        assert item['song']==item['artist']==''


def test_metadata_controls_length_and_preserves_plain_unicode_and_less_than():
    assert metadata_text('  冰与火 <3  ' )=='冰与火 <3'
    assert metadata_text('💜'*500)=='💜'*300
    assert metadata_text(None)==metadata_text(['text'])==''
    assert metadata_text('one\x00two\tthree')=='one two three'
