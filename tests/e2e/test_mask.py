import io

from PIL import Image
from playwright.sync_api import expect

from .conftest import ROOT
from .test_editor import saved, select


def recognize(page):
    page.get_by_label("轨道文件", exact=True).set_input_files(str(ROOT / "test-assets/reference/sample-09.png"))
    expect(page.locator(".asset-meta")).to_contain_text("1406 × 1123")
    page.get_by_role("button", name="去背景与轨道修正").click()
    page.get_by_label("自动去除背景", exact=True).check()
    expect(page.get_by_role("button", name="修正轨道", exact=True)).to_be_enabled(timeout=45000)
    saved(page)


def mask_pixel(client, x, y):
    document = client.get("/api/project").json()["project"]
    raw = client.get("/api/assets/" + document["maskAsset"]).content
    return Image.open(io.BytesIO(raw)).convert("L").getpixel((x, y)), document


def paint(page, x, y):
    canvas = page.get_by_label("轨道修正画布", exact=True)
    rect = canvas.bounding_box()
    page.mouse.move(rect["x"] + x / 1406 * rect["width"], rect["y"] + y / 1123 * rect["height"])
    page.mouse.down()
    page.mouse.up()
    expect(page.get_by_role("dialog", name="轨道修正工作区").get_by_role("status")).to_have_text("修正已保存", timeout=20000)


def test_erase_restore_undo_redo_and_refresh_use_original_coordinates(edge_page, running_app):
    page, client = edge_page, running_app["client"]
    recognize(page)
    initial, before = mask_pixel(client, 1000, 320)
    assert initial > 200
    page.get_by_role("button", name="修正轨道", exact=True).click()
    expect(page.get_by_role("dialog", name="轨道修正工作区").get_by_role("status")).to_have_text("修正已保存")
    page.get_by_role("button", name="擦除画笔", exact=True).click()
    paint(page, 1000, 320)
    saved(page)
    erased, after_erase = mask_pixel(client, 1000, 320)
    assert erased == 0
    assert after_erase["baseMaskAsset"] == before["baseMaskAsset"]
    page.get_by_role("button", name="保留画笔", exact=True).click()
    paint(page, 1000, 320)
    saved(page)
    assert mask_pixel(client, 1000, 320)[0] == 255
    page.get_by_role("button", name="撤销画笔", exact=True).click()
    saved(page)
    assert mask_pixel(client, 1000, 320)[0] == 0
    page.get_by_role("button", name="重做画笔", exact=True).click()
    saved(page)
    assert mask_pixel(client, 1000, 320)[0] == 255
    page.get_by_role("button", name="返回构图", exact=True).click()
    saved(page)
    page.reload()
    select(page, "轨道图形")
    page.get_by_role("button", name="去背景与轨道修正").click()
    expect(page.get_by_label("自动去除背景", exact=True)).to_be_checked()
    assert mask_pixel(client, 1000, 320)[0] == 255


def test_rerecognition_confirmation_and_cancel_preserve_valid_result(edge_page, running_app):
    page, client = edge_page, running_app["client"]
    recognize(page)
    before = client.get("/api/project").json()["project"]
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="重新识别", exact=True).click()
    assert client.get("/api/project").json()["project"] == before
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="重新识别", exact=True).click()
    page.get_by_role("button", name="取消识别", exact=True).click()
    expect(page.get_by_role("button", name="修正轨道", exact=True)).to_be_enabled()
    assert client.get("/api/project").json()["project"]["maskAsset"] == before["maskAsset"]
    page.get_by_label("自动去除背景", exact=True).uncheck()
    saved(page)
    assert client.get("/api/project").json()["project"]["maskAsset"] == before["maskAsset"]
    page.get_by_label("自动去除背景", exact=True).check()
    saved(page)
    assert client.get("/api/project").json()["project"]["removeBackground"]
