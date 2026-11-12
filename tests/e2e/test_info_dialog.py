import json
from playwright.sync_api import expect
from .conftest import ROOT
from .test_effects import pixels


def test_information_author_version_changelog_and_manual_are_offline_and_preserve_work(edge_page,running_app):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('查看信息不改变作品');pixels(page)
    before=running_app['client'].get('/api/project').json()
    button=page.get_by_role('button',name='信息',exact=True);button.click()
    dialog=page.get_by_role('dialog',name='关于封面制作器',exact=True)
    expect(dialog.get_by_text('ZAC688',exact=True)).to_be_visible()
    version=json.loads((ROOT/'frontend/package.json').read_text(encoding='utf-8'))['version']
    expect(dialog.get_by_label('应用版本',exact=True)).to_have_text(version)
    dialog.get_by_role('tab',name='更新日志',exact=True).click()
    expect(dialog.get_by_role('heading',name='0.6.0',exact=True)).to_be_visible()
    expect(dialog.get_by_text('滤镜预设可在本机保存、导出和导入，包含局部范围及贴图。',exact=True)).to_be_visible()
    dialog.get_by_role('tab',name='使用说明',exact=True).click()
    expect(dialog.get_by_text('PNG',exact=False).first).to_be_attached()
    text=dialog.get_by_role('tabpanel').inner_text()
    for term in ['上传底图','Delete','滤镜预设','3D 文字','退出程序']:assert term in text
    page.keyboard.press('Delete');page.keyboard.press('Control+z')
    assert running_app['client'].get('/api/project').json()==before
    page.keyboard.press('Escape');expect(dialog).to_have_count(0);expect(button).to_be_focused()
    button.click();expect(dialog.get_by_role('button',name='关闭信息')).to_be_focused()
    page.keyboard.press('Shift+Tab');expect(dialog.get_by_role('tabpanel')).to_be_focused()
    page.keyboard.press('Tab');expect(dialog.get_by_role('button',name='关闭信息')).to_be_focused()
    dialog.get_by_role('button',name='关闭信息').click();expect(button).to_be_focused()
    expect(page.get_by_label('标题内容',exact=True)).to_have_value('查看信息不改变作品')
    page.reload();page.get_by_role('button',name='信息',exact=True).click();expect(dialog.get_by_label('应用版本')).to_have_text(version)
    directory=ROOT/'artifacts/upgrade-06/05-info';directory.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(directory/'about.png'))
