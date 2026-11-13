import json
from .conftest import BUNDLE
from tests.e2e.test_property_switching import test_repeated_object_switches_never_duplicate_glow_controls as switching
from tests.e2e.test_filter_management import test_selected_object_and_canvas_manage_separate_filter_lists as management
from tests.e2e.test_filter_sliders import test_practical_and_fine_ranges_keep_full_numeric_values_and_history as sliders
from tests.e2e.test_preview_latency import test_heavy_slider_stays_responsive_and_shows_intermediate_previews as preview
from tests.e2e.test_text3d import (
    test_3d_switch_preserves_2d_and_all_configuration_changes_real_pixels as configuration,
    test_3d_supports_all_fonts_uploads_and_preserves_glyph_holes as fonts,
    test_3d_effects_filters_undo_and_both_ratios_export_exactly as effects,
    test_3d_outline_failure_retains_title_and_can_retry as retry,
    test_3d_titles_keep_five_slots_independent_and_can_be_dragged as slots,
)
from tests.e2e.test_drag_outline import test_outline_appears_only_during_transform_and_hides_for_effect_controls as outline


def test_frozen_switching_has_no_duplicate_controls(edge_page,running_app):switching(edge_page,running_app)
def test_frozen_filters_are_per_object(edge_page,running_app,tmp_path):management(edge_page,running_app,tmp_path)
def test_frozen_filter_sliders_are_precise(edge_page,running_app,tmp_path):sliders(edge_page,running_app,tmp_path)
def test_frozen_preview_remains_responsive(edge_page,running_app,tmp_path):preview(edge_page,running_app,tmp_path)
def test_frozen_3d_config_and_2d_switch(edge_page,running_app,tmp_path):configuration(edge_page,running_app,tmp_path)
def test_frozen_3d_all_fonts_and_holes(edge_page,running_app,tmp_path):fonts(edge_page,running_app,tmp_path)
def test_frozen_3d_effects_filters_and_exports(edge_page,running_app,tmp_path):effects(edge_page,running_app,tmp_path)
def test_frozen_3d_recovers_from_outline_read_failure(edge_page,running_app):retry(edge_page,running_app)
def test_frozen_3d_five_titles_and_drag(edge_page,running_app):slots(edge_page,running_app)
def test_frozen_outline_hidden_while_editing(edge_page,running_app,tmp_path):outline(edge_page,running_app,tmp_path,'track')


def test_frozen_050_contains_worker_three_and_original_license():
    manifest=json.loads((BUNDLE/'release-manifest.json').read_text(encoding='utf-8'))
    assert manifest['version']=='0.8.1' and manifest['three_version']=='0.187.0'
    for key in ['text3d','per_object_filter_management','collapsible_filters_and_reset','precise_filter_sliders','offscreen_light_effects_worker','outline_during_transform_only']:assert manifest[key] is True
    assets=BUNDLE/'_internal/frontend/dist/assets'
    assert list(assets.glob('effects.worker-*.js')) and list(assets.glob('threeText-*.js'))
    licenses=BUNDLE/'_internal/licenses/three'
    assert any(path.is_file() and 'MIT' in path.read_text(encoding='utf-8') for path in licenses.iterdir())
