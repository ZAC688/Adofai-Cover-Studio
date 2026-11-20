import io
from pathlib import Path
import struct
import zipfile

import pytest

from tools.check_android_pages import audit, inspect_elf


def elf(alignment=16384, address=16384, relro_end=None, load_end=32768):
    headers = [(1, 6, 0, address, address, 4096, load_end - address, alignment)]
    if relro_end is not None:
        headers.append((0x6474e552, 4, 0, address, address, 100, relro_end - address, 1))
    data = bytearray(4096)
    data[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', data, 18, 183)
    struct.pack_into('<Q', data, 32, 64)
    struct.pack_into('<HH', data, 54, 56, len(headers))
    for index, header in enumerate(headers):
        struct.pack_into('<IIQQQQQQ', data, 64 + index * 56, *header)
    return bytes(data)


def test_rejects_4k_even_with_other_segments_aligned():
    assert 'LOAD alignment 4096' in inspect_elf(elf(4096), 'fixture')['issues']


def test_rejects_merely_changing_the_alignment_field():
    assert 'LOAD offset/address not congruent at 16KB' in inspect_elf(elf(address=4096), 'fixture')['issues']


def test_rejects_relro_which_protects_following_writable_data():
    assert 'writable data shares the trailing RELRO page' in inspect_elf(elf(relro_end=20480), 'fixture')['issues']


@pytest.mark.parametrize('options', [{}, {'alignment': 65536}, {'relro_end': 32768}, {'relro_end': 20480, 'load_end': 20480}])
def test_valid_load_and_relro_layouts(options):
    assert inspect_elf(elf(**options), 'fixture')['issues'] == []


def test_scans_hidden_transitive_libraries_inside_imy_and_versioned_sonames(tmp_path):
    nested = io.BytesIO()
    with zipfile.ZipFile(nested, 'w') as bundle:
        bundle.writestr('package/library.so.3', elf(4096))
    path = tmp_path/'fixture.apk'
    with zipfile.ZipFile(path, 'w') as bundle:
        bundle.writestr('lib/arm64-v8a/valid.so', elf())
        bundle.writestr('assets/requirements-arm64-v8a.imy', nested.getvalue())
    result = audit(path)
    assert not result['passed']
    assert result['counts'] == {'arm64-v8a': 2}
    assert result['libraries'][1]['path'].endswith('.imy!package/library.so.3')


def test_empty_scan_is_not_a_pass(tmp_path):
    path = tmp_path/'empty.apk'
    with zipfile.ZipFile(path, 'w') as bundle:
        bundle.writestr('readme.txt', 'no native code')
    with pytest.raises(ValueError, match='No ELF'):
        audit(path)


@pytest.mark.parametrize('data', [b'', b'\x7fELF', elf()[:90]])
def test_rejects_malformed_elf(data):
    with pytest.raises(ValueError):
        inspect_elf(data, 'broken.so')
