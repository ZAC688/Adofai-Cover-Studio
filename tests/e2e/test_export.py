import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import expect

from .test_editor import saved, select, upload_track


def export(page, path, name="测试封面"):
    page.get_by_role("button", name="导出图片", exact=False).click()
    dialog = page.get_by_role("dialog", name="导出图片")
    expect(dialog.get_by_role("button", name="导出到电脑")).to_be_enabled()
    dialog.get_by_label("导出文件名").fill(name)
    with page.expect_download() as result:
        dialog.get_by_role("button", name="导出到电脑").click()
    download = result.value
    download.save_as(str(path))
    dialog.get_by_role("button", name="关闭导出").click()
    return download.suggested_filename


def test_png_matches_content_canvas_and_has_exact_ratio_dimensions(edge_page, tmp_path):
    page = edge_page
    upload_track(page)
    select(page, "第一行标题")
    page.get_by_label("标题内容", exact=True).fill("导出检验 ADOFAI")
    page.get_by_label("发光强度", exact=True).fill("65")
    page.locator(".panel-heading").first.click()
    saved(page)
    for ratio, size in [("16:9", (1920, 1080)), ("4:3", (1440, 1080))]:
        page.get_by_role("button", name=ratio, exact=True).click()
        saved(page)
        canvas_png = page.get_by_label("封面画布", exact=True).evaluate("canvas => canvas.toDataURL('image/png').split(',')[1]")
        filename = export(page, tmp_path / f"{size[0]}.png", "my:cover?")
        assert filename == "my_cover_.png"
        with Image.open(tmp_path / f"{size[0]}.png") as actual:
            assert actual.format == "PNG"
            assert actual.size == size
            reference = Image.open(io.BytesIO(base64.b64decode(canvas_png)))
            np.testing.assert_array_equal(np.array(actual), np.array(reference))


def test_glow_changes_exported_pixels_and_cancel_preserves_project(edge_page, running_app, tmp_path):
    page = edge_page
    page.get_by_label("标题内容", exact=True).fill("GLOW 光效")
    page.get_by_label("发光强度", exact=True).fill("0")
    page.locator(".panel-heading").first.click()
    saved(page)
    export(page, tmp_path / "no-glow.png")
    page.get_by_label("发光强度", exact=True).fill("85")
    page.locator(".panel-heading").first.click()
    saved(page)
    export(page, tmp_path / "glow.png")
    first, second = np.array(Image.open(tmp_path / "no-glow.png")), np.array(Image.open(tmp_path / "glow.png"))
    assert np.count_nonzero(np.any(first != second, axis=2)) > 500
    before = running_app["client"].get("/api/project").json()
    page.get_by_role("button", name="导出图片", exact=False).click()
    page.get_by_role("button", name="返回编辑", exact=True).click()
    assert running_app["client"].get("/api/project").json() == before
