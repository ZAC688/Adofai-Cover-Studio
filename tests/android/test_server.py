"""Exercise real loopback HTTP, files and algorithms without Qt or a cloud service."""
from copy import deepcopy
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import threading
import time

import httpx
import numpy as np
from PIL import Image
import pytest

from backend.android_server import Handler, Runtime
from backend.app.storage import Store
from backend.app.filter_schema import CATALOG

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def runtime_client(tmp_path):
    runtime = Runtime(ROOT, tmp_path / 'work')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    server.runtime = runtime
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with httpx.Client(base_url=f'http://127.0.0.1:{server.server_port}', timeout=60, trust_env=False) as client:
        client.headers['x-editor-token'] = client.get('/api/session').json()['token']
        yield client, runtime
    runtime.jobs.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def png(size=(80, 60), color='#cf9f50', mode='RGBA'):
    out = io.BytesIO()
    Image.new(mode, size, color).save(out, 'PNG')
    return out.getvalue()


def checked(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_requires_loopback_host_current_session_and_same_origin(runtime_client):
    client, _runtime = runtime_client
    before = checked(client.get('/api/project'))
    request = {'baseRevision': 0, 'project': before['project']}
    assert client.put('/api/project', json=request, headers={'x-editor-token': 'invalid'}).status_code == 403
    assert client.put('/api/project', json=request, headers={'Origin': 'https://foreign.example'}).status_code == 403
    assert client.get('/api/project', headers={'Host': 'foreign.example'}).status_code == 403
    assert client.post('/api/assets', files={'file': ('unauthorized.png', b'x' * 100_000)},
                       headers={'x-editor-token': 'invalid'}).status_code == 403
    assert checked(client.get('/api/project')) == before


def test_images_save_conflicts_and_restart_restore_real_files(runtime_client):
    client, runtime = runtime_client
    asset = checked(client.post('/api/assets', files={'file': ('底图.png', png(), 'image/png')}))
    project = checked(client.get('/api/project'))
    project['project'].update(name='手机作品', bgAsset=asset['id'])
    saved = checked(client.put('/api/project', json={'baseRevision': 0, 'project': project['project']}))
    assert saved['revision'] == 1
    assert Store(runtime.store.directory).load() == saved
    assert client.put('/api/project', json={'baseRevision': 0, 'project': project['project']}).status_code == 409
    assert checked(client.get('/api/project')) == saved
    image = Image.open(io.BytesIO(client.get('/api/assets/' + asset['id']).content))
    assert image.size == (80, 60) and image.getpixel((0, 0)) == (207, 159, 80, 255)


def test_streamed_phone_provider_upload_without_content_length(runtime_client):
    client, _runtime = runtime_client
    boundary='phone-streamed-file'
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="phone.png"\r\nContent-Type: image/png\r\n\r\n'.encode()
          +png()+f'\r\n--{boundary}--\r\n'.encode())
    response=client.post('/api/assets',content=(body[offset:offset+97] for offset in range(0,len(body),97)),
                         headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    asset=checked(response)
    assert (asset['width'],asset['height'])==(80,60)
    assert Image.open(io.BytesIO(client.get('/api/assets/'+asset['id']).content)).getpixel((0,0))==(207,159,80,255)


def test_invalid_file_project_and_path_cannot_damage_saved_work(runtime_client):
    client, runtime = runtime_client
    before = checked(client.get('/api/project'))
    assert client.post('/api/assets', files={'file': ('fake.png', b'not a PNG')}).status_code == 400
    assert client.post('/api/assets', files={'file': ('large.png', b'x' * 10_000_001)}).status_code == 413
    document = deepcopy(before['project'])
    document['titles'][0]['glow'] = 101
    assert client.put('/api/project', json={'baseRevision': 0, 'project': document}).status_code == 400
    assert client.get('/%2e%2e/%2e%2e/LICENSE').status_code == 400
    assert checked(client.get('/api/project')) == before
    assert not list((runtime.store.directory / 'assets').iterdir())


def test_masks_validate_dimensions_and_preserve_gray_pixels(runtime_client):
    client, _runtime = runtime_client
    asset = checked(client.post('/api/assets', files={'file': ('source.png', png())}))
    assert client.post('/api/masks/' + asset['id'], files={'file': ('mask.png', png((79, 60)))}).status_code == 400
    mask = checked(client.post('/api/masks/' + asset['id'], files={'file': ('mask.png', png(color=143, mode='L'))}))
    image = Image.open(io.BytesIO(client.get('/api/assets/' + mask['id']).content))
    assert image.mode == 'L' and image.getextrema() == (143, 143)
    assert client.post('/api/filter-masks/16-9', files={'file': ('mask.png', png())}).status_code == 400


def test_all_38_filters_and_text_presets_roundtrip_without_network(runtime_client):
    client, _runtime = runtime_client
    filters = [{'id': f'{index:032x}', 'type': kind, 'enabled': True, 'targets': ['track'],
                'params': {field['key']: deepcopy(field['value']) for field in entry['fields']}, 'regions': {}}
               for index, (kind, entry) in enumerate(CATALOG.items())]
    assert len(filters) == 38
    saved = checked(client.post('/api/filter-presets', json={'name': '全部滤镜', 'filters': filters}))
    exported = checked(client.get('/api/filter-presets/' + saved['id']))
    imported = checked(client.post('/api/filter-presets/import', files={'file': ('filters.json', json.dumps(exported).encode())}))
    prepared = checked(client.post('/api/filter-presets/' + imported['id'] + '/prepare'))
    assert [item['type'] for item in prepared['filters']] == list(CATALOG)
    assert prepared['filters'][0]['id'] != filters[0]['id']
    style = {'color': '#ffcc44', 'glow': 0, 'fontId': 'system', 'text3d': {'enabled': True, 'depth': 55}}
    text = checked(client.post('/api/text-presets', json={'name': '三维文字', 'style': style, 'fontSize': 137, 'filters': []}))
    exported_text = checked(client.get('/api/text-presets/' + text['id']))
    imported_text = checked(client.post('/api/text-presets/import', files={'file': ('text.json', json.dumps(exported_text).encode())}))
    restored = checked(client.post('/api/text-presets/' + imported_text['id'] + '/prepare'))
    assert restored['style']['color'] == '#ffcc44'
    assert restored['style']['text3d']['depth'] == 55 and restored['fontSize'] == 137


def test_uploaded_font_stickers_and_chinese_3d_outline_are_real(runtime_client):
    client, _runtime = runtime_client
    font = (ROOT / 'frontend/public/fonts/inter.ttf').read_bytes()
    uploaded = checked(client.post('/api/fonts', files={'file': ('上传字体.ttf', font)}))
    assert client.get('/api/fonts/' + uploaded['id']).content == font
    assert checked(client.get('/api/fonts'))[0]['id'] == uploaded['id']
    outline = checked(client.post('/api/text-outline', json={'text': '中文 ADOFAI', 'color': '#ffffff', 'glow': 0, 'fontId': uploaded['id']}))
    assert outline['width'] > 0 and outline['paths'] and not outline['missingCharacters']
    assert set(outline['fallbackCharacters']) == {'中', '文'}
    stickers = checked(client.get('/api/stickers'))
    assert len(stickers) == 253 and all(item['category'] for item in stickers)
    item = next(item for item in stickers if item['frames'] > 1)
    imported = checked(client.post('/api/stickers/' + item['id'] + '/import', json={'frame': 1}))
    expected = client.get(f"/api/stickers/{item['id']}/frames/1").content
    actual = client.get('/api/assets/' + imported['asset']['id']).content
    assert Image.open(io.BytesIO(expected)).tobytes() == Image.open(io.BytesIO(actual)).tobytes()


def test_chart_metadata_editor_and_real_gold_high_resolution_render(runtime_client):
    client, _runtime = runtime_client
    data = json.dumps({'pathData': 'RRRRUULLDDRRRR', 'settings': {'song': '测试曲', 'artist': '作者', 'bpm': 100},
                       'actions': [{'floor': 2, 'eventType': 'SetSpeed', 'speedType': 'Bpm', 'beatsPerMinute': 200},
                                   {'floor': 5, 'eventType': 'Twirl'}]}).encode()
    chart = checked(client.post('/api/charts', files={'file': ('test.adofai', data)}))
    assert chart['song'] == '测试曲' and chart['artist'] == '作者'
    editor = checked(client.post('/api/charts/' + chart['id'] + '/editor', json=None))['html']
    assert '/*__TRACK_DATA__*/' not in editor and '"embedded":true' in editor
    recipe = {'sourceId': chart['id'], 'start': 0, 'end': 6, 'resolution': 4096, 'aspect': '16:9'}
    rendered = checked(client.post('/api/charts/render', json=recipe))
    image = Image.open(io.BytesIO(client.get('/api/assets/' + rendered['asset']['id']).content)).convert('RGBA')
    assert image.size == (4096, 2304) and image.getchannel('A').getextrema() == (0, 255)
    rgb = np.asarray(image)
    opaque = rgb[rgb[:, :, 3] == 255, :3]
    gold = opaque[(opaque[:, 0] > 170) & (opaque[:, 1] > 140) & (opaque[:, 2] < 160)]
    assert len(gold) > 1000 and gold[:, 0].std() > 3
    assert np.any(np.all(opaque == [223, 73, 60], axis=1))
    assert checked(client.get('/api/project'))['revision'] == 0


def test_thread_recognition_returns_real_mask_without_changing_project(runtime_client):
    client, _runtime = runtime_client
    image = Image.new('RGBA', (400, 240), '#b83a4a')
    from PIL import ImageDraw
    ImageDraw.Draw(image).rectangle((110, 40, 129, 190), fill='#2fb6e9')
    encoded = io.BytesIO()
    image.save(encoded, 'PNG')
    asset = checked(client.post('/api/assets', files={'file': ('track.png', encoded.getvalue())}))
    job = checked(client.post('/api/jobs', json={'source': asset['id']}))
    deadline = time.monotonic() + 30
    while job['status'] == 'running' and time.monotonic() < deadline:
        time.sleep(.02)
        job = checked(client.get('/api/jobs/' + job['id']))
    assert job['status'] == 'succeeded', job
    mask = Image.open(io.BytesIO(client.get('/api/assets/' + job['result']['id']).content))
    assert mask.mode == 'L' and mask.size == image.size
    assert mask.getpixel((120, 120)) == 255 and mask.getpixel((0, 0)) == 0
    assert checked(client.get('/api/jobs/active/' + asset['id']))['job']['id'] == job['id']
    assert checked(client.get('/api/project'))['revision'] == 0


def test_offline_page_and_head_requests_serve_local_bytes(runtime_client):
    client, _runtime = runtime_client
    response = client.get('/')
    assert response.status_code == 200 and '<div id="root">' in response.text
    head = client.head('/app-icon.png')
    assert head.status_code == 200 and not head.content
    assert int(head.headers['content-length']) == len(client.get('/app-icon.png').content)
    assert checked(client.get('/api/health'))['platform'] == 'android'
