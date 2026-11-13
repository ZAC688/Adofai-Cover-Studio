import json
from .conftest import ROOT,BUNDLE
from tests.e2e.test_080_manual import test_current_information_documents_metadata_icons_and_portable_text_styles as manual_case
from tests.e2e.test_chart_metadata import test_white_metadata_titles_are_opt_in_independent_undoable_and_persistent as metadata_case
from tests.e2e.test_reference_style import test_reference_relief_reaches_live_preview_svg_and_applied_track as style_case


def test_frozen_080_manual_version_and_capabilities_match_source(edge_page,running_app):
    assert (BUNDLE/'使用说明.md').read_bytes()==(ROOT/'docs/使用说明.md').read_bytes()
    manifest=json.loads((BUNDLE/'release-manifest.json').read_text(encoding='utf-8'))
    assert manifest['version']=='0.8.1'
    assert manifest['optional_song_artist_titles'] and manifest['song_artist_default_checked'] is False
    assert manifest['application_icon']=='header-logo'
    assert manifest['application_icon_sizes']==[16,24,32,48,64,128,256]
    assert manifest['portable_text_presets'] and manifest['portable_filter_presets']
    assert manifest['text_preset_preserves']==['content','position','object-rotation']
    assert manifest['text_preset_resources']==['uploaded-font','filter-texture','filter-mask']
    manual_case(edge_page,running_app)


def test_frozen_song_and_artist_titles_preserve_existing_work(edge_page,running_app):
    metadata_case(edge_page,running_app)


def test_frozen_track_preview_svg_and_png_have_reference_details(edge_page,running_app,tmp_path):
    style_case(edge_page,running_app,tmp_path)
