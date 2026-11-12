from playwright.sync_api import expect
from .test_filters import fixture_track,panel,add_filter
from .test_effects import pixels


def test_practical_and_fine_ranges_keep_full_numeric_values_and_history(edge_page,running_app,tmp_path):
    page=edge_page;fixture_track(page,tmp_path);panel(page);entry=add_filter(page,'AdjustmentFilter')
    slider=entry.get_by_label('亮度滑块',exact=True)
    expect(slider).to_have_attribute('min','0');expect(slider).to_have_attribute('max','5')
    slider.focus();slider.press('ArrowRight');expect(entry.get_by_label('亮度',exact=True)).to_have_value('1.01')
    entry.get_by_role('button',name='精细调节 亮度',exact=True).click()
    expect(slider).to_have_attribute('step','0.001')
    slider.focus();slider.press('ArrowRight');expect(entry.get_by_label('亮度',exact=True)).to_have_value('1.011')
    page.locator('.panel-heading').first.click();pixels(page)
    page.get_by_role('button',name='撤销',exact=True).click();expect(entry.get_by_label('亮度',exact=True)).to_have_value('1.01')
    # Numeric inputs retain values outside the common slider range, including after reload.
    entry.get_by_label('亮度',exact=True).fill('8.75');page.locator('.panel-heading').first.click();pixels(page)
    assert running_app['client'].get('/api/project').json()['project']['filters'][0]['params']['brightness']==8.75
    page.reload();page.locator('[data-object-id="track"]').click();panel(page)
    page.locator('.filter-entry summary').click()  # Existing filters now enter collapsed.
    expect(page.get_by_label('亮度',exact=True)).to_have_value('8.75')
    page.get_by_role('button',name='精细调节 亮度',exact=True).click()
    assert float(page.get_by_label('亮度滑块',exact=True).get_attribute('min'))<8.75<float(page.get_by_label('亮度滑块',exact=True).get_attribute('max'))
    page.get_by_role('button',name='恢复默认参数',exact=True).click();expect(page.get_by_label('亮度',exact=True)).to_have_value('1')
