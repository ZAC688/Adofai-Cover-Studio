from copy import deepcopy
from PIL import Image
import pytest
from pydantic import ValidationError
from backend.app.schema import Project,default_project
from backend.app.storage import Store


def full_project():
    p=default_project()
    p['titles']+=[dict(p['titles'][0],text=f'title{i}') for i in range(3,6)]
    p['extraTracks']={f'track{i}':{key:deepcopy(p[key]) for key in ('trackAsset','maskAsset','baseMaskAsset','removeBackground','trackColor','trackGlow','trackEffects','trackShadow','fusion')} for i in range(2,6)}
    places=p['layouts']['16:9']
    places['extraTitles']={f'title{i}':dict(places['title1'],x=100*i,rotation=i*10) for i in range(3,6)}
    places['extraTracks']={f'track{i}':dict(places['track'],x=i*200,rotation=-i*10) for i in range(2,6)}
    p['layerOrder']=['title5','track5','title4','track4','title3','track3','title2','track2','title1','track','bg']
    p['layouts']['4:3']=deepcopy(places)
    p['layouts']['4:3']['extraTracks']['track2']['rotation']=19
    return p


def test_five_titles_five_tracks_assets_masks_order_and_both_layouts_reopen(tmp_path):
    store=Store(tmp_path);p=full_project()
    for i,item in enumerate([p,*p['extraTracks'].values()]):
        item['trackAsset']=store.put_pixels(Image.new('RGBA',(32+i,24),(i*40,100,200,255)),'image')['id']
        item['maskAsset']=store.put_pixels(Image.new('L',(32+i,24),150+i),'mask')['id']
        item['baseMaskAsset']=item['maskAsset'];item['removeBackground']=True;item['trackColor']=f'#{i:02x}bbdd'
    store.save(0,Project.model_validate(p));loaded=Store(tmp_path).load()
    assert loaded['project']==p and len(loaded['assets'])==10
    for item in [p,*p['extraTracks'].values()]:assert store.asset_path(item['maskAsset']).is_file()


@pytest.mark.parametrize('invalid',['six_titles','six_tracks','duplicate','background_above','no_background','unknown','missing_layout','missing_track'])
def test_invalid_object_counts_order_and_incomplete_layouts_are_rejected(invalid):
    p=full_project()
    if invalid=='six_titles':p['titles'].append(deepcopy(p['titles'][0]))
    elif invalid=='six_tracks':p['extraTracks']['track6']=deepcopy(p['extraTracks']['track2'])
    elif invalid=='duplicate':p['layerOrder'][0]='title1'
    elif invalid=='background_above':p['layerOrder']=['bg',*p['layerOrder'][:-1]]
    elif invalid=='no_background':p['layerOrder'].pop()
    elif invalid=='unknown':p['layerOrder'][0]='title6'
    elif invalid=='missing_layout':del p['layouts']['4:3']['extraTitles']['title3']
    elif invalid=='missing_track':del p['extraTracks']['track2']
    with pytest.raises(ValidationError):Project.model_validate(p)


def test_extra_track_missing_or_mismatched_mask_does_not_replace_saved_project(tmp_path):
    store=Store(tmp_path);p=full_project();before=store.load()
    p['extraTracks']['track2']['trackAsset']='a'*32
    with pytest.raises(FileNotFoundError):store.save(0,Project.model_validate(p))
    item=p['extraTracks']['track2'];item['trackAsset']=store.put_pixels(Image.new('RGBA',(20,20)),'image')['id']
    item['maskAsset']=store.put_pixels(Image.new('L',(10,10)),'mask')['id']
    with pytest.raises(ValueError,match='尺寸'):store.save(0,Project.model_validate(p))
    assert store.load()==before


def test_legacy_document_migrates_without_loss_or_revision_change(tmp_path):
    store=Store(tmp_path);legacy=default_project()
    legacy.pop('extraTracks');legacy.pop('layerOrder')
    for value in legacy['layouts'].values():
        if value:value.pop('extraTitles');value.pop('extraTracks')
    import json
    with store.connect() as db:db.execute('UPDATE project SET document=?',(json.dumps(legacy),))
    loaded=store.load();assert loaded['revision']==0
    assert loaded['project']['titles']==legacy['titles'];assert loaded['project']['layerOrder']==['title2','title1','track','bg']
    assert loaded['project']['layouts']['16:9']['title1']==legacy['layouts']['16:9']['title1']
