import xml.etree.ElementTree as ET

from playwright.sync_api import expect

from .test_chart_editor import open_new
from .test_effects import pixels


def test_reference_relief_reaches_live_preview_svg_and_applied_track(edge_page,running_app,tmp_path):
    page=edge_page;errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    frame=open_new(page)
    frame.locator('#resolution').select_option('1920')
    canvas=frame.locator('#preview')
    expect(frame.locator('#range-summary')).to_contain_text('块')
    # Wait for the actual image pattern, not the temporary flat loading fill.
    page.wait_for_function("()=>{const w=document.querySelector('iframe').contentWindow;return w.eval('stoneReady');}")
    data=canvas.evaluate("c=>Array.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data)")
    assert len(set(tuple(data[i:i+3]) for i in range(0,len(data),4) if data[i+3]==255))>300
    with page.expect_download() as event:
        frame.get_by_role('button',name='导出 SVG',exact=True).click()
    target=tmp_path/'track.svg';event.value.save_as(target)
    svg=ET.parse(target).getroot()
    assert svg.findall('.//{*}polyline[@data-detail="bevel"]')
    assert {e.attrib['stroke'] for e in svg.findall('.//{*}polyline[@data-detail="bevel"]')}=={'#f2d898ff','#a18a56ff'}
    assert any(e.attrib.get('stroke')=='#8552a9ff' for e in svg.iter())
    before=running_app['client'].get('/api/project').json()
    frame.get_by_role('button',name='生成并预览',exact=True).click()
    expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=20000)
    assert running_app['client'].get('/api/project').json()==before
    page.get_by_role('button',name='应用到封面',exact=True).click();pixels(page)
    page.screenshot(path='artifacts/upgrade-08/01-style/editor.png')
    assert not errors
