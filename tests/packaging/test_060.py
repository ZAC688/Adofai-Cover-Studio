import io,json
from pathlib import Path
import httpx
import pytest
from PIL import Image
from .conftest import BUNDLE,start_binary,wait_ready
from tests.backend.test_filters import spec
from tests.e2e.test_filter_presets import test_preset_save_export_import_apply_history_and_exact_masked_render as presets
from tests.e2e.test_filter_presets import test_preset_failed_save_retains_name_and_applies_only_to_selected_object as failure
from tests.e2e.test_filter_default_fold import test_reenter_and_switch_object_default_fold_without_changing_effects as folding
from tests.e2e.test_delete_key import test_delete_removes_selected_object_undo_restores_and_reload_persists as delete
from tests.e2e.test_delete_key import test_delete_edits_text_and_protects_numeric_fields_editable_content_dialogs_and_background as editing
from tests.e2e.test_toolbar_uploads import test_top_upload_buttons_use_file_picker_and_object_list_has_more_space as toolbar
from tests.e2e.test_info_dialog import test_information_author_version_changelog_and_manual_are_offline_and_preserve_work as info
from tests.e2e.test_level_sticker_order import test_real_new_level_stickers_p1_to_p20_first_crazy_last_and_selectable as stickers


def test_frozen_portable_presets_and_masked_export(edge_page,running_app,tmp_path):presets(edge_page,running_app,tmp_path)
def test_frozen_preset_failure_and_target_independence(edge_page,running_app,tmp_path):failure(edge_page,running_app,tmp_path)
def test_frozen_default_folding(edge_page,running_app,tmp_path):folding(edge_page,running_app,tmp_path)
@pytest.mark.parametrize('kind',['title1','track','sticker'])
def test_frozen_delete_objects(edge_page,running_app,kind):delete(edge_page,running_app,kind)
def test_frozen_delete_protects_editing(edge_page,running_app):editing(edge_page,running_app)
def test_frozen_toolbar_upload_and_layout(edge_page,running_app,tmp_path):toolbar(edge_page,running_app,tmp_path)
def test_frozen_offline_information_dialog(edge_page,running_app):info(edge_page,running_app)
def test_frozen_new_level_sticker_order(edge_page,running_app):stickers(edge_page,running_app)


def test_frozen_preset_library_and_embedded_images_survive_process_restart(running_app,tmp_path):
    client=running_app['client'];raw=io.BytesIO();Image.new('RGB',(32,32),(90,170,210)).save(raw,'PNG')
    texture=client.post('/api/assets',files={'file':('map.png',raw.getvalue(),'image/png')}).json()['id']
    filter=spec('SimpleLightmapFilter');filter['params']['lightMap']=texture
    value=client.post('/api/filter-presets',json={'name':'重启恢复','filters':[filter]});assert value.status_code==200,value.text
    key=value.json()['id'];exported=client.get('/api/filter-presets/'+key).json();project=client.get('/api/project').json()
    client.post('/api/shutdown');running_app['process'].communicate(timeout=20)
    ready=tmp_path/'restart-ready.json';process=start_binary(BUNDLE,running_app['data'],ready)
    address=None
    try:
        address=wait_ready(process,ready,running_app['data'])
        with httpx.Client(base_url=address,trust_env=False) as reopened:
            reopened.headers['x-editor-token']=reopened.get('/api/session').json()['token']
            assert reopened.get('/api/filter-presets').json()==[value.json()]
            assert reopened.get('/api/filter-presets/'+key).json()==exported
            assert reopened.get('/api/project').json()==project
            prepared=reopened.post('/api/filter-presets/'+key+'/prepare');assert prepared.status_code==200,prepared.text
            new_id=prepared.json()['filters'][0]['params']['lightMap']
            assert reopened.get('/api/assets/'+new_id).content==reopened.get('/api/assets/'+texture).content
    finally:
        if process.poll() is None:
            if address:
                with httpx.Client(base_url=address,trust_env=False) as cleanup:
                    cleanup.headers['x-editor-token']=cleanup.get('/api/session').json()['token'];cleanup.post('/api/shutdown')
                process.communicate(timeout=20)
            else:process.terminate();process.communicate(timeout=10)


def test_frozen_060_metadata_matches_information_version():
    manifest=json.loads((BUNDLE/'release-manifest.json').read_text(encoding='utf-8'))
    assert manifest['version']=='0.8.0' and manifest['author']=='ZAC688'
    for field in ['portable_filter_presets','existing_filters_folded_by_default','delete_object_key','toolbar_uploads','offline_information_dialog']:assert manifest[field] is True
    assert manifest['new_level_sticker_order']=='P-first-natural,crazy-last'
