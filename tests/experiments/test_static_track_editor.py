import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
from playwright.sync_api import sync_playwright, expect
import pytest

from experiments.static_track_probe import build_track
from experiments.static_track_editor import generate_editor
from experiments.static_track_export import fit_bounds, render_selection, selection_scene


@pytest.fixture(scope='module')
def sample_chart():
    return {'angleData': [0]*24+[90]*8+[180]*24,
            'settings': {'song': 'Vector & offline <3', 'bpm': 100, 'trackColor': '336699'},
            'actions': [{'floor': 3, 'eventType': 'SetSpeed', 'speedType': 'Bpm', 'beatsPerMinute': 200},
                        {'floor': 6, 'eventType': 'SetSpeed', 'speedType': 'Multiplier', 'bpmMultiplier': .5},
                        {'floor': 9, 'eventType': 'Twirl'}, {'floor': 14, 'eventType': 'Twirl'},
                        {'floor': 30, 'eventType': 'Twirl'}]}


@pytest.fixture(scope='module')
def editor_file(tmp_path_factory, sample_chart):
    root = tmp_path_factory.mktemp('static-editor')
    for name, chart in [('A', sample_chart), ('B', {'pathData': 'RRR', 'settings': {'song': 'Second', 'trackColor': '00ff00'}})]:
        folder = root/'input'/name
        folder.mkdir(parents=True)
        (folder/'main.adofai').write_text(json.dumps(chart), encoding='utf-8')
    data = generate_editor(root/'input', root/'output', make_samples=False)
    return root/'output'/'index.html', data


@pytest.fixture(scope='module')
def static_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(static_browser, editor_file):
    context = static_browser.new_context(viewport={'width': 1440, 'height': 1050}, accept_downloads=True)
    external, errors = [], []
    def block(route):
        external.append(route.request.url)
        route.abort()
    context.route('http://**/*', block)
    context.route('https://**/*', block)
    p = context.new_page()
    p.on('pageerror', lambda error: errors.append(str(error)))
    p.goto(editor_file[0].as_uri())
    expect(p.locator('#range-summary')).to_contain_text('块')
    yield p
    context.close()
    assert not external, f'Offline editor made network requests: {external}'
    assert not errors, f'Browser errors: {errors}'


def download(page, selector, target):
    with page.expect_download() as event:
        page.locator(selector).click()
    event.value.save_as(target)
    expect(page.locator('#status')).to_contain_text('已导出')
    return event.value.suggested_filename


def set_range(page, start, end):
    page.locator('#start').fill(str(start))
    page.locator('#end').fill(str(end))
    expect(page.locator('#range-summary')).to_contain_text(f'{start}—{end}')


def test_browser_data_is_inline_and_script_safe(editor_file):
    path, data = editor_file
    html = path.read_text(encoding='utf-8')
    assert '/*__TRACK_DATA__*/' not in html
    assert '\\u003c3' in html and '\\u0026' in html
    assert len(data['charts']) == 2
    assert data['charts'][0]['color'] == '#336699ff'
    assert len(data['charts'][0]['tiles']) == 57
    assert set(data['templates']) == {'rabbit', 'turtle', 'midspin', 'checkpoint', 'twirl-cw', 'twirl-ccw'}


def test_python_export_is_real_4k_and_preserves_color(sample_chart, tmp_path):
    result = render_selection(build_track(sample_chart), tmp_path/'4k.png', start_floor=0, end_floor=20)
    assert result['view']['width'] == 3840 and result['view']['height'] == 2160
    with Image.open(tmp_path/'4k.png') as image:
        assert image.size == (3840, 2160)
        assert image.mode == 'RGBA'
        assert image.getchannel('A').getextrema() == (0, 255)
        assert (51, 102, 153, 255) in {color for _, color in image.getcolors(image.width*image.height)}


def test_browser_png_exports_full_resolution_not_preview_size(page, tmp_path):
    set_range(page, 0, 20)
    assert int(page.locator('#preview').get_attribute('width')) < 3840
    filename = download(page, '#export-png', tmp_path/'download.png')
    assert 'bricks-0-20_3840x2160.png' in filename
    with Image.open(tmp_path/'download.png') as image:
        assert image.size == (3840, 2160)
        assert image.getchannel('A').getextrema() == (0, 255)
        box = image.getchannel('A').getbbox()
        assert box[0] > 0 and box[1] > 0 and box[2] < image.width and box[3] < image.height


def test_svg_has_only_inclusive_selected_bricks_colors_and_all_three_icons(page, tmp_path):
    set_range(page, 2, 10)
    download(page, '#export-svg', tmp_path/'segment.svg')
    root = ET.parse(tmp_path/'segment.svg').getroot()
    bricks = root.findall('.//{*}polygon')
    assert {int(p.attrib['data-floor']) for p in bricks} == set(range(2, 11))
    assert {p.attrib['fill'] for p in bricks} == {'#336699ff'}
    assert {e.attrib['data-icon'] for e in root.iter() if 'data-icon' in e.attrib} == {'rabbit', 'turtle', 'twirl'}


def test_range_and_export_settings_survive_reload_and_chart_switch(page):
    set_range(page, 5, 18)
    page.locator('#aspect').select_option('4:3')
    page.locator('#resolution').select_option('2560')
    page.locator('#rotate-icons').uncheck()
    page.locator('#chart').select_option(index=1)
    expect(page.locator('#size-summary')).to_contain_text('3840 × 2160')
    page.locator('#chart').select_option(index=0)
    expect(page.locator('#start')).to_have_value('5')
    expect(page.locator('#end')).to_have_value('18')
    expect(page.locator('#size-summary')).to_contain_text('2560 × 1920')
    page.reload()
    expect(page.locator('#start')).to_have_value('5')
    expect(page.locator('#end')).to_have_value('18')
    expect(page.locator('#rotate-icons')).not_to_be_checked()
    expect(page.locator('#size-summary')).to_contain_text('2560 × 1920')


def test_invalid_endpoints_block_export_without_replacing_saved_range(page):
    set_range(page, 3, 15)
    page.locator('#start').fill('30')
    expect(page.locator('#export-png')).to_be_disabled()
    expect(page.locator('#status')).to_contain_text('请输入有效编号')
    page.reload()
    expect(page.locator('#start')).to_have_value('3')
    expect(page.locator('#end')).to_have_value('15')
    expect(page.locator('#export-png')).to_be_enabled()


def test_pointer_selects_correct_start_and_end_brick(page, sample_chart):
    track = build_track(sample_chart)
    set_range(page, 0, 20)
    def click_floor(floor, start, end):
        # Calculate from the independent Python renderer, not browser helpers.
        scene = selection_scene(track, start, end)
        b = scene['bounds']
        world = [b[0]-.04, b[1]-.04, b[2]+.04, b[3]+.04]
        element = page.locator('#preview')
        w, h = int(element.get_attribute('width')), int(element.get_attribute('height'))
        view = fit_bounds(world, w, h, max(4, round(min(w,h)*.05)))
        tile, box = track.tiles[floor], element.bounding_box()
        x = (tile.x*view['scale']+view['offset_x'])*box['width']/w
        y = (view['offset_y']-tile.y*view['scale'])*box['height']/h
        element.click(position={'x': x, 'y': y})
    page.locator('[data-mode=start]').click()
    click_floor(5, 0, 20)
    expect(page.locator('#start')).to_have_value('5')
    expect(page.locator('#range-summary')).to_contain_text('5—20')
    page.locator('[data-mode=end]').click()
    click_floor(12, 5, 20)
    expect(page.locator('#end')).to_have_value('12')


def test_drag_crop_is_applied_persisted_and_reset(page, tmp_path):
    set_range(page, 0, 20)
    page.locator('[data-mode=crop]').click()
    box = page.locator('#preview').bounding_box()
    page.mouse.move(box['x']+box['width']*.30, box['y']+box['height']*.30)
    page.mouse.down()
    page.mouse.move(box['x']+box['width']*.65, box['y']+box['height']*.70, steps=10)
    page.mouse.up()
    expect(page.locator('#crop-summary')).to_contain_text('已应用矩形裁切')
    page.reload()
    expect(page.locator('#crop-summary')).to_contain_text('已应用矩形裁切')
    download(page, '#export-png', tmp_path/'crop.png')
    with Image.open(tmp_path/'crop.png') as image:
        assert image.getchannel('A').getbbox() is not None
        assert image.getpixel((0, 0))[3] == 0
    page.locator('#reset-crop').click()
    expect(page.locator('#crop-summary')).to_contain_text('完整选段')


def test_four_by_three_and_tight_exports_have_requested_dimensions(page, tmp_path):
    set_range(page, 0, 20)
    page.locator('#aspect').select_option('4:3')
    page.locator('#resolution').select_option('1920')
    download(page, '#export-png', tmp_path/'four-three.png')
    assert Image.open(tmp_path/'four-three.png').size == (1920, 1440)
    page.locator('#aspect').select_option('tight')
    download(page, '#export-png', tmp_path/'tight.png')
    with Image.open(tmp_path/'tight.png') as image:
        assert image.width == 1920 and 64 <= image.height < 200


def test_icons_can_be_disabled_and_upright_changes_only_icon_geometry(page, tmp_path):
    set_range(page, 24, 45)
    # A Twirl lies on the vertical segment: upright must change its geometry.
    download(page, '#export-svg', tmp_path/'a.svg')
    page.locator('#rotate-icons').uncheck()
    download(page, '#export-svg', tmp_path/'b.svg')
    a, b = ET.parse(tmp_path/'a.svg').getroot(), ET.parse(tmp_path/'b.svg').getroot()
    assert [e.attrib for e in a.findall('.//{*}polygon')] == [e.attrib for e in b.findall('.//{*}polygon')]
    before = [e.attrib for e in a.iter() if 'data-icon' in e.attrib]
    after = [e.attrib for e in b.iter() if 'data-icon' in e.attrib]
    assert before and after and before != after
    set_range(page, 2, 10)
    page.locator('#icons').uncheck()
    download(page, '#export-svg', tmp_path/'no-icons.svg')
    assert not any('data-icon' in e.attrib for e in ET.parse(tmp_path/'no-icons.svg').getroot().iter())
