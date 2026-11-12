from copy import deepcopy
import pytest
from pydantic import ValidationError
from backend.app.schema import default_project,Project
from backend.app.storage import Store


def test_rotation_persists_per_layout_and_old_data_defaults_to_zero(tmp_path):
    document=default_project()
    # Only the four original placements existed in legacy documents. The new
    # extraTitles/extraTracks fields are containers rather than placements.
    for key in ['bg','track','title1','title2']:document['layouts']['16:9'][key].pop('rotation')
    old=Project.model_validate(document)
    for key in ['bg','track','title1','title2']:assert getattr(old.layouts['16:9'],key).rotation==0
    document=default_project();document['layouts']['4:3']=deepcopy(document['layouts']['16:9'])
    document['layouts']['16:9']['track']['rotation']=45
    document['layouts']['4:3']['track']['rotation']=-30
    document['layouts']['16:9']['title1']['rotation']=90
    store=Store(tmp_path);store.save(0,Project.model_validate(document))
    assert Store(tmp_path).load()['project']==document


@pytest.mark.parametrize('angle',[float('inf'),float('nan'),361,-361])
def test_invalid_rotation_rejected(angle):
    document=default_project();document['layouts']['16:9']['title1']['rotation']=angle
    with pytest.raises(ValidationError):Project.model_validate(document)
