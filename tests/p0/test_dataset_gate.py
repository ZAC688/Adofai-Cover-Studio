from pathlib import Path
import json

from PIL import Image
import pytest

from experiments.p0 import assess_dataset, saliency_mask
from experiments.solid_gate import assess_solid_dataset

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def solid_report(tmp_path_factory):
    return assess_solid_dataset(output=tmp_path_factory.mktemp('solid-predictions'))


def test_current_gate_contains_all_nine_approved_unmodified_real_samples(solid_report):
    manifest = json.loads((ROOT / 'test-assets/solid/manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['samples']) == 9
    assert manifest['thresholds']['intersection_over_union_min'] == .9
    assert solid_report['passed'], '\n'.join(solid_report['failures'])


@pytest.mark.parametrize('sample_id', [f'solid-{i:02}' for i in range(1, 10)])
def test_each_solid_screenshot_automatic_iou_at_least_ninety_percent(solid_report, sample_id):
    values = next(row for row in solid_report['results'] if row['id'] == sample_id)
    assert values['intersection_over_union'] >= .9, values


def test_historical_complex_report_still_records_its_real_failures(tmp_path):
    # User explicitly replaced the active acceptance scope with solid test_2 / IoU.
    # Recompute the old model's known failures rather than erasing or blessing them.
    manifest_path = ROOT / 'test-assets/manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for sample in manifest['samples']:
        if sample.get('annotation_approved'):
            with Image.open(manifest_path.parent / sample['file']) as image:
                saliency_mask(image, ROOT / 'models/u2netp.onnx').save(tmp_path / f"{sample['id']}-mask.png")
    report = assess_dataset(manifest_path, tmp_path)
    assert not report['passed']
    assert any('sample-03: recognition is below' in failure for failure in report['failures'])
    assert any('sample-08: recognition is below' in failure for failure in report['failures'])
    assert any('missing approved ground-truth' in failure for failure in report['failures'])
