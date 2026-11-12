from copy import deepcopy
import pytest
from pydantic import ValidationError
from backend.app.schema import Project,default_project
from backend.app.storage import Store
from tests.backend.test_objects import full_project


def test_shadows_are_independent_for_all_objects_and_old_defaults_are_disabled(tmp_path):
    old=default_project();old.pop('trackShadow')
    for title in old['titles']:title.pop('shadow')
    assert Project.model_validate(old).trackShadow is None
    document=full_project()
    shadow=dict(enabled=True,color='#224466',opacity=71,blur=23,distance=67,direction=45)
    document['titles'][4]['shadow']=deepcopy(shadow);document['extraTracks']['track4']['trackShadow']=deepcopy(shadow)
    store=Store(tmp_path);store.save(0,Project.model_validate(document));restored=Store(tmp_path).load()['project']
    assert restored==document
    assert restored['trackShadow'] is None and restored['titles'][0]['shadow'] is None


@pytest.mark.parametrize('field,value',[('opacity',101),('blur',-1),('distance',501),('direction',361),('color','red')])
def test_invalid_shadow_parameters_cannot_be_saved(field,value):
    p=default_project();p['trackShadow']={field:value}
    with pytest.raises(ValidationError):Project.model_validate(p)
