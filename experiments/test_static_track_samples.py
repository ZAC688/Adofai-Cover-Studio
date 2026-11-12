"""Explicit local acceptance check using the user's four private chart groups.

Run separately from the portable suite; missing/changed samples fail, never skip.
This validates export/geometry contracts, not visual identity with the game.
"""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
import pytest

from experiments.static_track_probe import ROOT, build_track, main_charts, read_chart, run

EXPECTED = {
    "Heaven's Gateway": (3354, 56, 60, '4cb7f77389d32c49feaab89b86a26ca04edef618102436ca41c7ea16ea3649e2'),
    'The Limit Does Not Exist': (1360, 0, 0, '77cbb5fb1a2a0f4225b906a79be7c0fd460100fb6073958479c398bd13eb3853'),
    'Inferno': (1795, 36, 0, '0f6900d60588ac3d323593e5c058d46c9e4160f64b196b63e026737a504eea7c'),
    'Crystallized': (2040, 108, 1, 'c0c2a929c79040ef8ada0f5c764dd5473e1afbf5fb1bb5dc4fde8a42da3b2601'),
}


@pytest.fixture(scope='module')
def generated(tmp_path_factory):
    folder = ROOT / 'generate_test'
    assert folder.is_dir(), 'Private generate_test samples are required for this explicit acceptance run'
    assert len(main_charts(folder)) == 4
    output = tmp_path_factory.mktemp('static-track-samples')
    manifest = run(folder, output)
    return output, manifest


@pytest.mark.parametrize('name', EXPECTED)
def test_four_real_charts_have_expected_identity_and_exported_nodes(generated, name):
    output, manifest = generated
    entry = next(r for r in manifest['charts'] if r['display_name'] == name)
    count, midspins, offsets, sha = EXPECTED[name]
    assert entry['sha256'] == sha
    assert hashlib.sha256(Path(entry['input']).read_bytes()).hexdigest() == sha
    assert (entry['angle_count'], entry['tile_count'], entry['midspin_count'], entry['position_events_applied']) == (count, count+1, midspins, offsets)
    geometry = json.loads((output / entry['id'] / 'geometry.json').read_text(encoding='utf-8'))
    assert [t['floor'] for t in geometry['tiles']] == list(range(count+1))
    assert all(math.isfinite(t[k]) for t in geometry['tiles'] for k in ['x', 'y'])
    svg = ET.parse(output / entry['id'] / 'track.svg').getroot()
    assert len(svg.findall('{*}polygon')) == count+1
    with Image.open(output / entry['id'] / 'track.png') as image:
        assert image.mode == 'RGBA'
        assert image.getchannel('A').getextrema() == (0, 255)
        bbox = image.getchannel('A').getbbox()
        assert bbox and bbox[0] > 0 and bbox[1] > 0 and bbox[2] < image.width and bbox[3] < image.height


def test_all_source_charts_including_variants_are_unchanged(generated):
    _, manifest = generated
    assert manifest['source_files_unchanged'] is True
    assert manifest['all_chart_sha256_before'] == manifest['all_chart_sha256_after']
    assert len(manifest['all_chart_sha256_before']) > 4


@pytest.mark.parametrize('name', EXPECTED)
def test_real_base_geometry_moves_one_unit_and_midspins_retrace(generated, name):
    _, manifest = generated
    path = next(r['input'] for r in manifest['charts'] if r['display_name'] == name)
    chart = read_chart(Path(path))
    track = build_track(chart, apply_offsets=False)
    for left, right in zip(track.tiles, track.tiles[1:]):
        assert math.hypot(right.x-left.x, right.y-left.y) == pytest.approx(1, abs=1e-9)
    for i, tile in enumerate(track.tiles[:-1]):
        if tile.midspin:
            assert i > 0
            assert (track.tiles[i+1].x, track.tiles[i+1].y) == pytest.approx((track.tiles[i-1].x, track.tiles[i-1].y), abs=1e-8)


def test_limitations_are_visible_and_no_claim_of_game_match(generated):
    output, manifest = generated
    assert manifest['visual_match_status'] == 'NOT_VERIFIED_AGAINST_GAME'
    heaven = next(r for r in manifest['charts'] if r['display_name'] == "Heaven's Gateway")
    assert len(heaven['notes']) == 3
    assert heaven['editor_only_position_events_ignored'] == 2
    assert '缩放与粘性轨道' in (output / 'index.html').read_text(encoding='utf-8')
