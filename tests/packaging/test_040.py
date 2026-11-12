import io
import json
import time
from PIL import Image
from .conftest import ROOT,BUNDLE
from experiments.p0 import quality_metrics
from tests.e2e.test_filters import test_every_upstream_filter_runs_real_webgl_and_has_visible_effect as all_filters
from tests.e2e.test_fonts import test_six_user_supplied_faces_render_real_distinct_glyphs_and_restore_styles as supplied_fonts
from tests.e2e.test_stickers import test_all_and_every_category_display_complete_naturally_sorted_names as sticker_order
from tests.e2e.test_palette import test_continuous_palette_coalesces_work_and_preserves_final_color_history_and_png as palette
from tests.e2e.test_zero_glow import test_old_saved_glow_values_survive_reload_and_adding_new_objects as old_glow

def test_frozen_all_38_native_filters(edge_page,running_app,tmp_path):all_filters(edge_page,running_app,tmp_path)
def test_frozen_new_fonts_preserve_all_styles(edge_page,running_app,tmp_path):supplied_fonts(edge_page,running_app,tmp_path)
def test_frozen_all_sticker_categories_are_sorted(edge_page,running_app):sticker_order(edge_page,running_app)
def test_frozen_palette_is_coalesced_and_pixel_exact(edge_page,running_app,tmp_path):palette(edge_page,running_app,tmp_path)
def test_frozen_old_glow_is_unchanged(edge_page,running_app):old_glow(edge_page,running_app)

def test_frozen_nine_real_solid_images_each_pass_iou_gate(running_app):
    client=running_app['client'];manifest=json.loads((ROOT/'test-assets/solid/manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['samples'])==9
    for sample in manifest['samples']:
        source=ROOT/sample['file'];asset=client.post('/api/assets',files={'file':('source.png',source.read_bytes(),'image/png')}).json()
        job=client.post('/api/jobs',json={'source':asset['id']}).json();deadline=time.monotonic()+45
        while job['status']=='running' and time.monotonic()<deadline:
            time.sleep(.05);job=client.get('/api/jobs/'+job['id']).json()
        assert job['status']=='succeeded',job
        with Image.open(io.BytesIO(client.get('/api/assets/'+job['result']['id']).content)) as mask, Image.open(ROOT/'test-assets/solid'/sample['ground_truth']) as truth:
            assert mask.size==truth.size
            assert quality_metrics(mask,truth)['intersection_over_union']>=.9,sample['id']

def test_frozen_fonts_catalog_and_original_licenses_match_source():
    directory=BUNDLE/'_internal/frontend/dist/fonts'
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['fonts'])==10
    for font in manifest['fonts']:assert (directory/font['file']).read_bytes()==(ROOT/'frontend/public/fonts'/font['file']).read_bytes()
    for name in ['Bebas_Neue','Russo_One','Space_Mono']:assert (directory/f'{name}-OFL.txt').is_file()
