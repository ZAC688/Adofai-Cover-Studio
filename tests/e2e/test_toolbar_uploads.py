from PIL import Image
from playwright.sync_api import expect
from .test_effects import pixels
from .conftest import ROOT


def test_top_upload_buttons_use_file_picker_and_object_list_has_more_space(edge_page,running_app,tmp_path):
    page=edge_page;pixels(page)
    for width,height in [(1440,1000),(1050,760)]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.locator('.topbar').evaluate('e=>e.scrollWidth<=e.clientWidth')
        box=page.locator('.object-list').bounding_box()
        assert box['height']>height-510+80
        for label in ['上传底图','上传轨道']:
            button=page.get_by_role('button',name=label,exact=True)
            expect(button).to_have_count(1)
            assert button.evaluate('e=>!!e.closest("header.topbar")')
            rect=button.bounding_box();assert rect['y']<80 and rect['x']+rect['width']<=width
    background=tmp_path/'background.png';Image.new('RGB',(640,360),(30,60,90)).save(background)
    with page.expect_file_chooser() as picker:page.get_by_role('button',name='上传底图',exact=True).click()
    picker.value.set_files(str(background));expect(page.locator('.asset-meta')).to_contain_text('640 × 360');pixels(page)
    with page.expect_file_chooser() as picker:page.get_by_role('button',name='上传轨道',exact=True).click()
    picker.value.set_files(str(ROOT/'test-assets/reference/transparent-fixture.png'));expect(page.locator('.asset-meta')).to_contain_text('1406 × 1123');pixels(page)
    doc=running_app['client'].get('/api/project').json()['project'];assert doc['bgAsset'] and doc['trackAsset'] and doc['bgAsset']!=doc['trackAsset']
    page.set_viewport_size({'width':1440,'height':1000})
    directory=ROOT/'artifacts/upgrade-06/04-layout';directory.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(directory/'editor.png'))
