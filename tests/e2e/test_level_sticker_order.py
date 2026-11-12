from playwright.sync_api import expect
from .test_effects import pixels
from .conftest import ROOT


def test_real_new_level_stickers_p1_to_p20_first_crazy_last_and_selectable(edge_page,running_app):
    page=edge_page;page.get_by_role('button',name='选择贴纸',exact=True).click()
    dialog=page.get_by_role('dialog',name='选择贴纸');dialog.get_by_role('button',name='分类 TUF / 新等级',exact=True).click()
    expected=[f'P{i}' for i in range(1,21)]+[f'G{i}' for i in range(1,21)]+['m21']+[f'U{i}' for i in range(1,21)]+['crazy']
    expect(dialog.locator('[data-preset-id]')).to_have_count(len(expected))
    assert dialog.locator('.sticker-grid span').all_text_contents()==expected
    directory=ROOT/'artifacts/upgrade-06/06-stickers';directory.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(directory/'new-levels.png'))
    for name in ['P10','crazy']:
        if name=='crazy':
            page.get_by_role('button',name='选择贴纸',exact=True).click()
            dialog.get_by_role('button',name='分类 TUF / 新等级',exact=True).click()
            assert dialog.locator('.sticker-grid span').all_text_contents()==expected
        dialog.get_by_role('button',name='选择贴纸 '+name,exact=True).click()
        dialog.get_by_role('button',name='添加贴纸',exact=True).click();expect(dialog).to_have_count(0);pixels(page)
        expect(page.locator('.object-row.selected')).to_contain_text('贴纸 · '+name)
    project=running_app['client'].get('/api/project').json()['project']
    assert sorted(item['name'] for item in project['stickers'].values())==['P10','crazy']
