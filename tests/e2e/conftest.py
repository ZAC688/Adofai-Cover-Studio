import json
from pathlib import Path
import subprocess
import sys
import time

import httpx
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def running_app(tmp_path):
    ready = tmp_path / "ready.json"
    data = tmp_path / "作品数据 with spaces"
    process = subprocess.Popen(
        [sys.executable, "-m", "backend.launcher", "--data-dir", str(data),
         "--ready-file", str(ready), "--no-browser"], cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    deadline = time.monotonic() + 25
    try:
        while not ready.is_file():
            if process.poll() is not None:
                _out, err = process.communicate()
                pytest.fail(f"Launcher stopped: {err.decode(errors='replace')}")
            if time.monotonic() > deadline:
                pytest.fail("Launcher did not become ready")
            time.sleep(.05)
        state = json.loads(ready.read_text(encoding="utf-8"))
        address = f"http://127.0.0.1:{state['port']}"
        with httpx.Client(base_url=address, trust_env=False) as client:
            client.headers["x-editor-token"] = client.get("/api/session").json()["token"]
            yield {"url": address, "client": client, "process": process, "data": data, "ready": ready}
    finally:
        if process.poll() is None:
            try:
                with httpx.Client(base_url=address, trust_env=False) as cleanup:
                    token = cleanup.get("/api/session").json()["token"]
                    cleanup.post("/api/shutdown", headers={"x-editor-token": token})
                process.communicate(timeout=15)
            except (httpx.HTTPError, subprocess.TimeoutExpired):
                process.terminate()
                process.communicate(timeout=10)


@pytest.fixture
def edge_page(running_app):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
        external = []
        def route_request(route):
            url = route.request.url
            if url.startswith(running_app["url"] + "/") or url.startswith(("blob:", "data:")):
                route.continue_()
            else:
                external.append(url)
                route.abort()
        context.route("**/*", route_request)
        page = context.new_page()
        page.goto(running_app["url"])
        yield page
        assert external == [], f"Unexpected external requests: {external}"
        context.close()
        browser.close()
