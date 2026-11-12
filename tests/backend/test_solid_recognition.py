from pathlib import Path
import hashlib
import json
import time

import numpy as np
from PIL import Image, ImageDraw
import pytest

from backend.app.jobs import Jobs
from backend.app.recognition import fill_bounded_holes, solid_track_mask, track_mask
from backend.app.storage import Store
from experiments.p0 import quality_metrics

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / 'test-assets/solid/manifest.json').read_text(encoding='utf-8'))


def wait(jobs, job_id):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        job = jobs.get(job_id)
        if job['status'] != 'running':
            return job
        time.sleep(.05)
    raise AssertionError('Recognition job did not finish')


@pytest.mark.parametrize('sample', MANIFEST['samples'], ids=lambda row: row['id'])
def test_actual_job_uses_current_recognizer_and_meets_each_native_size_gate(tmp_path, sample):
    source = ROOT / sample['file']
    truth_path = ROOT / 'test-assets/solid' / sample['ground_truth']
    assert sample['annotation_approved']
    assert hashlib.sha256(truth_path.read_bytes()).hexdigest() == sample['annotation_sha256']
    store = Store(tmp_path)
    asset = store.put_image(source.read_bytes())
    jobs = Jobs(store)
    try:
        result = wait(jobs, jobs.start(asset['id'])['id'])
        assert result['status'] == 'succeeded', result
        with Image.open(store.asset_path(result['result']['id'])) as mask, Image.open(truth_path) as truth, Image.open(source) as image:
            assert mask.size == image.size == truth.size
            assert mask.mode == 'L'
            assert mask.tobytes() == track_mask(image, ROOT / 'models/u2netp.onnx').tobytes()
            assert quality_metrics(mask, truth)['intersection_over_union'] >= .9
        assert store.load()['revision'] == 0
    finally:
        jobs.close()


def test_diagonal_outline_is_closed_without_filling_external_background():
    mask = np.zeros((9, 9), np.uint8)
    for y, x in [(2, 4), (3, 3), (4, 2), (5, 3), (6, 4), (5, 5), (4, 6), (3, 5)]:
        mask[y, x] = 255
    result = fill_bounded_holes(mask, 30)
    assert result[4, 4] == 255
    assert result[0, 0] == 0


def test_nonblack_solid_background_and_transparency_without_source_mutation():
    image = Image.new('RGBA', (400, 240), '#b83a4a')
    draw = ImageDraw.Draw(image)
    draw.rectangle((110, 40, 129, 190), fill='#2fb6e9')
    draw.rectangle((110, 170, 280, 189), fill='#2fb6e9')
    draw.rectangle((110, 70, 129, 80), fill=(47, 182, 233, 0))
    before = image.tobytes()
    mask = solid_track_mask(image)
    assert mask.getpixel((120, 120)) == 255
    assert mask.getpixel((240, 180)) == 255
    assert mask.getpixel((10, 10)) == 0
    assert mask.getpixel((120, 75)) == 0
    assert image.tobytes() == before


def test_uniform_image_produces_empty_mask_and_tiny_image_is_rejected():
    assert not np.asarray(solid_track_mask(Image.new('RGB', (320, 180), '#2467ab'))).any()
    with pytest.raises(ValueError, match='尺寸太小'):
        solid_track_mask(Image.new('RGB', (2, 2)))
