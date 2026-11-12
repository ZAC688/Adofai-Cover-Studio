"""Freeze the nine draft labels explicitly approved by the user on 2026-11-09."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'test-assets/solid/manifest.json'
manifest = json.loads(path.read_text(encoding='utf-8'))
destination = path.parent / 'annotations'
destination.mkdir(exist_ok=True)
for sample in manifest['samples']:
    source = path.parent / sample['ground_truth']
    target = destination / f"{sample['id']}.png"
    shutil.copyfile(source, target)
    sample.update(ground_truth=f"annotations/{target.name}", annotation_approved=True,
                  annotation_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  approval='User explicitly approved all nine original/overlay/cutout review sheets on 2026-11-09.')
manifest['annotation_status'] = 'APPROVED_AND_FROZEN'
path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
