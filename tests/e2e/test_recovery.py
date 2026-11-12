import json
from pathlib import Path
import subprocess
import sys
import time

import httpx
from playwright.sync_api import expect, sync_playwright

from .conftest import ROOT
from .test_editor import saved, select
from .test_mask import recognize, mask_pixel


def test_failed_save_retains_editor_content_and_retries(edge_page, running_app):
    page = edge_page
    expect(page.locator(".save-state")).to_have_text("已保存到本机")
    def fail_writes(route):
        if route.request.method == "PUT":
            route.fulfill(status=503, content_type="application/json", body=json.dumps({"detail": "模拟磁盘写入失败"}))
        else:
            route.continue_()
    page.route("**/api/project", fail_writes)
    page.get_by_label("标题内容", exact=True).fill("保存失败也不能丢失这段文字")
    page.locator(".panel-heading").first.click()
    expect(page.locator(".save-state")).to_contain_text("模拟磁盘写入失败")
    expect(page.get_by_label("标题内容", exact=True)).to_have_value("保存失败也不能丢失这段文字")
    assert running_app["client"].get("/api/project").json()["project"]["titles"][0]["text"] == ""
    page.unroute("**/api/project", fail_writes)
    page.get_by_role("button", name="重试保存", exact=True).click()
    saved(page)
    assert running_app["client"].get("/api/project").json()["project"]["titles"][0]["text"] == "保存失败也不能丢失这段文字"


def test_mask_write_failure_keeps_draft_until_retry(edge_page, running_app):
    page, client = edge_page, running_app["client"]
    recognize(page)
    before_value, before = mask_pixel(client, 1000, 320)
    page.get_by_role("button", name="修正轨道", exact=True).click()
    dialog = page.get_by_role("dialog", name="轨道修正工作区")
    expect(dialog.get_by_role("status")).to_have_text("修正已保存")
    def fail_mask(route):
        route.fulfill(status=503, content_type="application/json", body='{"detail":"simulated mask write failure"}')
    page.route("**/api/masks/*", fail_mask)
    canvas = page.get_by_label("轨道修正画布")
    rect = canvas.bounding_box()
    page.mouse.click(rect["x"] + 1000 / 1406 * rect["width"], rect["y"] + 320 / 1123 * rect["height"])
    expect(dialog.get_by_role("status")).to_have_text("修正保存失败，请重试")
    expect(dialog.get_by_role("button", name="返回构图", exact=True)).to_be_disabled()
    assert mask_pixel(client, 1000, 320)[0] == before_value
    assert mask_pixel(client, 1000, 320)[1]["maskAsset"] == before["maskAsset"]
    page.unroute("**/api/masks/*", fail_mask)
    dialog.get_by_role("button", name="重试保存修正", exact=True).click()
    expect(dialog.get_by_role("status")).to_have_text("修正已保存")
    saved(page)
    assert mask_pixel(client, 1000, 320)[0] == 0


def test_zoom_and_pan_do_not_change_mask_coordinate_system_or_composition(edge_page, running_app):
    page, client = edge_page, running_app["client"]
    recognize(page)
    before = client.get("/api/project").json()["project"]
    assert mask_pixel(client, 880, 540)[0] > 200
    page.get_by_role("button", name="修正轨道", exact=True).click()
    dialog = page.get_by_role("dialog", name="轨道修正工作区")
    expect(dialog.get_by_role("status")).to_have_text("修正已保存")
    page.get_by_label("修正缩放").press("End")
    canvas = page.get_by_label("轨道修正画布")
    rect = canvas.bounding_box()
    page.mouse.click(rect["x"] + 880 / 1406 * rect["width"], rect["y"] + 540 / 1123 * rect["height"])
    expect(dialog.get_by_role("status")).to_have_text("修正已保存")
    saved(page)
    assert mask_pixel(client, 880, 540)[0] == 0
    page.get_by_role("button", name="平移", exact=True).click()
    page.mouse.move(720, 500)
    page.mouse.down()
    page.mouse.move(770, 535, steps=3)
    page.mouse.up()
    page.get_by_role("button", name="返回构图", exact=True).click()
    saved(page)
    after = client.get("/api/project").json()["project"]
    assert after["layouts"] == before["layouts"]


def test_actual_browser_close_reopen_and_service_restart_restore_work(running_app, tmp_path):
    address = running_app["url"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(address)
        page.get_by_label("标题内容", exact=True).fill("关闭浏览器后继续")
        recognize(page)
        page.get_by_role("button", name="4:3", exact=True).click()
        saved(page)
        before = running_app["client"].get("/api/project").json()["project"]
        browser.close()
        reopened = playwright.chromium.launch(channel="msedge", headless=True)
        again = reopened.new_page()
        again.goto(address)
        expect(again.get_by_label("标题内容", exact=True)).to_have_value("关闭浏览器后继续")
        saved(again)
        reopened.close()
    running_app["client"].post("/api/shutdown")
    running_app["process"].communicate(timeout=15)
    ready = tmp_path / "restart-ready.json"
    process = subprocess.Popen(
        [sys.executable, "-m", "backend.launcher", "--no-browser", "--data-dir", str(running_app["data"]), "--ready-file", str(ready)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 20
        while not ready.is_file():
            assert process.poll() is None, "Restarted service exited"
            assert time.monotonic() < deadline, "Restarted service did not become ready"
            time.sleep(.05)
        state = json.loads(ready.read_text(encoding="utf-8"))
        with httpx.Client(base_url=f"http://127.0.0.1:{state['port']}", trust_env=False) as client:
            restored = client.get("/api/project").json()
            assert restored["project"] == before
            assert len(restored["assets"]) >= 2
            for asset in restored["assets"]:
                assert client.get("/api/assets/" + asset).status_code == 200
            client.headers["x-editor-token"] = client.get("/api/session").json()["token"]
            client.post("/api/shutdown")
            process.communicate(timeout=15)
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=10)
