from playwright.sync_api import expect
from .test_effects import pixels


def test_desktop_version_and_track_instructions_are_available_offline(edge_page,running_app):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('阅读新说明不修改作品');pixels(page)
    before=running_app['client'].get('/api/project').json()
    page.get_by_role('button',name='信息',exact=True).click()
    dialog=page.get_by_role('dialog',name='关于封面制作器',exact=True)
    expect(dialog.get_by_label('应用版本',exact=True)).to_have_text('0.8.1')
    expect(dialog.get_by_text('Windows · 独立桌面 · 完全离线',exact=True)).to_be_visible()
    dialog.get_by_role('tab',name='更新日志',exact=True).click()
    expect(dialog.get_by_role('heading',name='0.7.0',exact=True)).to_be_visible()
    dialog.get_by_role('tab',name='使用说明',exact=True).click()
    text=dialog.get_by_role('tabpanel').inner_text()
    for term in ['无需安装浏览器','Windows 10','金黄色石砖','从谱面生成','生成并预览','编辑谱面选段','导出轨道 PNG','保存失败','20000','PositionTrack']:
        assert term in text,term
    assert '下载保存位置由 Edge' not in text
    assert running_app['client'].get('/api/project').json()==before
