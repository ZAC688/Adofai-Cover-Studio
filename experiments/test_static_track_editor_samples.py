"""Explicit private-chart acceptance for high-resolution selected segments."""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image
import pytest

from experiments.static_track_editor import generate_editor
from experiments.static_track_probe import ROOT


@pytest.fixture(scope='module')
def generated(tmp_path_factory):
    output = tmp_path_factory.mktemp('static-editor-real')
    assert (ROOT/'generate_test').is_dir()
    payload = generate_editor(ROOT/'generate_test', output)
    assert len(payload['charts']) == 4
    return output, payload


@pytest.mark.parametrize('index,color', [(0, '#ffffffff'), (1, '#00ff00ff'), (2, '#ff8800ff'), (3, '#4c98cdff')])
def test_four_private_charts_export_native_4k_with_colors_and_exact_selection(generated, index, color):
    output, payload = generated
    chart = payload['charts'][index]
    a, b = chart['sample_range']
    assert chart['color'] == color
    root = ET.parse(output/chart['id']/'thumbnail-4k.svg').getroot()
    assert {int(e.attrib['data-floor']) for e in root.findall('.//{*}polygon')} == set(range(a, b+1))
    assert any('data-icon' in e.attrib for e in root.iter())
    with Image.open(output/chart['id']/'thumbnail-4k.png') as image:
        assert image.size == (3840, 2160)
        assert image.mode == 'RGBA'
        box = image.getchannel('A').getbbox()
        assert box and min(box[:2]) > 0 and box[2] < 3840 and box[3] < 2160


def test_all_private_sources_remain_unchanged_and_page_is_self_contained(generated):
    import json
    output, _ = generated
    manifest = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_files_unchanged'] is True
    assert manifest['visual_match_status'] == 'NOT_VERIFIED_AGAINST_GAME'
    assert len(manifest['source_hashes']) == 10
    for name, digest in manifest['source_hashes'].items():
        assert hashlib.sha256((ROOT/'generate_test'/name).read_bytes()).hexdigest() == digest
    html = (output/'index.html').read_text(encoding='utf-8')
    assert '/*__TRACK_DATA__*/' not in html
    assert '<script src=' not in html and '<link ' not in html
