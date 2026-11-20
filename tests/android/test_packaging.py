import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
APK = ROOT / 'android/app/build/outputs/apk/debug/app-debug.apk'
RELEASE_APK = ROOT / 'android/app/build/outputs/apk/release/app-release.apk'


@pytest.fixture(scope='module', params=[APK, RELEASE_APK], ids=['debug', 'release'])
def apk(request):
    assert request.param.is_file(), 'Build both debug and release APKs before Android packaging tests'
    with zipfile.ZipFile(request.param) as bundle:
        assert bundle.testzip() is None
        yield bundle


def test_both_target_and_emulator_have_real_python_sqlite_and_onnx(apk):
    for abi, architecture in (('arm64-v8a', 183), ('x86_64', 62)):
        # libsqlite3_chaquopy is only an ABI shim; _python contains SQLite itself.
        for library in ('libpython3.13.so', 'libsqlite3_python.so', 'libonnxruntime.so', 'libonnxruntime4j_jni.so'):
            path = f'lib/{abi}/{library}'
            assert apk.getinfo(path).file_size > 10000
            header = apk.read(path)[:20]
            assert header[:5] == b'\x7fELF\x02'
            assert int.from_bytes(header[18:20], 'little') == architecture
    assert apk.getinfo('AndroidManifest.xml').file_size > 0
    assert apk.getinfo('classes.dex').file_size > 10000


def test_all_bundled_resources_match_manifest_and_exclude_private_material(apk):
    manifest=apk.read('assets/runtime/resource-manifest.json')
    expected = json.loads(manifest)
    info=json.loads(apk.read('assets/runtime/bundle-info.json'))
    assert info['resourceFingerprint']==hashlib.sha256(manifest).hexdigest()
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


def test_apk_signature_is_valid(apk):
    signer = ROOT / 'tools/android-sdk/build-tools/35.0.0/apksigner.bat'
    assert signer.is_file()
    result = subprocess.run([str(signer), 'verify', '--verbose', str(apk.filename)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Verifies' in result.stdout


def test_release_is_separate_nondebuggable_and_signed_by_the_preserved_local_identity():
    import os
    import re
    from tests.android.test_signing import keytool
    aapt = ROOT / 'tools/android-sdk/build-tools/35.0.0/aapt.exe'
    result = subprocess.run([str(aapt), 'dump', 'badging', str(RELEASE_APK)], capture_output=True, timeout=30)
    assert result.returncode == 0
    badging = result.stdout.decode('utf-8')
    assert "package: name='com.zac688.adofaicoverstudio'" in badging
    assert "versionName='0.8.1-android.2'" in badging
    assert "sdkVersion:'29'" in badging and "targetSdkVersion:'35'" in badging
    assert 'application-debuggable' not in badging
    private_receiver = 'com.zac688.adofaicoverstudio.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'
    assert set(re.findall(r"uses-permission: name='([^']+)'", badging)) == {'android.permission.INTERNET', private_receiver}
    manifest = subprocess.run([str(aapt), 'dump', 'xmltree', str(RELEASE_APK), 'AndroidManifest.xml'], capture_output=True, timeout=30)
    assert manifest.returncode == 0
    declaration = manifest.stdout.decode('utf-8').split('E: permission (', 1)[1].split('E: uses-permission (', 1)[0]
    assert private_receiver in declaration and 'android:protectionLevel(0x01010009)=(type 0x11)0x2' in declaration
    xml = manifest.stdout.decode('utf-8')
    assert 'android:allowBackup(0x01010280)=(type 0x12)0x0' in xml
    assert 'android:fullBackupContent' in xml and 'android:dataExtractionRules' in xml
    identity = json.loads((ROOT/'android/signing/release.json').read_text())
    environment = dict(os.environ, ADOFAI_KEY_PASSWORD=identity['storePassword'])
    certificate = subprocess.run([str(keytool()), '-exportcert', '-keystore', str(ROOT/'android/signing'/identity['storeFile']),
                                  '-storepass:env', 'ADOFAI_KEY_PASSWORD', '-alias', identity['keyAlias']],
                                 env=environment, capture_output=True, timeout=30)
    assert certificate.returncode == 0
    digest = hashlib.sha256(certificate.stdout).hexdigest()
    signer = ROOT/'tools/android-sdk/build-tools/35.0.0/apksigner.bat'
    signed = subprocess.run([str(signer), 'verify', '--print-certs', str(RELEASE_APK)], capture_output=True, text=True, timeout=30)
    assert signed.returncode == 0
    assert f'certificate SHA-256 digest: {digest}' in signed.stdout
    with zipfile.ZipFile(RELEASE_APK) as bundle:
        assert not any(name.startswith(('assets/solid/', 'assets/model-reference')) for name in bundle.namelist())


def test_all_native_dependencies_including_nested_archives_support_16kb(apk):
    from tools.check_android_pages import audit
    result = audit(Path(apk.filename), ROOT/'tools/android-sdk/build-tools/35.0.0/zipalign.exe')
    assert set(result['counts']) == {'arm64-v8a', 'x86_64'}
    assert min(result['counts'].values()) >= 90, 'Both embedded Python runtimes must be audited'
    assert result['passed'], [record for record in result['libraries'] if record['issues']]


def test_source_built_libraries_exclude_debug_data_and_local_workspace_paths(apk):
    for abi in ('arm64-v8a', 'x86_64'):
        with zipfile.ZipFile(io.BytesIO(apk.read(f'assets/chaquopy/requirements-{abi}.imy'))) as libraries:
            for name in ('cv2.so', 'chaquopy/lib/libfreetype.so', 'chaquopy/lib/libjpeg_chaquopy.so'):
                data = libraries.read(name)
                assert ROOT.as_posix().encode() not in data
                assert str(ROOT).encode() not in data
                assert b'.debug_info\0' not in data
                package = {'cv2.so': 'opencv_python_headless-4.12.0.88-1-cp313-cp313-',
                           'chaquopy/lib/libfreetype.so': 'chaquopy_freetype-2.9.1-3-py3-none-',
                           'chaquopy/lib/libjpeg_chaquopy.so': 'chaquopy_libjpeg-3.1.3-1-py3-none-'}[name]
                wheel = ROOT/'tools/android-downloads/native-16kb/wheels'/f'{package}android_24_{abi.replace("-", "_")}.whl'
                with zipfile.ZipFile(wheel) as built:
                    assert hashlib.sha256(data).digest() == hashlib.sha256(built.read(name)).digest(), 'APK contains a stale native wheel'
    # Chaquopy deduplicates non-native files into the common archive.
    with zipfile.ZipFile(io.BytesIO(apk.read('assets/chaquopy/requirements-common.imy'))) as common:
        work = ROOT/'tools/android-downloads/native-16kb'
        licenses = {
            'chaquopy_freetype-2.9.1.dist-info/licenses/FTL.TXT': work/'freetype-2.9.1/freetype-VER-2-9-1/docs/FTL.TXT',
            'opencv_python_headless-4.12.0.88.dist-info/licenses/cpufeatures/LICENSE': work/'opencv-4.12.0/opencv-4.12.0/3rdparty/cpufeatures/LICENSE',
            'opencv_python_headless-4.12.0.88.dist-info/licenses/kleidicv/kleidicv-0.5.0/LICENSES/Apache-2.0.txt': work/'build/arm64-v8a/opencv/3rdparty/kleidicv/kleidicv-0.5.0/LICENSES/Apache-2.0.txt',
        }
        for name, source in licenses.items():
            assert common.read(name) == source.read_bytes(), 'Bundled license differs from the upstream source'
