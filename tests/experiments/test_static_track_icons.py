from dataclasses import replace
import math
import xml.etree.ElementTree as ET

from PIL import Image
import pytest

from experiments.static_track_probe import Tile, build_track
from experiments.static_track_icons import color_rgba, icon_primitives, local_icon
from experiments.static_track_export import render_selection, selection_scene


@pytest.mark.parametrize('value,wanted', [('00ff00', '#00ff00ff'), ('#FF880080', '#ff880080'),
                                         ('ffffffff', '#ffffffff'), (None, '#eaf2fcff')])
def test_default_chart_color_including_alpha_is_preserved(value, wanted):
    track = build_track({'pathData': 'RR', 'settings': {'trackColor': value}})
    assert track.color == wanted
    assert {t['fill'] for t in selection_scene(track)['tiles']} == {wanted}


@pytest.mark.parametrize('value', ['pink', 'fff', '12345g', '123456789'])
def test_invalid_color_fails(value):
    with pytest.raises(ValueError):
        color_rgba(value)


def test_speed_icons_use_cumulative_bpm_and_equal_speed_has_no_icon():
    chart = {'pathData': 'RRRRR', 'settings': {'bpm': 100}, 'actions': [
        {'floor': 1, 'eventType': 'SetSpeed', 'speedType': 'Multiplier', 'bpmMultiplier': 2},
        {'floor': 2, 'eventType': 'SetSpeed', 'speedType': 'Bpm', 'beatsPerMinute': 150},
        {'floor': 3, 'eventType': 'SetSpeed', 'speedType': 'Bpm', 'beatsPerMinute': 150},
        {'floor': 4, 'eventType': 'SetSpeed', 'speedType': 'Multiplier', 'bpmMultiplier': .5}]}
    track = build_track(chart)
    assert [t.bpm for t in track.tiles] == [100, 200, 150, 150, 75, 75]
    assert [t.speed_icon for t in track.tiles] == [None, 'rabbit', 'turtle', None, 'turtle', None]
    # Selecting the later section must not reset to the chart's initial BPM.
    scene = selection_scene(track, 2, 3)
    assert {p['icon_type'] for p in scene['tiles'][0]['icons']} == {'turtle'}
    assert scene['tiles'][1]['icons'] == []


def test_same_floor_events_are_compared_after_resolving_all_changes():
    track = build_track({'pathData': 'RR', 'settings': {'bpm': 100}, 'actions': [
        {'floor': 1, 'eventType': 'SetSpeed', 'speedType': 'Multiplier', 'bpmMultiplier': 2},
        {'floor': 1, 'eventType': 'SetSpeed', 'speedType': 'Multiplier', 'bpmMultiplier': .5}]})
    assert track.tiles[1].bpm == 100
    assert track.tiles[1].speed_icon is None


@pytest.mark.parametrize('event', [
    {'speedType': 'Bpm', 'beatsPerMinute': 0}, {'speedType': 'Multiplier', 'bpmMultiplier': -1},
    {'speedType': 'Bpm', 'beatsPerMinute': float('inf')}, {'speedType': 'Unknown'}])
def test_invalid_speed_is_not_rendered_as_a_valid_icon(event):
    with pytest.raises(ValueError):
        build_track({'pathData': 'RR', 'actions': [{'floor': 1, 'eventType': 'SetSpeed', **event}]})


def test_twirl_spiral_direction_alternates_without_changing_centers():
    track = build_track({'pathData': 'RRR', 'actions': [
        {'floor': 1, 'eventType': 'Twirl'}, {'floor': 2, 'eventType': 'Twirl'}]})
    assert [t.twirl_clockwise for t in track.tiles] == [True, False, True, True]
    assert [(t.x, t.y) for t in track.tiles] == [(0, 0), (1, 0), (2, 0), (3, 0)]
    a, b = local_icon('twirl', True)[0], local_icon('twirl', False)[0]
    for (ax, ay), (bx, by) in zip(a['points'], b['points']):
        assert ax == pytest.approx(bx)
        assert ay == pytest.approx(-by)


@pytest.mark.parametrize('kind', ['rabbit', 'turtle', 'twirl'])
def test_icons_rotate_with_tile_axis_and_can_stay_upright(kind):
    tile = Tile(0, 5, 3, None, 0, twirl=kind == 'twirl', speed_icon=None if kind == 'twirl' else kind)
    original = icon_primitives(tile)
    rotated = icon_primitives(replace(tile, outgoing=90))
    upright = icon_primitives(replace(tile, outgoing=90), rotate_icons=False)
    assert original == upright
    for a, b in zip(original, rotated):
        for (x, y), (rx, ry) in zip(a['points'], b['points']):
            assert (rx, ry) == pytest.approx((5-(y-3), 3+(x-5)))


def test_multiple_icons_share_brick_without_spilling_outside_body():
    tile = Tile(0, 0, 0, None, 45, midspin=True, twirl=True, checkpoint=True, speed_icon='rabbit')
    parts = icon_primitives(tile)
    assert {p['icon_type'] for p in parts} == {'rabbit', 'twirl', 'midspin', 'checkpoint'}
    assert all(math.hypot(x, y) < .29 for p in parts for x, y in p['points'])


def test_colored_png_and_svg_contain_real_vector_rabbit_turtle_and_twirl(tmp_path):
    track = build_track({'pathData': 'RRRRRR', 'settings': {'bpm': 100, 'trackColor': '00ff00'}, 'actions': [
        {'floor': 1, 'eventType': 'SetSpeed', 'speedType': 'Bpm', 'beatsPerMinute': 200},
        {'floor': 3, 'eventType': 'SetSpeed', 'speedType': 'Bpm', 'beatsPerMinute': 100},
        {'floor': 5, 'eventType': 'Twirl'}]})
    render_selection(track, tmp_path/'icons.png', width=1400, height=400, padding=25)
    svg = ET.parse(tmp_path/'icons.svg').getroot()
    assert {e.attrib['data-icon'] for e in svg.iter() if 'data-icon' in e.attrib} == {'rabbit', 'turtle', 'twirl'}
    assert {e.attrib['fill'] for e in svg.findall('.//{*}polygon')} == {'#00ff00ff'}
    with Image.open(tmp_path/'icons.png') as image:
        colors = {color for _, color in image.convert('RGB').getcolors(image.width*image.height)}
        for wanted in [(0, 255, 0), (255, 185, 107), (155, 230, 147), (255, 138, 203)]:
            assert wanted in colors
