import pytest
from playwright.sync_api import expect
from .test_selection import upload_shape
from .test_effects import pixels,open_effects


@pytest.mark.parametrize('kind',['track','title'])
def test_outline_appears_only_during_transform_and_hides_for_effect_controls(edge_page,running_app,tmp_path,kind):
    page=edge_page;upload_shape(page,tmp_path)
    if kind=='title':
        page.locator('[data-object-id="title1"]').click()
        page.get_by_label('标题内容',exact=True).fill('拖动时显示')
    pixels(page);canvas=page.get_by_label('封面画布');rect=canvas.bounding_box()
    project=running_app['client'].get('/api/project').json()['project']
    p=project['layouts']['16:9'][kind if kind=='track' else 'title1']
    if kind=='track':
        x=p['x']+(80-128)*p['scale'];y=p['y']+(120-128)*p['scale']
        overlay=page.get_by_label('轨道选中轮廓');expect(overlay).to_be_hidden()
    else:
        x=p['x']+30;y=p['y']+20
        overlay=page.locator('.selection-box')
        assert overlay.evaluate("e=>getComputedStyle(e).borderTopColor")=='rgba(0, 0, 0, 0)'
    x=rect['x']+x/1920*rect['width'];y=rect['y']+y/1080*rect['height']
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+15,y+8,steps=2)
    expect(page.locator('.canvas-stage')).to_have_class('canvas-stage manipulating')
    if kind=='track':expect(overlay).to_be_visible()
    else:assert overlay.evaluate("e=>getComputedStyle(e).borderTopColor")!='rgba(0, 0, 0, 0)'
    page.mouse.up();expect(page.locator('.canvas-stage')).to_have_class('canvas-stage')
    page.get_by_label('发光强度',exact=True).fill('32');open_effects(page)
    page.get_by_label('多尺度 Bloom开关',exact=True).check();page.get_by_label('多尺度 Bloom半径',exact=True).fill('25')
    pixels(page)
    if kind=='track':expect(overlay).to_be_hidden()
    else:assert overlay.evaluate("e=>getComputedStyle(e).borderTopColor")=='rgba(0, 0, 0, 0)'
    assert page.locator('.rotation-handle').evaluate("e=>getComputedStyle(e).opacity")=='0'
    # Cancel/lost-capture also ends the temporary visual state.
    page.mouse.move(x+15,y+8);page.mouse.down();page.mouse.move(x+20,y+10)
    canvas.dispatch_event('pointercancel');expect(page.locator('.canvas-stage')).to_have_class('canvas-stage')
    page.mouse.up()
