import numpy as np
from playwright.sync_api import expect
from .test_effects import pixels,open_effects
from .test_objects import add,row

def test_new_work_and_added_title_track_have_zero_glow_but_effect_can_be_enabled(edge_page,running_app):
    page=edge_page;client=running_app['client'];p=client.get('/api/project').json()['project']
    assert p['trackGlow']==0 and all(t['glow']==0 and t['effects'] is None for t in p['titles'])
    expect(page.get_by_label('发光强度',exact=True)).to_have_value('0')
    add(page,'标题');expect(page.get_by_label('发光强度',exact=True)).to_have_value('0')
    page.get_by_label('标题内容',exact=True).fill('CLEAR 新标题');baseline=pixels(page)
    open_effects(page);expect(page.get_by_label('外发光开关',exact=True)).not_to_be_checked()
    page.get_by_label('外发光开关',exact=True).check();assert np.any(pixels(page)!=baseline)
    add(page,'轨道');expect(page.get_by_label('发光强度',exact=True)).to_have_value('0');pixels(page)
    p=client.get('/api/project').json()['project'];assert p['extraTracks']['track2']['trackGlow']==0

def test_old_saved_glow_values_survive_reload_and_adding_new_objects(edge_page,running_app):
    page=edge_page;client=running_app['client'];p=client.get('/api/project').json()
    p['project']['titles'][0]['glow']=25;p['project']['titles'][1]['glow']=20;p['project']['trackGlow']=37
    assert client.put('/api/project',json={'baseRevision':p['revision'],'project':p['project']}).status_code==200
    page.reload()
    for id,value in [('title1','25'),('title2','20'),('track','37')]:
        row(page,id).click();expect(page.get_by_label('发光强度',exact=True)).to_have_value(value)
    add(page,'标题');expect(page.get_by_label('发光强度',exact=True)).to_have_value('0')
    add(page,'轨道');expect(page.get_by_label('发光强度',exact=True)).to_have_value('0');pixels(page)
    p=client.get('/api/project').json()['project'];assert [t['glow'] for t in p['titles']]==[25,20,0] and p['trackGlow']==37
