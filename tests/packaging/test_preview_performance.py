from playwright.sync_api import sync_playwright,expect
from tests.e2e.test_preview_performance import exercise_preview,start_visible_preview
from tests.e2e.test_desktop_runtime import stop_desktop
from .conftest import BUNDLE


def test_frozen_heavy_light_edits_are_fast_cached_and_export_exactly(tmp_path,monkeypatch):
    monkeypatch.setenv('PREVIEW_PHASE','frozen')
    host=start_visible_preview(tmp_path,binary=BUNDLE/'ADOFAI-Cover-Studio.exe')
    try:
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{host["debug"]}',no_defaults=True)
            page=browser.contexts[0].pages[0]
            page.set_viewport_size({'width':1440,'height':1000})
            page.wait_for_url(host['url']+'/',timeout=30000)
            expect(page.get_by_label('标题内容',exact=True)).to_be_visible(timeout=30000)
            exercise_preview(page,host)
    finally:stop_desktop(host)
