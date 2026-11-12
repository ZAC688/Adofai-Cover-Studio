import re

from playwright.sync_api import expect

from .conftest import ROOT


def select(page, name):
    page.locator(".object-row").filter(has_text=name).click()


def saved(page):
    expect(page.locator(".save-state")).to_have_text("已保存到本机", timeout=15000)


def upload_track(page):
    page.get_by_label("轨道文件", exact=True).set_input_files(str(ROOT / "test-assets/reference/transparent-fixture.png"))
    expect(page.locator(".asset-meta")).to_contain_text("1406 × 1123")
    saved(page)


def test_titles_independent_undo_and_refresh(edge_page, running_app):
    page = edge_page
    expect(page.locator(".save-state")).to_have_text("已保存到本机")
    page.get_by_label("标题内容", exact=True).fill("中文主标题 ADOFAI")
    page.get_by_label("字号", exact=True).fill("96")
    page.get_by_label("发光强度", exact=True).fill("0")
    select(page, "第二行标题")
    page.get_by_label("标题内容", exact=True).fill("作者 / 20.5 难度")
    page.get_by_label("字号", exact=True).fill("48")
    select(page, "第一行标题")
    expect(page.get_by_label("标题内容", exact=True)).to_have_value("中文主标题 ADOFAI")
    expect(page.get_by_label("字号", exact=True)).to_have_value("96")
    expect(page.get_by_label("发光强度", exact=True)).to_have_value("0")
    page.get_by_label("水平位置", exact=True).fill("300")
    page.locator(".panel-heading").first.click()
    page.get_by_role("button", name="撤销", exact=True).click()
    expect(page.get_by_label("水平位置", exact=True)).to_have_value("160")
    page.get_by_role("button", name="重做", exact=True).click()
    expect(page.get_by_label("水平位置", exact=True)).to_have_value("300")
    saved(page)
    page.reload()
    expect(page.get_by_label("标题内容", exact=True)).to_have_value("中文主标题 ADOFAI")
    document = running_app["client"].get("/api/project").json()["project"]
    assert document["titles"][1]["text"] == "作者 / 20.5 难度"
    assert document["titles"][1]["glow"] == 0  # New works now start without glow.


def test_track_drag_and_ratio_layout_memory(edge_page, running_app):
    page = edge_page
    upload_track(page)
    before = float(page.get_by_label("水平位置", exact=True).input_value())
    box = page.get_by_label("封面画布").bounding_box()
    # Drag a visible track pixel; the image center is transparent padding.
    placement=running_app['client'].get('/api/project').json()['project']['layouts']['16:9']['track']
    logical_x=placement['x']+(1000-1406/2)*placement['scale']
    logical_y=placement['y']+(320-1123/2)*placement['scale']
    x,y=box['x']+logical_x/1920*box['width'],box['y']+logical_y/1080*box['height']
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 40, y + 15, steps=4)
    page.mouse.up()
    moved = float(page.get_by_label("水平位置", exact=True).input_value())
    assert moved > before
    page.get_by_role("button", name="4:3", exact=True).click()
    page.get_by_label("水平位置", exact=True).fill("500")
    page.locator(".panel-heading").first.click()
    page.get_by_role("button", name="16:9", exact=True).click()
    expect(page.get_by_label("水平位置", exact=True)).to_have_value(str(round(moved, 2)).rstrip('0').rstrip('.') if moved % 1 else str(int(moved)))
    page.get_by_role("button", name="4:3", exact=True).click()
    expect(page.get_by_label("水平位置", exact=True)).to_have_value("500")
    saved(page)
    page.reload()
    page.locator(".object-row").filter(has_text="轨道图形").click()
    expect(page.get_by_label("水平位置", exact=True)).to_have_value("500")
    expect(page.get_by_role("button", name="4:3", exact=True)).to_have_attribute("aria-pressed", "true")


def test_oversized_replacement_keeps_existing_track(edge_page, running_app):
    page = edge_page
    upload_track(page)
    previous = running_app["client"].get("/api/project").json()["project"]["trackAsset"]
    page.get_by_label("轨道文件", exact=True).set_input_files({"name": "too-large.png", "mimeType": "image/png", "buffer": bytes(10_000_001)})
    expect(page.get_by_role("alert")).to_contain_text("图片不能超过 10 MB")
    assert running_app["client"].get("/api/project").json()["project"]["trackAsset"] == previous


def test_canvas_selection_and_background_cover(edge_page):
    page = edge_page
    page.get_by_label("底图文件", exact=True).set_input_files(str(ROOT / "test-assets/reference/sample-08.png"))
    expect(page.locator(".asset-meta")).to_contain_text("1381 × 1354")
    page.get_by_role("button", name="铺满画布", exact=True).click()
    expect(page.get_by_label("水平位置", exact=True)).to_have_value("960")
    select(page, "第一行标题")
    page.get_by_label("标题内容", exact=True).fill("点击选中")
    select(page, "底图")
    canvas = page.get_by_label("封面画布")
    box = canvas.bounding_box()
    page.mouse.click(box["x"] + 220 / 1920 * box["width"], box["y"] + 430 / 1080 * box["height"])
    expect(page.locator(".object-row.selected")).to_contain_text("第一行标题")
    expect(page.get_by_label("标题内容", exact=True)).to_have_value("点击选中")
    saved(page)
    directory = ROOT / "artifacts/p2"
    directory.mkdir(exist_ok=True)
    page.screenshot(path=str(directory / "editor.png"))
