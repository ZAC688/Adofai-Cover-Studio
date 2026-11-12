from tests.e2e.test_objects import (
    test_five_of_each_limit_delete_readd_undo_and_layout_persistence as five_each,
    test_drag_mixed_layers_changes_pixels_hit_priority_undo_and_export as mixed_layers,
)
from tests.e2e.test_rotation import test_rotation_handle_is_interactive_and_undoable as rotation_gesture


def test_frozen_package_supports_full_object_capacity_and_restores_layouts(edge_page,running_app,tmp_path):
    five_each(edge_page,running_app,tmp_path)


def test_frozen_package_renders_reordered_objects_and_exports_identical_pixels(edge_page,running_app,tmp_path):
    mixed_layers(edge_page,running_app,tmp_path)


def test_frozen_package_rotates_with_one_gesture_undo(edge_page):
    rotation_gesture(edge_page)
