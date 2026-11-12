import numpy as np
from playwright.sync_api import expect
from PIL import Image
from .test_editor import saved,select
from .test_effects import pixels
from .test_selection import upload_shape
from .test_export import export


def bounds(image):
    y,x=np.where(np.any(image[:,:,:3]!=[8,13,22],axis=2));return x.max()-x.min()+1,y.max()-y.min()+1


def test_title_rotation_changes_real_pixels_persists_and_exports(edge_page,tmp_path):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('ROTATE')
    page.get_by_label('发光强度',exact=True).fill('0');page.locator('.panel-heading').first.click()
    before=pixels(page);w,h=bounds(before)
    page.get_by_label('旋转角度',exact=True).fill('90');page.locator('.panel-heading').first.click()
    after=pixels(page);rw,rh=bounds(after)
    assert abs(rw-h)<=3 and abs(rh-w)<=3
    page.reload();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('90');after=pixels(page)
    export(page,tmp_path/'rotated.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'rotated.png')),after)


def test_rotated_track_outline_and_alpha_hit_testing_stay_aligned(edge_page,running_app,tmp_path):
    page=edge_page;upload_shape(page,tmp_path)
    page.get_by_label('旋转角度',exact=True).fill('45');page.locator('.panel-heading').first.click();pixels(page)
    expect(page.get_by_label('轨道选中轮廓').locator('g').first).to_have_attribute('transform',__import__('re').compile('rotate\\(45 '))
    p=running_app['client'].get('/api/project').json()['project']['layouts']['16:9']['track']
    canvas=page.get_by_label('封面画布');rect=canvas.bounding_box()
    x=(80-128)*p['scale'];y=(120-128)*p['scale'];c=2**-.5
    logical_x=p['x']+(x-y)*c;logical_y=p['y']+(x+y)*c
    select(page,'第一行标题')
    page.mouse.click(rect['x']+logical_x/1920*rect['width'],rect['y']+logical_y/1080*rect['height'])
    expect(page.locator('.object-row.selected')).to_contain_text('轨道图形')
    page.get_by_role('button',name='4:3',exact=True).click()
    page.get_by_label('旋转角度',exact=True).fill('-30');page.locator('.panel-heading').first.click()
    page.get_by_role('button',name='16:9',exact=True).click()
    expect(page.get_by_label('旋转角度',exact=True)).to_have_value('45')


def test_rotation_handle_is_interactive_and_undoable(edge_page):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('HANDLE')
    pixels(page)
    box=page.locator('.selection-box').bounding_box();knob=page.get_by_label('旋转手柄').bounding_box()
    cx=box['x']+box['width']/2;cy=box['y']+box['height']/2
    page.mouse.move(knob['x']+knob['width']/2,knob['y']+knob['height']/2);page.mouse.down();page.mouse.move(cx+100,cy,steps=5);page.mouse.up()
    assert abs(float(page.get_by_label('旋转角度',exact=True).input_value())-90)<3
    page.get_by_role('button',name='撤销',exact=True).click();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('0')
    saved(page)
