import math
import xml.etree.ElementTree as ET

from PIL import Image
import pytest

from experiments.static_track_probe import build_track
from experiments.static_track_export import fit_bounds, render_selection, select_tiles, selection_scene


def test_both_brick_endpoints_are_included_and_geometry_is_not_rebased():
    track = build_track({'pathData': 'RRUUL'})
    selected = select_tiles(track, 2, 4)
    assert [t.floor for t in selected] == [2, 3, 4]
    for tile, expected in zip(selected, [(2, 0), (2, 1), (2, 2)]):
        assert (tile.x, tile.y) == pytest.approx(expected)
    assert selected[0] is track.tiles[2]
    assert select_tiles(track, 5, 5) == [track.tiles[5]]


@pytest.mark.parametrize('start,end', [(-1, 2), (3, 2), (0, 100), (True, 2), (1.5, 2)])
def test_bad_ranges_fail_instead_of_silently_cropping(start, end):
    with pytest.raises(ValueError):
        select_tiles(build_track({'pathData': 'RRR'}), start, end)


def test_uniform_fit_is_centered_and_preserves_aspect_ratio():
    view = fit_bounds([10, -5, 14, -3], 1000, 600, 100)
    assert view['scale'] == 200
    assert view['clip'] == [100, 100, 900, 500]
    assert 10*view['scale']+view['offset_x'] == 100
    assert view['offset_y']-(-3)*view['scale'] == 100


@pytest.mark.parametrize('world', [[0, 0, 0, 1], [2, 0, 1, 1], [0, 0, 1, float('nan')]])
def test_invalid_crop_is_rejected(world):
    with pytest.raises(ValueError):
        fit_bounds(world, 1000, 600, 50)


@pytest.mark.parametrize('w,h,p', [(60, 100, 5), (1000, 600, -1), (1000, 600, 300), (8192, 8192, 10)])
def test_invalid_dimensions_and_memory_excess_are_rejected(w, h, p):
    with pytest.raises(ValueError):
        fit_bounds([0, 0, 1, 1], w, h, p)


def test_selection_exports_only_requested_bricks_and_no_outside_track(tmp_path):
    track = build_track({'pathData': 'RULDRR'})
    result = render_selection(track, tmp_path/'segment.png', start_floor=1, end_floor=2,
                              width=960, height=540, padding=30)
    svg = ET.parse(tmp_path/'segment.svg').getroot()
    assert {int(p.attrib['data-floor']) for p in svg.findall('.//{*}polygon')} == {1, 2}
    assert result['tile_count'] == 2
    with Image.open(tmp_path/'segment.png') as image:
        assert image.size == (960, 540)
        b = image.getchannel('A').getbbox()
        assert b[0] >= 27 and b[1] >= 27 and b[2] <= 933 and b[3] <= 513


def test_crop_clips_overflow_in_letterbox_instead_of_redrawing_hidden_bricks(tmp_path):
    track = build_track({'pathData': 'RRRRRR'})
    result = render_selection(track, tmp_path/'crop.png', width=800, height=600, padding=50,
                              crop=[1.8, -.3, 2.2, .3])
    x1, y1, x2, y2 = result['view']['clip']
    with Image.open(tmp_path/'crop.png') as image:
        b = image.getchannel('A').getbbox()
        assert b[0] >= math.floor(x1)-3 and b[2] <= math.ceil(x2)+3
        assert b[1] >= math.floor(y1)-3 and b[3] <= math.ceil(y2)+3
        assert image.getpixel((400, 300))[3] == 255


def test_single_endpoint_brick_can_be_fit_and_exported(tmp_path):
    track = build_track({'pathData': 'RU'})
    result = render_selection(track, tmp_path/'one.png', start_floor=2, end_floor=2,
                              width=500, height=500, padding=30)
    assert result['tile_count'] == 1
    assert Image.open(tmp_path/'one.png').getchannel('A').getbbox()


def test_scene_contains_original_boundary_ports_and_not_other_floor_meshes():
    track = build_track({'pathData': 'RULDR'})
    scene = selection_scene(track, 2, 2)
    assert len(scene['tiles']) == 1
    assert scene['tiles'][0]['floor'] == 2
    assert scene['bounds'][0] > 0
