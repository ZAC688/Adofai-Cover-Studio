import json
import os
from pathlib import Path
import subprocess
import time

import httpx
import pytest

from tests.e2e.conftest import edge_page

ROOT = Path(__file__).resolve().parents[2]
_pointer=ROOT/'artifacts/current-bundle.json'
_default=json.loads(_pointer.read_text(encoding='utf-8-sig'))['directory'] if _pointer.is_file() else str(ROOT/'dist/ADOFAI-Cover-Studio')
BUNDLE=Path(os.environ.get('ADOFAI_TEST_BUNDLE',_default)).resolve()
assert BUNDLE.is_relative_to(ROOT), 'Bundle tests only execute project-owned build outputs'


def clean_environment():
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() not in {'PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'}}
    environment['PATH'] = r'C:\Windows\System32;C:\Windows'
    return environment


def start_binary(bundle, data, ready):
    return subprocess.Popen(
        [str(bundle / 'ADOFAI-Cover-Studio.exe'), '--no-browser', '--data-dir', str(data), '--ready-file', str(ready)],
        cwd=ready.parent, env=clean_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def wait_ready(process, ready, data):
    deadline = time.monotonic() + 45
    while not ready.is_file():
        if process.poll() is not None:
            _output, errors = process.communicate()
            log = data / 'startup-error.log'
            detail = log.read_text(encoding='utf-8') if log.is_file() else errors.decode(errors='replace')
            pytest.fail('Frozen application stopped: ' + detail)
        assert time.monotonic() < deadline, 'Frozen application did not become ready'
        time.sleep(.05)
    state = json.loads(ready.read_text(encoding='utf-8'))
    return f"http://127.0.0.1:{state['port']}"


@pytest.fixture
def running_app(tmp_path):
    assert (BUNDLE / 'ADOFAI-Cover-Studio.exe').is_file(), 'Build the Windows package first'
    data = tmp_path / '打包作品 with spaces'
    ready = tmp_path / 'ready.json'
    process = start_binary(BUNDLE, data, ready)
    address = None
    try:
        address = wait_ready(process, ready, data)
        with httpx.Client(base_url=address, trust_env=False) as client:
            client.headers['x-editor-token'] = client.get('/api/session').json()['token']
            yield {'url': address, 'client': client, 'process': process, 'data': data, 'ready': ready}
    finally:
        if process.poll() is None:
            try:
                if address:
                    with httpx.Client(base_url=address, trust_env=False) as cleanup:
                        token = cleanup.get('/api/session').json()['token']
                        cleanup.post('/api/shutdown', headers={'x-editor-token': token})
                    process.communicate(timeout=15)
                else:
                    process.terminate()
                    process.communicate(timeout=10)
            except (httpx.HTTPError, subprocess.TimeoutExpired):
                process.terminate()
                process.communicate(timeout=10)
