from backend.app.schema import Project,default_project
from backend.app.storage import Store

def test_new_store_is_dark_and_existing_values_are_never_migrated_to_zero(tmp_path):
    store=Store(tmp_path);p=store.load()['project']
    assert p['trackGlow']==0 and [t['glow'] for t in p['titles']]==[0,0]
    p['trackGlow']=73;p['titles'][0]['glow']=42;p['titles'][1]['glow']=19
    store.save(0,Project.model_validate(p));assert Store(tmp_path).load()['project']==p
    assert default_project()['trackGlow']==0
