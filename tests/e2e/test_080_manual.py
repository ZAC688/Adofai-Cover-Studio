from playwright.sync_api import expect
from .test_effects import pixels


def test_current_information_documents_metadata_icons_and_portable_text_styles(edge_page,running_app):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('说明书不修改当前作品');pixels(page)
    before=running_app['client'].get('/api/project').json()
    page.get_by_role('button',name='信息',exact=True).click()
    dialog=page.get_by_role('dialog',name='关于封面制作器',exact=True)
    expect(dialog.get_by_label('应用版本',exact=True)).to_have_text('0.8.1')
    dialog.get_by_role('tab',name='更新日志',exact=True).click()
    expect(dialog.get_by_role('heading',name='0.8.0',exact=True)).to_be_visible()
    dialog.get_by_role('tab',name='使用说明',exact=True).click()
    text=dialog.get_by_role('tabpanel').inner_text()
    for term in ['生成音乐名称标题','生成音乐作者标题','默认均关闭','名额不足','文字预设','100 MB','文案、位置和对象旋转角度','上传字体','EXE、窗口和任务栏','原有“滤镜预设”']:
        assert term in text,term
    assert running_app['client'].get('/api/project').json()==before
