from tests.e2e.test_native_text_presets import assert_native_text_presets
from tests.e2e.test_text_presets import test_portable_custom_font_texture_and_mask_render_without_source_store as portable_case
from .conftest import BUNDLE


def test_frozen_native_text_presets_render_undo_and_restart_exactly(tmp_path):
    assert_native_text_presets(tmp_path,binary=BUNDLE/'ADOFAI-Cover-Studio.exe')


def test_frozen_portable_text_preset_imports_custom_font_masks_and_textures(edge_page,running_app,tmp_path):
    portable_case(edge_page,running_app,tmp_path)
