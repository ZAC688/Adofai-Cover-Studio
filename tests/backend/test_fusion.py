from copy import deepcopy
import pytest
from PIL import Image
from pydantic import ValidationError
from backend.app.schema import Project,default_project
from backend.app.storage import Store
from tests.backend.test_objects import full_project


def test_fusion_mask_and_modes_reopen_independently_of_recognition_masks(tmp_path):
    store=Store(tmp_path);p=full_project();item=p['extraTracks']['track2']
    item['trackAsset']=store.put_pixels(Image.new('RGBA',(64,32),'red'),'image')['id']
    item['maskAsset']=store.put_pixels(Image.new('L',(64,32),100),'mask')['id']
    fusion_mask=store.put_pixels(Image.new('L',(64,32),180),'mask')['id']
    item['fusion']={'enabled':True,'maskAsset':fusion_mask,'mode':'soft-light','opacity':51}
    store.save(0,Project.model_validate(p));assert Store(tmp_path).load()['project']==p
    bad=deepcopy(p);bad['extraTracks']['track2']['fusion']['maskAsset']=store.put_pixels(Image.new('L',(10,10)),'mask')['id']
    with pytest.raises(ValueError,match='融合蒙版'):store.save(1,Project.model_validate(bad))
    assert store.load()['project']==p
    old=default_project();old.pop('fusion');assert Project.model_validate(old).fusion is None


@pytest.mark.parametrize('field,value',[('mode','unknown'),('opacity',101),('opacity',-1),('maskAsset','../bad')])
def test_invalid_fusion_parameters_are_rejected(field,value):
    p=default_project();p['fusion']={field:value}
    with pytest.raises(ValidationError):Project.model_validate(p)


@pytest.mark.parametrize('field,value',[('position',-1),('position',101),('width',0),('width',201),('angle',181),('angle',float('nan')),('mode','screen')])
def test_gradient_rejects_invalid_parameters_and_legacy_options(field,value):
    p=default_project();p['fusion']={'kind':'gradient',field:value}
    with pytest.raises(ValidationError):Project.model_validate(p)


def test_gradient_parameters_and_mask_survive_store_reopen(tmp_path):
    store=Store(tmp_path);p=default_project()
    p['trackAsset']=store.put_pixels(Image.new('RGB',(40,20),'red'),'image')['id']
    p['fusion']={'kind':'gradient','enabled':True,'maskAsset':store.put_pixels(Image.new('L',(40,20),180),'mask')['id'],
                 'position':37,'width':78,'angle':-60,'reverse':True}
    store.save(0,Project.model_validate(p));assert Store(tmp_path).load()['project']==p
