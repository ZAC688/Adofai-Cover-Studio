from playwright.sync_api import expect


def test_exit_flushes_pending_edits_and_stops_local_service(edge_page, running_app):
    page = edge_page
    page.get_by_label('标题内容', exact=True).fill('退出前必须保存')
    page.get_by_role('button', name='退出程序', exact=True).click()
    expect(page.get_by_text('作品已保存，本地程序已退出。再次双击启动程序即可继续。')).to_be_visible()
    running_app['process'].communicate(timeout=15)
    from backend.app.storage import Store
    assert Store(running_app['data']).load()['project']['titles'][0]['text'] == '退出前必须保存'
