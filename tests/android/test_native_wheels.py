import base64
import csv
import hashlib
import io
import json
import zipfile

import pytest

from tests.android.test_page_sizes import elf
from tools import build_android_native as native


def test_source_wheel_record_verifies_every_byte_and_preserves_license(tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'OUTPUT', tmp_path)
    path=native.wheel('sample','1.0','1','py3-none-android_24_arm64_v8a',
                      {'sample.so':elf(),'sample-1.0.dist-info/licenses/LICENSE':b'upstream license'},['numpy>=1.26'])
    with zipfile.ZipFile(path) as bundle:
        rows=list(csv.reader(io.StringIO(bundle.read('sample-1.0.dist-info/RECORD').decode())))
        assert {r[0] for r in rows}==set(bundle.namelist())
        for name,digest,length in rows[:-1]:
            content=bundle.read(name)
            assert int(length)==len(content)
            assert digest=='sha256='+base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
        assert b'Requires-Dist: numpy>=1.26' in bundle.read('sample-1.0.dist-info/METADATA')
        assert bundle.read('sample-1.0.dist-info/licenses/LICENSE')==b'upstream license'


def test_source_wheel_fails_on_an_incompatible_library(tmp_path, monkeypatch):
    monkeypatch.setattr(native,'OUTPUT',tmp_path)
    with pytest.raises(ValueError,match='16KB ELF audit'):
        native.wheel('broken','1.0','1','py3-none-android_24_arm64_v8a',{'broken.so':elf(4096)})


def test_cached_native_build_is_invalidated_by_modified_wheel_bytes(tmp_path, monkeypatch):
    output=tmp_path/'wheels';output.mkdir()
    monkeypatch.setattr(native,'OUTPUT',output)
    monkeypatch.setattr(native,'WORK',tmp_path)
    wheels={}
    for i in range(6):
        name=f'fixture-{i}.whl';(output/name).write_bytes(b'verified bytes')
        wheels[name]=hashlib.sha256(b'verified bytes').hexdigest()
    (tmp_path/'native-build.json').write_text(json.dumps({'fingerprint':native.fingerprint(),'wheels':wheels}))
    assert native.cached()
    (output/'fixture-2.whl').write_bytes(b'changed without changing file name')
    assert not native.cached()
