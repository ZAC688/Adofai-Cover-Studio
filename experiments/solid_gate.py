"""Run the production recognizer on every approved test_2 sample, score IoU."""
from pathlib import Path
import hashlib
import json

from PIL import Image

from backend.app.recognition import track_mask
from experiments.p0 import quality_metrics

ROOT = Path(__file__).resolve().parents[1]


def assess_solid_dataset(manifest_path=ROOT / 'test-assets/solid/manifest.json', output=None):
    output = output or ROOT / 'artifacts/upgrade-04/02-recognition/predictions'
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    failures, results = [], []
    for sample in manifest['samples']:
        source = ROOT / sample['file']
        truth_path = manifest_path.parent / sample['ground_truth']
        if not sample.get('annotation_approved'):
            failures.append(f"{sample['id']}: annotation not approved")
            continue
        if hashlib.sha256(source.read_bytes()).hexdigest() != sample['sha256']:
            failures.append(f"{sample['id']}: source hash mismatch")
            continue
        if hashlib.sha256(truth_path.read_bytes()).hexdigest() != sample['annotation_sha256']:
            failures.append(f"{sample['id']}: frozen annotation hash mismatch")
            continue
        with Image.open(source) as image:
            predicted = track_mask(image, ROOT / 'models/u2netp.onnx')
            predicted.save(output / f"{sample['id']}-mask.png")
        with Image.open(truth_path) as truth:
            values = quality_metrics(predicted, truth)
        results.append({'id': sample['id'], **values})
        if values['intersection_over_union'] < manifest['thresholds']['intersection_over_union_min']:
            failures.append(f"{sample['id']}: IoU {values['intersection_over_union']:.4%} < 90%")
    report = {'passed': not failures and len(results) == 9, 'failures': failures, 'results': results}
    (output.parent / 'quality-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(assess_solid_dataset(), indent=2))
