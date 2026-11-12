import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def source_server(tmp_path):
    ready = tmp_path / "本地验证 ready.json"
    command = [sys.executable, "-m", "experiments.p0", "--serve", "--output",
               str(ROOT / "artifacts/p0/reference"), "--ready-file", str(ready)]
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 20
    try:
        while not ready.is_file():
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(f"Server stopped: {stdout!r} {stderr!r}")
            if time.monotonic() > deadline:
                pytest.fail("Local server never became ready")
            time.sleep(.05)
        yield process, json.loads(ready.read_text(encoding="utf-8")), command
    finally:
        process.terminate()
        process.communicate(timeout=10)


def test_repeated_start_reuses_loopback_service(source_server):
    process, ready, command = source_server
    duplicate = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    assert duplicate.returncode == 0, duplicate.stderr.decode(errors="replace")
    assert process.poll() is None
    with urlopen(f"http://127.0.0.1:{ready['port']}/health") as response:
        assert json.load(response)["application"] == "adofai-p0"


def test_occupied_explicit_port_reports_error_without_killing_owner(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        command = [sys.executable, "-m", "experiments.p0", "--serve", "--output", str(tmp_path),
                   "--port", str(port)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode != 0
        assert occupied.getsockname()[1] == port


def test_edge_renders_local_comparison_with_external_requests_blocked(source_server):
    _process, ready, _command = source_server
    external_requests = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 768})

        def route_request(route):
            if route.request.url.startswith(f"http://127.0.0.1:{ready['port']}/"):
                route.continue_()
            else:
                external_requests.append(route.request.url)
                route.abort()

        context.route("**/*", route_request)
        page = context.new_page()
        page.goto(f"http://127.0.0.1:{ready['port']}/")
        assert page.title() == "ADOFAI P0 离线识别验证"
        page.locator("img").evaluate("img => img.decode()")
        assert page.locator("img").evaluate("img => img.naturalWidth") == 1200
        assert page.get_by_role("link", name="查看模型候选").count() == 1
        page.screenshot(path=str(ROOT / "artifacts/p0/edge-preview.png"))
        assert external_requests == []
        browser.close()
