"""Hand-computed geometry and image contracts; no private chart dependency."""
import json
import math
import xml.etree.ElementTree as ET

from PIL import Image
import pytest

from experiments.static_track_probe import (
    Tile, bounds, build_track, decode_angles, main_charts, read_chart,
    render_track, tile_polygon,
)


def centers(track):
    return [(t.x, t.y) for t in track.tiles]


def assert_centers(track, expected):
    assert len(track.tiles) == len(expected)
    for actual, wanted in zip(centers(track), expected):
        assert actual == pytest.approx(wanted, abs=1e-9)


def test_legacy_json_preserves_metadata_and_comments_after_trailing_comma(tmp_path):
    path = tmp_path / 'chart.adofai'
    # Write the exact LF fixture bytes; Windows write_text would insert CRLF
    # inside the metadata string and test a different string than intended.
    path.write_bytes(('\ufeff{ "pathData":"RUL", // comment\n'
                    '"settings":{"url":"https://example.test/a/*text*/,}",'
                    '"song":"line one\nline two", "quote":"a\\\"b",},'
                    '"actions":[{"floor":1,"eventType":"Twirl", /* ok */}, // end\n],}')
                    .encode('utf-8'))
    original = path.read_bytes()
    result = read_chart(path)
    assert result['pathData'] == 'RUL'
    assert result['settings']['url'] == 'https://example.test/a/*text*/,}'
    assert result['settings']['song'] == 'line one\nline two'
    assert result['settings']['quote'] == 'a"b'
    assert result['actions'] == [{'floor': 1, 'eventType': 'Twirl'}]
    assert path.read_bytes() == original


@pytest.mark.parametrize('text', ['[]', '{bad}', '{"angleData":[NaN]}',
                                       '{"angleData":[Infinity]}', '{/* no end'])
def test_malformed_chart_fails_without_guessing(tmp_path, text):
    path = tmp_path / 'bad.adofai'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError):
        read_chart(path)


def test_square_has_one_more_center_than_directions_and_y_is_up():
    assert_centers(build_track({'pathData': 'RULD'}),
                   [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])


def test_path_and_angle_encodings_agree_with_hand_calculated_diagonal():
    expected = [(0, 0), (1, 0), (1+math.sqrt(.5), math.sqrt(.5)),
                (1, 2*math.sqrt(.5))]
    assert_centers(build_track({'pathData': 'REQ'}), expected)
    assert_centers(build_track({'angleData': [0, 45, 135]}), expected)


def test_all_24_absolute_path_directions_and_old_midspin_character():
    angles, midspins = decode_angles({'pathData': 'RpJEToUqGQHWLxNZFVDYBCMA!'})
    assert angles[:-1] == list(range(0, 360, 15))
    assert angles[-1] == 165
    assert midspins == [False]*24 + [True]


def test_midspin_returns_to_previous_center_instead_of_repeating_direction():
    track = build_track({'angleData': [0, 150, 999, 0]})
    assert_centers(track, [(0, 0), (1, 0), (1-math.sqrt(3)/2, .5), (1, 0), (2, 0)])
    assert track.tiles[2].midspin
    assert track.tiles[2].outgoing == 330
    assert not track.tiles[-1].midspin


def test_consecutive_midspins_and_negative_unwrapped_angles():
    assert_centers(build_track({'angleData': [0, 999, 999, -270, 450]}),
                   [(0, 0), (1, 0), (0, 0), (1, 0), (1, 1), (1, 2)])


@pytest.mark.parametrize('chart', [
    {'pathData': 'RX'}, {'pathData': '5'}, {'angleData': []}, {'angleData': [999]},
    {'angleData': [True]}, {'angleData': ['90']}, {'angleData': [float('inf')]},
    {'angleData': [555]}, {'angleData': 'R'}, {},
])
def test_unsupported_or_invalid_directions_fail_explicitly(chart):
    with pytest.raises(ValueError):
        build_track(chart)


@pytest.mark.parametrize('kind', ['MoveTrack', 'MoveCamera', 'SetSpeed', 'Twirl',
                                 'AnimateTrack', 'AddDecoration', 'Bloom', 'SetFilter'])
def test_out_of_scope_time_events_do_not_change_static_centers(kind):
    chart = {'angleData': [0, 90, 180, 270]}
    baseline = centers(build_track(chart))
    chart['actions'] = [{'floor': 1, 'eventType': kind, 'positionOffset': [100, -80],
                         'rotation': 123, 'scale': [900, 50], 'duration': 0,
                         'beatsPerMinute': 1000, 'decorationImage': '../../not-read.png'}]
    assert centers(build_track(chart)) == baseline


def test_position_offsets_propagate_and_local_offsets_do_not():
    chart = {'pathData': 'RRR', 'actions': [
        {'floor': 1, 'eventType': 'PositionTrack', 'positionOffset': [2, 3]},
        {'floor': 2, 'eventType': 'PositionTrack', 'positionOffset': [0, -5], 'justThisTile': True},
    ]}
    assert_centers(build_track(chart), [(0, 0), (3, 3), (4, -2), (5, 3)])
    assert_centers(build_track(chart, apply_offsets=False), [(0, 0), (1, 0), (2, 0), (3, 0)])


@pytest.mark.parametrize('flag', [True, 'Enabled'])
def test_editor_only_offsets_do_not_change_game_layout(flag):
    chart = {'pathData': 'RR', 'actions': [
        {'floor': 1, 'eventType': 'PositionTrack', 'positionOffset': [100, 100], 'editorOnly': flag}]}
    assert_centers(build_track(chart), [(0, 0), (1, 0), (2, 0)])
    assert build_track(chart).position_events_applied == 0


def test_unimplemented_static_transforms_are_disclosed():
    chart = {'pathData': 'RR', 'settings': {'stickToFloors': True}, 'actions': [
        {'floor': 1, 'eventType': 'PositionTrack', 'positionOffset': [1, 0], 'scale': 120},
        {'floor': 1, 'eventType': 'ScaleRadius', 'scale': 150}]}
    track = build_track(chart)
    assert len(track.notes) == 3
    assert any('ScaleRadius (1)' in note for note in track.notes)
    assert any('non-default transform (1)' in note for note in track.notes)
    assert any('stickToFloors' in note for note in track.notes)


@pytest.mark.parametrize('event', [
    {'floor': -1}, {'floor': 100}, {'floor': True},
    {'floor': 1, 'eventType': 'PositionTrack', 'relativeTo': [1, 'Start']},
    {'floor': 1, 'eventType': 'PositionTrack', 'positionOffset': ['bad', 0]},
])
def test_bad_events_are_not_silently_accepted(event):
    with pytest.raises(ValueError):
        build_track({'pathData': 'RR', 'actions': [event]})


def test_offset_jump_does_not_create_a_bridge():
    track = build_track({'pathData': 'RR', 'actions': [
        {'floor': 1, 'eventType': 'PositionTrack', 'positionOffset': [40, 50]}]})
    for tile in track.tiles:
        for x, y in tile_polygon(tile):
            assert math.hypot(x-tile.x, y-tile.y) < .6
    assert bounds(track.tiles[:1])[2] < 1
    assert bounds(track.tiles[1:])[0] > 40


def test_png_svg_are_transparent_finite_unclipped_and_y_up(tmp_path):
    path = tmp_path / 'track.png'
    track = build_track({'pathData': 'RU'})
    meta = render_track(track, path, max_side=500)
    with Image.open(path) as image:
        assert image.mode == 'RGBA'
        assert image.size == (meta['width'], meta['height'])
        alpha = image.getchannel('A')
        assert alpha.getextrema() == (0, 255)
        for edge in [alpha.crop((0, 0, image.width, 1)), alpha.crop((0, image.height-1, image.width, image.height)),
                     alpha.crop((0, 0, 1, image.height)), alpha.crop((image.width-1, 0, image.width, image.height))]:
            assert edge.getbbox() is None
    svg = ET.parse(path.with_suffix('.svg')).getroot()
    polygons = {int(p.attrib['data-floor']): p for p in svg.findall('{*}polygon')}
    assert set(polygons) == {0, 1, 2}
    def average_y(polygon):
        return sum(float(point.split(',')[1]) for point in polygon.attrib['points'].split()) / len(polygon.attrib['points'].split())
    assert average_y(polygons[2]) < average_y(polygons[1])


def test_extremely_long_track_has_transparent_pixel_border(tmp_path):
    path = tmp_path / 'long.png'
    render_track(build_track({'angleData': [0]*1500}), path, max_side=500)
    with Image.open(path) as image:
        alpha = image.getchannel('A')
        assert alpha.getbbox() is not None
        assert alpha.crop((0, 0, 1, image.height)).getbbox() is None
        assert alpha.crop((image.width-1, 0, image.width, image.height)).getbbox() is None


def test_primary_chart_selection_avoids_backups_and_is_ambiguous_safe(tmp_path):
    folder = tmp_path / 'group'
    folder.mkdir()
    for name in ['backup.adofai', 'main Outer.adofai', 'main.adofai']:
        (folder / name).write_text('{}')
    assert main_charts(tmp_path) == [folder / 'main.adofai']
    nested = folder / 'nested'
    nested.mkdir()
    (nested / 'main.adofai').write_text('{}')
    with pytest.raises(ValueError, match='Ambiguous'):
        main_charts(tmp_path)
