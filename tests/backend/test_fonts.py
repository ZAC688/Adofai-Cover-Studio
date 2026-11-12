import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen

from backend.app.api import create_app
from backend.app.schema import Project,default_project
from backend.app.storage import Store

ROOT=Path(__file__).resolve().parents[2]


def font_bytes(extension):
    raw=(ROOT/'frontend/public/fonts/inter.ttf').read_bytes()
    if extension=='ttf':return raw
    output=io.BytesIO()
    if extension in {'woff','woff2'}:
        with TTFont(io.BytesIO(raw)) as font:font.flavor=extension;font.save(output)
    else:
        builder=FontBuilder(1000,isTTF=False)
        builder.setupGlyphOrder(['.notdef','A']);builder.setupCharacterMap({65:'A'})
        charstrings={}
        for name in ['.notdef','A']:
            pen=T2CharStringPen(600,None);pen.moveTo((0,0));pen.lineTo((300,700));pen.lineTo((600,0));pen.closePath()
            charstrings[name]=pen.getCharString()
        builder.setupCFF('TestOTF',{'FullName':'Test OTF','FamilyName':'Test OTF','Weight':'Regular'},charstrings,{})
        builder.setupHorizontalMetrics({'.notdef':(600,0),'A':(600,0)})
        builder.setupHorizontalHeader(ascent=800,descent=-200)
        builder.setupNameTable({'familyName':'Test OTF','styleName':'Regular','uniqueFontIdentifier':'TestOTF','fullName':'Test OTF','psName':'TestOTF'})
        builder.setupOS2(sTypoAscender=800,sTypoDescender=-200,usWinAscent=800,usWinDescent=200)
        builder.setupPost();builder.save(output)
    return output.getvalue()


@pytest.mark.parametrize('extension',['ttf','otf','woff','woff2'])
def test_supported_fonts_are_validated_and_roundtrip(tmp_path,extension):
    raw=font_bytes(extension);store=Store(tmp_path)
    record=store.put_font(raw)
    assert record['extension']==extension
    assert store.font_info(record['id'])['path'].read_bytes()==raw
    document=default_project();document['titles'][0]['fontId']=record['id']
    store.save(0,Project.model_validate(document))
    restored=Store(tmp_path)
    assert restored.load()['project']['titles'][0]['fontId']==record['id']
    assert restored.load()['project']['titles'][1]['fontId']=='system'
    assert restored.list_fonts()[0]['id']==record['id']


def test_bad_font_and_missing_font_never_clear_existing_project(tmp_path):
    store=Store(tmp_path)
    with pytest.raises(ValueError):store.put_font(b'OTTOtruncated')
    with pytest.raises(ValueError):store.put_font(b'not a font')
    assert store.list_fonts()==[]
    document=default_project();document['titles'][0]['fontId']='f'*32
    with pytest.raises(FileNotFoundError):store.save(0,Project.model_validate(document))
    assert store.load()['revision']==0


def test_font_upload_limit_and_mime_are_independent_from_image_limit(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        client.headers['x-editor-token']=client.get('/api/session').json()['token']
        raw=font_bytes('ttf')
        exact=raw+bytes(50_000_000-len(raw))
        accepted=client.post('/api/fonts',files={'file':('font.ttf',exact,'application/octet-stream')})
        assert accepted.status_code==200,accepted.text
        assert client.get('/api/fonts/'+accepted.json()['id']).headers['content-type']=='font/ttf'
        rejected=client.post('/api/fonts',files={'file':('font.ttf',exact+b'0','font/ttf')})
        assert rejected.status_code==413
        assert len(client.get('/api/fonts').json())==1
        assert client.get('/api/project').json()['revision']==0


def test_old_title_without_font_field_keeps_original_font():
    document=default_project()
    for title in document['titles']:title.pop('fontId')
    assert all(title.fontId=='system' for title in Project.model_validate(document).titles)
