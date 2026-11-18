"""Bundle only approved runtime resources, never private fixtures or user data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def prepare():
    frontend = ROOT / 'frontend/dist'
    if not (frontend / 'index.html').is_file():
        raise RuntimeError('Build the frontend before preparing Android assets')
    from experiments.p0 import validate_model
    validate_model(ROOT / 'models/u2netp.onnx')
    generated = ROOT / 'android/app/build/generated/python'
    for directory, patterns in [('backend', ['**/*.py']), ('experiments', ['p0.py', 'static_track*.py', '__init__.py'])]:
        source = ROOT / directory
        for pattern in patterns:
            for path in source.glob(pattern):
                target = generated / directory / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    assets = ROOT / 'android/app/src/main/assets/runtime'
    assets.mkdir(parents=True, exist_ok=True)
    resources = list(frontend.rglob('*'))
    resources += [path for path in (ROOT / 'Logos').rglob('*') if path.suffix.lower() in {'.png', '.gif'}]
    resources += [ROOT / 'models/u2netp.onnx', ROOT / 'experiments/static_track_editor.html', ROOT / 'LICENSE']
    manifest = []
    with zipfile.ZipFile(assets / 'runtime.zip', 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(set(resources)):
            if not path.is_file(): continue
            name = path.relative_to(ROOT).as_posix()
            content = path.read_bytes()
            bundle.writestr(name, content)
            manifest.append({'path': name, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
    manifest_bytes=json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
    (assets / 'resource-manifest.json').write_bytes(manifest_bytes)
    (assets / 'bundle-info.json').write_text(json.dumps({'resourceFingerprint':hashlib.sha256(manifest_bytes).hexdigest()}),encoding='utf-8')
    drawable = ROOT / 'android/app/src/main/res/drawable'
    drawable.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'frontend/public/app-icon.png', drawable / 'app_icon.png')
    print(f'Bundled {len(manifest)} offline resources; private fixtures excluded')


if __name__ == '__main__':
    prepare()
