from copy import deepcopy
import pytest
from pydantic import ValidationError
from backend.app.schema import Project,default_project
from backend.app.storage import Store


def effect():
    return dict(enabled=True,color='#ff0088',color2='#00ccff',intensity=70,radius=24,width=5,direction=45,blend='add',followGradient=False)


def test_effects_roundtrip_for_title_and_track_and_old_projects(tmp_path):
    old=default_project();old.pop('trackEffects')
    for title in old['titles']:title.pop('effects')
    validated=Project.model_validate(old)
    assert validated.titles[0].effects is None
    current=default_project()
    settings={key:effect() for key in ['outerGlow','innerGlow','bloom','stroke','gradient','bevel','horizontalBlur']}
    current['titles'][0]['effects']=settings
    current['trackEffects']=deepcopy(settings)
    store=Store(tmp_path);store.save(0,Project.model_validate(current))
    restored=Store(tmp_path).load()['project']
    assert restored['titles'][0]['effects']==settings
    assert restored['trackEffects']==settings
    assert restored['titles'][1]['effects'] is None


def test_gradient_following_is_independent_persistent_and_defaults_off_for_old_effects(tmp_path):
    document=default_project();old=effect();old.pop('followGradient')
    document['titles'][0]['effects']={'outerGlow':old}
    assert not Project.model_validate(document).titles[0].effects['outerGlow'].followGradient
    settings={key:effect() for key in ['outerGlow','innerGlow','bloom','stroke','gradient','bevel','horizontalBlur']}
    settings['bloom']['followGradient']=True;settings['gradient']['enabled']=False
    document['trackEffects']=settings
    store=Store(tmp_path);store.save(0,Project.model_validate(document))
    restored=Store(tmp_path).load()['project'];assert restored['trackEffects']==settings
    assert not restored['titles'][0]['effects']['outerGlow']['followGradient']


@pytest.mark.parametrize('field,value',[('radius',-1),('radius',181),('intensity',101),('blend','multiply'),('width',81),('color','not-color')])
def test_invalid_effect_parameters_rejected(field,value):
    document=default_project();settings=effect();settings[field]=value
    document['titles'][0]['effects']={'outerGlow':settings}
    with pytest.raises(ValidationError):Project.model_validate(document)
