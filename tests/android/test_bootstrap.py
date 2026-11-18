import hashlib
import stat
import zipfile

import pytest

from tools.bootstrap_android import safe_extract, verify


def test_corrupt_download_is_rejected(tmp_path):
    archive = tmp_path / 'download.zip'
    archive.write_bytes(b'incomplete or substituted download')
    with pytest.raises(ValueError, match='SHA-256'):
        verify(archive, hashlib.sha256(b'official bytes').hexdigest())
    verify(archive, hashlib.sha256(archive.read_bytes()).hexdigest())


@pytest.mark.parametrize('entry', ['../outside.txt', '/outside.txt', r'..\outside.txt', 'C:/outside.txt'])
def test_zip_cannot_escape_installation_directory(tmp_path, entry):
    archive = tmp_path / 'download.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr(entry, 'unexpected')
    with pytest.raises(ValueError, match='unsafe path'):
        safe_extract(archive, tmp_path / 'install')
    assert not (tmp_path / 'outside.txt').exists()


def test_symbolic_link_archive_is_rejected_before_writing(tmp_path):
    archive = tmp_path / 'download.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        link = zipfile.ZipInfo('tool/link')
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr('tool/safe.txt', 'safe')
        bundle.writestr(link, '../../outside')
    with pytest.raises(ValueError, match='symbolic link'):
        safe_extract(archive, tmp_path / 'install')
    assert not (tmp_path / 'install/tool/safe.txt').exists()


def test_valid_tool_archive_keeps_expected_bytes(tmp_path):
    archive = tmp_path / 'download.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        bundle.writestr('tool/bin/run.bat', b'@echo off\r\n')
    safe_extract(archive, tmp_path / 'install')
    assert (tmp_path / 'install/tool/bin/run.bat').read_bytes() == b'@echo off\r\n'
