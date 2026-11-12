import numpy as np
from playwright.sync_api import expect
from .test_filters import fixture_track,panel,add_filter
from .test_effects import pixels
from .test_objects import row


def test_reenter_and_switch_object_default_fold_without_changing_effects(edge_page,running_app,tmp_path):
    page=edge_page;fixture_track(page,tmp_path);panel(page)
    first=add_filter(page,'AdjustmentFilter');first.get_by_label('亮度',exact=True).fill('.4')
    add_filter(page,'GrayscaleFilter');expected=pixels(page)
    before=running_app['client'].get('/api/project').json()
    page.get_by_role('button',name='对象属性',exact=True).click();panel(page)
    entries=page.locator('.filter-entry');expect(entries).to_have_count(2)
    assert entries.evaluate_all('entries=>entries.every(e=>!e.open)')
    np.testing.assert_array_equal(pixels(page),expected)
    assert running_app['client'].get('/api/project').json()==before
    entries.first.locator('summary').click();expect(entries.first.get_by_label('亮度',exact=True)).to_be_visible()
    assert not entries.last.evaluate('e=>e.open')
    row(page,'title1').click();add_filter(page,'EmbossFilter');pixels(page)
    row(page,'track').click();expect(entries).to_have_count(2)
    assert entries.evaluate_all('entries=>entries.every(e=>!e.open)')
    row(page,'title1').click();expect(entries).to_have_count(1);assert not entries.first.evaluate('e=>e.open')
    page.reload();panel(page);expect(entries).to_have_count(1);assert not entries.first.evaluate('e=>e.open')
