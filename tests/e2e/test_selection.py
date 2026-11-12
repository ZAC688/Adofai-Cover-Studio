from PIL import Image,ImageDraw
from playwright.sync_api import expect

from .test_editor import saved,select
from .test_effects import pixels,open_effects
from .test_export import export
import numpy as np
from .conftest import ROOT


def upload_shape(page,tmp_path):
    path=tmp_path/'concave.png';image=Image.new('RGBA',(256,256));draw=ImageDraw.Draw(image)
    draw.rectangle((64,64,95,191),fill='white');draw.rectangle((64,160,191,191),fill='white');draw.rectangle((74,80,85,95),fill=(0,0,0,0));image.save(path)
    page.get_by_label('轨道文件',exact=True).set_input_files(str(path))
    # Geometry stays available for hit testing; the outline is shown only during a drag.
    expect(page.get_by_label('轨道选中轮廓')).to_have_count(1)
    expect(page.get_by_label('轨道选中轮廓')).to_be_hidden()
    saved(page)


def test_outline_follows_concavity_holes_and_ignores_effects(edge_page,tmp_path):
    page=edge_page;upload_shape(page,tmp_path)
    outline=page.get_by_label('轨道选中轮廓').locator('path').last
    original_path=outline.get_attribute('d');assert original_path.count('M')==2
    assert original_path.count('L')>6
    assert page.locator('.selection-box').count()==0
    handles=page.get_by_label('轨道缩放手柄').bounding_box()
    page.get_by_label('发光强度',exact=True).fill('90');page.locator('.panel-heading').first.click()
    open_effects(page);page.get_by_label('多尺度 Bloom开关').check();pixels(page)
    assert outline.get_attribute('d')==original_path
    assert page.get_by_label('轨道缩放手柄').bounding_box()==handles
    content=pixels(page);export(page,tmp_path/'no-overlay.png')
    np.testing.assert_array_equal(np.array(Image.open(tmp_path/'no-overlay.png')),content)
    directory=ROOT/'artifacts/upgrade/04-selection';directory.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(directory/'outline.png'))


def test_transparent_padding_does_not_hit_track_but_body_does(edge_page,running_app,tmp_path):
    page=edge_page;upload_shape(page,tmp_path)
    project=running_app['client'].get('/api/project').json()['project'];p=project['layouts']['16:9']['track']
    canvas=page.get_by_label('封面画布');rect=canvas.bounding_box()
    def location(x,y):return rect['x']+(p['x']+(x-128)*p['scale'])/1920*rect['width'],rect['y']+(p['y']+(y-128)*p['scale'])/1080*rect['height']
    select(page,'第一行标题');x,y=location(160,90);page.mouse.click(x,y)
    expect(page.locator('.object-row.selected')).to_contain_text('第一行标题')
    x,y=location(80,120);page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+20,y+10,steps=3);page.mouse.up()
    expect(page.locator('.object-row.selected')).to_contain_text('轨道图形')
    saved(page)
    moved=running_app['client'].get('/api/project').json()['project']['layouts']['16:9']['track']
    assert moved['x']>p['x'] and moved['y']>p['y']
