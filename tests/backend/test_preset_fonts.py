from pathlib import Path
import hashlib
import json
from fontTools.ttLib import TTFont
from backend.app.fonts import BUILTIN_FONTS
from backend.app.schema import Project,default_project
from backend.app.storage import Store

ROOT=Path(__file__).resolve().parents[2]

def test_all_preset_fonts_have_valid_hashes_licenses_and_preserved_face_metadata(tmp_path):
    directory=ROOT/'frontend/public/fonts';manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    entries=manifest['fonts'];assert len(entries)==10
    assert {e['id'] for e in entries}|{'system'}==BUILTIN_FONTS
    assert len({e['sha256'] for e in entries})==10
    store=Store(tmp_path)
    for entry in entries:
        path=directory/entry['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['sha256']
        with TTFont(path) as font:
            assert font.getBestCmap()
            if 'weight' in entry:
                assert font['OS/2'].usWeightClass==entry['weight']
                assert bool(font['head'].macStyle&2)==(entry['style']=='italic')
        p=default_project();p['titles'][0]['fontId']=entry['id'];store.save(store.load()['revision'],Project.model_validate(p))
        assert Store(tmp_path).load()['project']['titles'][0]['fontId']==entry['id']
    for family in ['Bebas_Neue','Russo_One','Space_Mono']:
        assert 'SIL OPEN FONT LICENSE' in (directory/f'{family}-OFL.txt').read_text(encoding='utf-8')
    assert not any('clash' in p.name.lower() or 'tanker' in p.name.lower() for p in directory.rglob('*'))
