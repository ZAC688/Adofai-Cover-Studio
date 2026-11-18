import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
APK = ROOT / 'android/app/build/outputs/apk/debug/app-debug.apk'


@pytest.fixture(scope='module')
def apk():
    assert APK.is_file(), 'Run tools/build-android.ps1 before the Android packaging tests'
    with zipfile.ZipFile(APK) as bundle:
        assert bundle.testzip() is None
        yield bundle


def test_both_target_and_emulator_have_real_python_sqlite_and_onnx(apk):
    for abi, architecture in (('arm64-v8a', 183), ('x86_64', 62)):
        # libsqlite3_chaquopy is only an ABI shim; _python contains SQLite itself.
        for library in ('libpython3.10.so', 'libsqlite3_python.so', 'libonnxruntime.so', 'libonnxruntime4j_jni.so'):
            path = f'lib/{abi}/{library}'
            assert apk.getinfo(path).file_size > 10000
            header = apk.read(path)[:20]
            assert header[:5] == b'\x7fELF\x02'
            assert int.from_bytes(header[18:20], 'little') == architecture
    assert apk.getinfo('AndroidManifest.xml').file_size > 0
    assert apk.getinfo('classes.dex').file_size > 10000


def test_all_bundled_resources_match_manifest_and_exclude_private_material(apk):
    expected = json.loads(apk.read('assets/runtime/resource-manifest.json'))
    with zipfile.ZipFile(io.BytesIO(apk.read('assets/runtime/runtime.zip'))) as resources:
        names = resources.namelist()
        assert resources.testzip() is None
        assert set(names) == {item['path'] for item in expected}
        for item in expected:
            content = resources.read(item['path'])
            assert len(content) == item['size']
            assert hashlib.sha256(content).hexdigest() == item['sha256']
        assert 'frontend/dist/index.html' in names and 'experiments/static_track_editor.html' in names
        assert hashlib.sha256(resources.read('models/u2netp.onnx')).hexdigest() == '309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8'
        assert len([name for name in names if name.startswith('Logos/')]) == 253
        assert resources.read('frontend/dist/index.html') == (ROOT / 'frontend/dist/index.html').read_bytes()
        for name in names:
            assert not name.startswith(('generate_test/', 'testscreenshots/', 'test-assets/', 'artifacts/', '.git/'))
            assert not name.lower().endswith(('.adofai', '.mp3', '.ogg', '.sqlite3', '.jks', '.keystore', '.docx'))


def test_apk_signature_is_valid():
    signer = ROOT / 'tools/android-sdk/build-tools/35.0.0/apksigner.bat'
    assert signer.is_file()
    result = subprocess.run([str(signer), 'verify', '--verbose', str(APK)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Verifies' in result.stdout
