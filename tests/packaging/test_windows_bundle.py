import json
import shutil
import subprocess
import io

import httpx
from PIL import Image
from playwright.sync_api import expect

from .conftest import BUNDLE, ROOT, clean_environment, start_binary, wait_ready
from tests.e2e.test_editor import saved, select
from tests.e2e.test_mask import recognize, paint, mask_pixel
from tests.e2e.test_export import export


def test_frozen_application_infers_paints_saves_and_exports_in_real_edge(edge_page, running_app, tmp_path):
    page = edge_page
    background = tmp_path / 'background.png'
    Image.new('RGB', (1920, 1080), (10, 21, 32)).save(background)
    page.get_by_label('底图文件', exact=True).set_input_files(str(background))
    expect(page.locator('.asset-meta')).to_contain_text('1920 × 1080')
    recognize(page)
    page.get_by_role('button', name='修正轨道', exact=True).click()
    expect(page.get_by_role('dialog', name='轨道修正工作区').get_by_role('status')).to_have_text('修正已保存')
    paint(page, 1000, 320)
    saved(page)
    assert mask_pixel(running_app['client'], 1000, 320)[0] == 0
    page.get_by_role('button', name='返回构图', exact=True).click()
    select(page, '第一行标题')
    page.get_by_label('标题内容', exact=True).fill('冰与火之舞')
    page.get_by_label('字号', exact=True).fill('120')
    select(page, '第二行标题')
    page.get_by_label('标题内容', exact=True).fill('ADOFAI · COVER STUDIO')
    page.get_by_label('字号', exact=True).fill('40')
    page.locator('.panel-heading').first.click()
    saved(page)
    filename = export(page, tmp_path / 'production.png', '实际打包验证')
    assert filename == '实际打包验证.png'
    assert Image.open(tmp_path / 'production.png').size == (1920, 1080)
    page.get_by_role('button', name='4:3', exact=True).click()
    saved(page)
    export(page, tmp_path / 'production-4x3.png')
    assert Image.open(tmp_path / 'production-4x3.png').size == (1440, 1080)
    page.reload()
    expect(page.get_by_label('标题内容', exact=True)).to_have_value('冰与火之舞')
    saved(page)
    page.screenshot(path=str(ROOT / 'artifacts/p6/packaged-editor.png'))


def test_moved_bundle_restores_same_local_data_without_development_paths(running_app, tmp_path):
    client = running_app['client']
    state = client.get('/api/project').json()
    uploaded = client.post('/api/assets', files={'file': ('track.png', (ROOT/'test-assets/reference/sample-09.png').read_bytes(), 'image/png')}).json()
    mask_bytes = io.BytesIO()
    Image.new('L', (1406,1123), 128).save(mask_bytes,'PNG')
    mask = client.post('/api/masks/'+uploaded['id'],files={'file':('mask.png',mask_bytes.getvalue(),'image/png')}).json()
    state['project']['titles'][0]['text'] = '更换程序目录仍能恢复'
    state['project'].update(trackAsset=uploaded['id'],maskAsset=mask['id'],baseMaskAsset=mask['id'],removeBackground=True)
    assert client.put('/api/project', json={'baseRevision': state['revision'], 'project': state['project']}).status_code == 200
    original_resource = client.get('/api/assets/'+uploaded['id']).content
    client.post('/api/shutdown')
    running_app['process'].communicate(timeout=15)
    copied = tmp_path / '移动后的程序 中文'
    assert copied.resolve().is_relative_to(tmp_path.resolve())
    shutil.copytree(BUNDLE, copied)
    ready = tmp_path / 'moved-ready.json'
    process = start_binary(copied, running_app['data'], ready)
    try:
        address = wait_ready(process, ready, running_app['data'])
        with httpx.Client(base_url=address, trust_env=False) as restored:
            assert restored.get('/api/project').json()['project']['titles'][0]['text'] == '更换程序目录仍能恢复'
            assert restored.get('/api/project').json()['project']['maskAsset'] == mask['id']
            assert restored.get('/api/assets/'+uploaded['id']).content == original_resource
            assert Image.open(io.BytesIO(restored.get('/api/assets/'+mask['id']).content)).getpixel((10,10)) == 128
            token = restored.get('/api/session').json()['token']
            restored.post('/api/shutdown', headers={'x-editor-token': token})
            process.communicate(timeout=15)
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)


def test_incomplete_bundle_reports_missing_resource_without_downloading(tmp_path):
    copied = tmp_path / '不完整的程序'
    assert copied.resolve().is_relative_to(tmp_path.resolve())
    shutil.copytree(BUNDLE, copied)
    (copied / '_internal/models/u2netp.onnx').unlink()
    data = tmp_path / 'error-data'
    result = subprocess.run(
        [str(copied / 'ADOFAI-Cover-Studio.exe'), '--no-browser', '--data-dir', str(data)],
        cwd=tmp_path, env=clean_environment(), capture_output=True, timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode != 0
    assert '本地识别资源缺失或校验失败' in (data / 'startup-error.log').read_text(encoding='utf-8')
    assert not (copied / '_internal/models/u2netp.onnx').exists()


def test_release_contains_licenses_and_no_user_screenshots():
    names = [str(file.relative_to(BUNDLE)).lower() for file in BUNDLE.rglob('*') if file.is_file()]
    assert any('third_party_notices' in name for name in names)
    assert not any('testscreenshots' in name or 'test-assets' in name or 'user-reference' in name for name in names)
    manifest = json.loads((BUNDLE / 'release-manifest.json').read_text(encoding='utf-8'))
    assert manifest['recognition_quality_status'] == 'SOLID_TEST_2_EACH_IOU_GE_90_PASSED'
    assert manifest['version']=='0.8.0'
    assert manifest['recognition_acceptance_samples']==9
    assert manifest['pixi_filters']==38 and manifest['offline_font_faces']==10
    assert manifest['default_glow']==0 and manifest['fusion_editor']=='smooth-gradient-mask'
    assert not any('clash' in name or 'tanker' in name for name in names)
    assert manifest['max_titles']==5 and manifest['max_tracks']==5
    assert manifest['sticker_preset_count']==253 and manifest['max_stickers'] is None
    assert len(list((BUNDLE/'_internal/Logos').rglob('*.gif')))==8
