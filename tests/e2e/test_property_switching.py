from playwright.sync_api import expect
from .test_editor import upload_track, select, saved


def test_repeated_object_switches_never_duplicate_glow_controls(edge_page, running_app):
    page = edge_page
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    upload_track(page)
    page.get_by_role('button', name='去背景与轨道修正', exact=True).click()
    expect(page.get_by_role('button', name='重新识别', exact=True)).to_be_visible()
    page.get_by_role('button', name='添加轨道', exact=False).click()
    for _ in range(6):
        page.locator('[data-object-id="track"]').click()
        expect(page.get_by_label('发光强度', exact=True)).to_have_count(1)
        page.locator('[data-object-id="track2"]').click()
        expect(page.get_by_label('发光强度', exact=True)).to_have_count(1)
        select(page, '底图')
        expect(page.get_by_label('发光强度', exact=True)).to_have_count(0)
        select(page, '第一行标题')
        expect(page.get_by_label('发光强度', exact=True)).to_have_count(1)
        page.locator('[data-object-id="track"]').click()
        expect(page.get_by_label('发光强度', exact=True)).to_have_count(1)
        expect(page.get_by_role('button', name='基础发光设置', exact=False)).to_have_count(1)
    page.get_by_label('发光强度', exact=True).fill('23')
    select(page, '第一行标题')
    page.get_by_label('发光强度', exact=True).fill('41')
    select(page, '底图')
    expect(page.get_by_label('发光强度', exact=True)).to_have_count(0)
    saved(page)
    value = running_app['client'].get('/api/project').json()['project']
    assert value['trackGlow'] == 23
    assert value['titles'][0]['glow'] == 41
    page.reload()
    page.locator('[data-object-id="track"]').click()
    expect(page.get_by_label('发光强度', exact=True)).to_have_value('23')
    assert not errors
