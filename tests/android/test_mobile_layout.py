import json
import io
from pathlib import Path

from playwright.sync_api import expect, sync_playwright
import pytest
from PIL import Image,ImageDraw

from tests.android.test_server import runtime_client


@pytest.fixture(scope='module')
def mobile_browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        yield browser
        browser.close()


@pytest.fixture
def phone(mobile_browser, runtime_client, request):
    client, _runtime = runtime_client
    context = mobile_browser.new_context(viewport={'width': 360, 'height': 804},
                                        device_scale_factor=2, is_mobile=True, has_touch=True)
    external = []
    address = str(client.base_url).rstrip('/')

    def network(route):
        if route.request.url.startswith(address + '/') or route.request.url.startswith(('blob:', 'data:')):
            route.continue_()
        else:
            external.append(route.request.url)
            route.abort()

    context.route('**/*', network)
    page = context.new_page()
    page.goto(address)
    expect(page.get_by_label('标题内容', exact=True)).to_be_visible()
    yield page, client
    evidence = Path('artifacts/android/layout')
    evidence.mkdir(parents=True, exist_ok=True)
    safe_name = ''.join(letter if letter.isalnum() else '-' for letter in request.node.name)
    page.screenshot(path=str(evidence / (safe_name + '.png')))
    assert not external, external
    context.close()


def no_horizontal_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def in_viewport(page, locator):
    expect(locator).to_be_visible()
    box = locator.bounding_box()
    viewport = page.viewport_size
    assert box['x'] >= -1 and box['y'] >= -1, box
    assert box['x'] + box['width'] <= viewport['width'] + 1, box
    assert box['y'] + box['height'] <= viewport['height'] + 1, box


@pytest.mark.parametrize('width,height', [(360, 804), (412, 915), (804, 360), (320, 568), (360, 420)])
def test_all_main_actions_and_tabs_fit_phone_screens(phone, width, height):
    page, _client = phone
    page.set_viewport_size({'width': width, 'height': height})
    for label in ('上传底图', '上传轨道', '信息'):
        in_viewport(page, page.get_by_role('button', name=label, exact=True))
    in_viewport(page, page.get_by_role('button', name='从谱面生成', exact=True))
    in_viewport(page, page.locator('.export-trigger'))
    for label in ('对象', '属性', '光效', '滤镜'):
        tab = page.get_by_role('tab', name=label, exact=True)
        in_viewport(page, tab)
        tab.tap()
        expect(tab).to_have_attribute('aria-selected', 'true')
        no_horizontal_overflow(page)
    canvas = page.get_by_label('封面画布', exact=True)
    in_viewport(page, canvas)
    box = canvas.bounding_box()
    assert box['width'] > 100 and box['height'] > 50
    assert abs(box['width'] / box['height'] - 16 / 9) < .02


def test_rotation_and_tabs_preserve_text_style_and_undo(phone):
    page, client = phone
    page.get_by_label('标题内容', exact=True).fill('手机封面 ADOFAI')
    page.get_by_label('字号', exact=True).fill('96')
    page.get_by_role('tab', name='光效', exact=True).tap()
    page.locator('.effects-panel > summary').tap()
    page.get_by_label('外发光开关', exact=True).check()
    page.get_by_label('外发光强度', exact=True).fill('35')
    page.set_viewport_size({'width': 804, 'height': 360})
    expect(page.get_by_label('外发光强度', exact=True)).to_have_value('35')
    page.get_by_role('tab', name='属性', exact=True).tap()
    expect(page.get_by_label('标题内容', exact=True)).to_have_value('手机封面 ADOFAI')
    expect(page.get_by_label('字号', exact=True)).to_have_value('96')
    expect(page.get_by_label('外发光开关', exact=True)).to_be_hidden()
    expect(page.locator('.save-state')).to_have_text('已保存到本机')
    saved = client.get('/api/project').json()['project']
    assert saved['titles'][0]['effects']['outerGlow']['intensity'] == 35
    page.reload()
    expect(page.get_by_label('标题内容', exact=True)).to_have_value('手机封面 ADOFAI')
    page.set_viewport_size({'width': 360, 'height': 804})
    no_horizontal_overflow(page)


def touch_drag(page, source, target, cancel=False):
    session = page.context.new_cdp_session(page)
    session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': source[0], 'y': source[1]}]})
    for index in range(1, 6):
        session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{
            'x': source[0] + (target[0] - source[0]) * index / 5,
            'y': source[1] + (target[1] - source[1]) * index / 5}]})
    session.send('Input.dispatchTouchEvent', {'type': 'touchCancel' if cancel else 'touchEnd', 'touchPoints': []})
    session.detach()


def test_finger_reorders_layers_and_one_undo_restores_order(phone):
    page, client = phone
    page.get_by_role('tab', name='对象', exact=True).tap()
    handle = page.get_by_role('button', name='拖动排序 第一行标题', exact=True)
    handle.scroll_into_view_if_needed()
    source = handle.bounding_box()
    target = page.locator('[data-layer-id="title2"]').bounding_box()
    touch_drag(page, (source['x'] + source['width'] / 2, source['y'] + source['height'] / 2),
               (source['x'] + source['width'] / 2, target['y'] + target['height'] / 2))
    expect(page.locator('.object-row').first).to_have_attribute('data-object-id', 'title1')
    page.get_by_role('button', name='撤销', exact=True).tap()
    expect(page.locator('.object-row').first).to_have_attribute('data-object-id', 'title2')
    expect(page.locator('.save-state')).to_have_text('已保存到本机')
    assert client.get('/api/project').json()['project']['layerOrder'] == ['title2', 'title1', 'track', 'bg']


def test_cancelled_finger_sort_does_not_change_layers(phone):
    page, _client = phone
    page.get_by_role('tab', name='对象', exact=True).tap()
    source = page.get_by_role('button', name='拖动排序 第一行标题', exact=True).bounding_box()
    target = page.locator('[data-layer-id="title2"]').bounding_box()
    touch_drag(page, (source['x'] + 12, source['y'] + 20), (source['x'] + 12, target['y'] + 20), cancel=True)
    expect(page.locator('.object-row').first).to_have_attribute('data-object-id', 'title2')
    expect(page.get_by_role('button', name='撤销', exact=True)).to_be_disabled()


def test_touch_buttons_fire_once_per_tap_including_rapid_additions(phone):
    page, client = phone
    page.get_by_role('tab', name='对象', exact=True).tap()
    add = page.get_by_role('button', name='添加标题', exact=False)
    add.tap()
    add.tap()
    expect(page.locator('[data-object-id^="title"]')).to_have_count(4)
    expect(page.locator('.save-state')).to_have_text('已保存到本机')
    assert len([key for key in client.get('/api/project').json()['project']['layerOrder'] if key.startswith('title')]) == 4


@pytest.mark.parametrize('size', [{'width': 360, 'height': 804}, {'width': 804, 'height': 360}])
def test_information_and_sticker_dialogs_fit_phone(phone, size):
    page, _client = phone
    page.set_viewport_size(size)
    page.get_by_role('button', name='信息', exact=True).tap()
    dialog = page.get_by_role('dialog')
    in_viewport(page, dialog)
    no_horizontal_overflow(page)
    dialog.locator('.modal-header button').tap()
    page.get_by_role('tab', name='对象', exact=True).tap()
    page.get_by_role('button', name='选择贴纸', exact=True).tap()
    dialog = page.get_by_role('dialog', name='选择贴纸', exact=True)
    expect(dialog.locator('.sticker-grid button').first).to_be_visible()
    in_viewport(page, dialog)
    no_horizontal_overflow(page)
    dialog.locator('.sticker-grid button').first.tap()
    page.get_by_role('button', name='添加贴纸', exact=True).tap()
    expect(page.get_by_role('dialog')).to_have_count(0)
    expect(page.locator('[data-object-id^="sticker_"]')).to_have_count(1)


@pytest.mark.parametrize('size', [{'width': 360, 'height': 804}, {'width': 804, 'height': 360}])
def test_chart_editor_selection_preview_and_optional_titles_fit_phone(phone, size):
    page, client = phone
    page.set_viewport_size(size)
    page.get_by_role('button', name='从谱面生成', exact=True).tap()
    source = json.dumps({'pathData': 'RRRRUULLDDRRRR', 'settings': {'song': '手机测试曲', 'artist': '测试作者', 'bpm': 100},
                         'actions': [{'floor': 2, 'eventType': 'SetSpeed', 'speedType': 'Bpm', 'beatsPerMinute': 200}]}).encode()
    page.get_by_label('谱面文件', exact=True).set_input_files({'name': '手机测试.adofai', 'mimeType': 'application/json', 'buffer': source})
    frame = page.frame_locator('iframe[title="轨道选段工具"]')
    expect(frame.locator('#preview')).to_be_visible()
    assert frame.locator('html').evaluate('(el)=>el.scrollWidth<=el.ownerDocument.defaultView.innerWidth+1')
    frame.locator('#start').fill('1')
    frame.locator('#end').fill('6')
    frame.locator('#resolution').select_option('1920')
    frame.locator('#aspect').select_option('4:3')
    page.get_by_label('生成音乐名称标题', exact=True).check()
    frame.locator('#export-png').tap()
    expect(page.locator('.chart-result-image img')).to_be_visible(timeout=30000)
    in_viewport(page, page.get_by_role('dialog', name='从谱面生成轨道', exact=True))
    page.get_by_role('button', name='应用到封面', exact=True).tap()
    expect(page.get_by_role('dialog')).to_have_count(0)
    expect(page.locator('.save-state')).to_have_text('已保存到本机')
    saved = client.get('/api/project').json()
    assert saved['project']['generatedTrack']['start'] == 1 and saved['project']['generatedTrack']['end'] == 6
    assert any(title['text'] == '手机测试曲' for title in saved['project']['titles'])
    asset = saved['assets'][saved['project']['trackAsset']]
    assert (asset['width'], asset['height']) == (1920, 1440)
    no_horizontal_overflow(page)


@pytest.mark.parametrize('size', [{'width': 360, 'height': 804}, {'width': 804, 'height': 360}])
def test_phone_fusion_mask_painting_and_local_filter_dialog(phone, size):
    page, client = phone
    page.set_viewport_size(size)
    image = Image.new('RGBA', (400, 240), '#b83a4a')
    ImageDraw.Draw(image).rectangle((110, 40, 129, 190), fill='#2fb6e9')
    buffer = io.BytesIO()
    image.save(buffer, 'PNG')
    page.get_by_label('轨道文件', exact=True).set_input_files({'name': 'track.png', 'mimeType': 'image/png', 'buffer': buffer.getvalue()})
    page.get_by_role('tab', name='属性', exact=True).tap()
    expect(page.get_by_role('button', name='融合图片', exact=True)).to_be_enabled()
    page.get_by_role('button', name='融合图片', exact=True).tap()
    dialog = page.get_by_role('dialog', name='图片融合', exact=True)
    expect(dialog.get_by_role('button', name='应用融合', exact=True)).to_be_enabled()
    in_viewport(page, dialog)
    no_horizontal_overflow(page)
    dialog.get_by_role('button', name='应用融合', exact=True).tap()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button', name='去背景与轨道修正', exact=True).tap()
    page.get_by_label('自动去除背景', exact=True).check()
    expect(page.get_by_role('button', name='修正轨道', exact=True)).to_be_enabled(timeout=30000)
    page.get_by_role('button', name='修正轨道', exact=True).tap()
    dialog = page.get_by_role('dialog', name='轨道修正工作区', exact=True)
    in_viewport(page, dialog)
    expect(dialog.get_by_role('status')).to_have_text('修正已保存')
    page.get_by_role('button', name='擦除画笔', exact=True).tap()
    canvas = page.get_by_label('轨道修正画布', exact=True)
    bounds = canvas.bounding_box()
    x, y = bounds['x'] + bounds['width'] * 120 / 400, bounds['y'] + bounds['height'] * 120 / 240
    touch_drag(page, (x, y), (x + 2, y + 2))
    expect(dialog.get_by_role('status')).to_have_text('修正已保存', timeout=20000)
    expect(page.locator('.save-state')).to_have_text('已保存到本机')
    saved = client.get('/api/project').json()['project']
    mask = Image.open(io.BytesIO(client.get('/api/assets/' + saved['maskAsset']).content))
    assert mask.getpixel((120, 120)) == 0
    page.get_by_role('button', name='返回构图', exact=True).tap()
    page.get_by_role('tab', name='滤镜', exact=True).tap()
    page.get_by_label('选择滤镜', exact=True).select_option('GrayscaleFilter')
    page.get_by_role('button', name='添加滤镜', exact=True).tap()
    page.get_by_label('滤镜局部区域', exact=True).select_option('rect')
    page.get_by_role('button', name='编辑滤镜范围', exact=True).tap()
    dialog = page.get_by_role('dialog', name='滤镜局部范围', exact=True)
    in_viewport(page, dialog)
    no_horizontal_overflow(page)
    expect(page.get_by_role('button', name='应用滤镜范围', exact=True)).to_be_enabled()
    page.get_by_role('button', name='应用滤镜范围', exact=True).tap()
    expect(page.get_by_role('dialog')).to_have_count(0)
