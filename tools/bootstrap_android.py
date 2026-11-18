"""Install pinned official Android build tools into ignored workspace folders."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    'android': ('https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip',
                '90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a'),
    'gradle': ('https://downloads.gradle.org/distributions/gradle-8.11.1-bin.zip',
               'f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6'),
}


def verify(path: Path, expected: str) -> None:
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else None
        if digest is None:
            digest_object = hashlib.sha256()
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest_object.update(block)
            digest = digest_object.hexdigest()
    if digest != expected:
        raise ValueError(f'Official SHA-256 does not match: {path.name}')


def safe_extract(archive: Path, destination: Path) -> None:
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            relative = PurePosixPath(member.filename.replace('\\', '/'))
            target = destination.joinpath(*relative.parts).resolve()
            if relative.is_absolute() or ':' in member.filename or not target.is_relative_to(destination):
                raise ValueError('Archive contains an unsafe path')
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError('Archive contains a symbolic link')
        bundle.extractall(destination)


def download(name: str, opener) -> Path:
    url, expected = TOOLS[name]
    directory = ROOT / 'tools/android-downloads'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / url.rsplit('/', 1)[1]
    if target.exists():
        verify(target, expected)
        print(f'{name}: cached checksum verified', flush=True)
        return target
    temporary = target.with_suffix('.part')
    try:
        with opener.open(url, timeout=60) as response, temporary.open('wb') as stream:
            count, last = 0, time.monotonic()
            while block := response.read(1024 * 1024):
                stream.write(block)
                count += len(block)
                if time.monotonic() - last >= 10:
                    print(f'{name}: {count // 1048576} MiB received', flush=True)
                    last = time.monotonic()
        verify(temporary, expected)
        temporary.replace(target)
        print(f'{name}: official checksum verified', flush=True)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def install(name: str, archive: Path) -> None:
    tools = ROOT / 'tools'
    target = tools / ('android-sdk/cmdline-tools/latest' if name == 'android' else 'gradle-8.11.1')
    executable = target / ('bin/sdkmanager.bat' if name == 'android' else 'bin/gradle.bat')
    if executable.is_file():
        print(f'{name}: installed', flush=True)
        return
    with tempfile.TemporaryDirectory(prefix='android-bootstrap-', dir=tools / 'android-downloads') as temporary:
        safe_extract(archive, Path(temporary))
        source = Path(temporary) / ('cmdline-tools' if name == 'android' else 'gradle-8.11.1')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), target)
    if not executable.is_file():
        raise RuntimeError(f'Build tool entry point missing: {name}')
    print(f'{name}: installed', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy', help='Proxy for this download only; no system settings are changed')
    args = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(
        {'http': args.proxy, 'https': args.proxy}) if args.proxy else urllib.request.ProxyHandler())
    with ThreadPoolExecutor(max_workers=2) as pool:
        archives = dict(zip(TOOLS, pool.map(lambda name: download(name, opener), TOOLS)))
    for name, archive in archives.items():
        install(name, archive)


if __name__ == '__main__':
    main()
