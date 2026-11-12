import json
from playwright.sync_api import expect
from .test_effects import pixels


def import_music(page):
    page.get_by_role('button',name='从谱面生成',exact=True).click()
    chart={'pathData':'RRRRUULL','settings':{'song':'<color=#ffaa00>曲名 Ice & Fire</color>','artist':'音乐作者 Composer','author':'制谱人 Mapper'}}
    page.get_by_label('谱面文件',exact=True).set_input_files({'name':'song.adofai','mimeType':'application/json','buffer':json.dumps(chart).encode()})
    expect(page.get_by_label('生成音乐名称标题')).to_be_visible()
    return page.frame_locator('iframe[title="轨道选段工具"]')


def preview(page,frame):
    frame.locator('#resolution').select_option('1920')
    frame.get_by_role('button',name='生成并预览',exact=True).click()
    expect(page.get_by_role('img',name='生成轨道预览')).to_be_visible(timeout=20000)


def test_white_metadata_titles_are_opt_in_independent_undoable_and_persistent(edge_page,running_app):
    page=edge_page;client=running_app['client'];before=client.get('/api/project').json()['project']
    frame=import_music(page)
    expect(page.get_by_label('生成音乐名称标题')).not_to_be_checked()
    expect(page.get_by_label('生成音乐作者标题')).not_to_be_checked()
    page.get_by_label('生成音乐名称标题').check();page.get_by_label('生成音乐作者标题').check()
    preview(page,frame)
    assert client.get('/api/project').json()['project']==before
    page.get_by_role('button',name='应用到封面',exact=True).click();pixels(page)
    saved=client.get('/api/project').json()['project']
    assert saved['titles'][:2]==before['titles']
    assert [t['text'] for t in saved['titles'][2:]]==['曲名 Ice & Fire','音乐作者 Composer']
    assert all(t['color']=='#ffffff' and t['glow']==0 for t in saved['titles'][2:])
    page.reload();pixels(page);assert client.get('/api/project').json()['project']==saved
    # New re-edit session does not silently add the same labels again.
    page.locator('[data-object-id="track"]').click()
    page.get_by_label('轨道图形操作',exact=True).click();page.get_by_role('menuitem',name='编辑谱面选段').click()
    expect(page.get_by_label('生成音乐名称标题')).not_to_be_checked()
    page.get_by_label('关闭谱面生成').click()
    # Verify a fresh apply can be undone as one operation after the saved reload.
    page.get_by_label('轨道图形操作',exact=True).click();page.get_by_role('menuitem',name='编辑谱面选段').click()
    page.get_by_label('生成音乐作者标题').check()
    preview(page,page.frame_locator('iframe[title="轨道选段工具"]'))
    page.get_by_role('button',name='应用到封面',exact=True).click();pixels(page)
    page.get_by_role('button',name='撤销',exact=True).click();pixels(page)
    assert client.get('/api/project').json()['project']==saved


def test_capacity_blocks_overwrite_and_cancelling_selected_labels_keeps_project(edge_page,running_app):
    page=edge_page;client=running_app['client']
    for _ in range(3):page.get_by_role('button',name='添加标题',exact=False).click()
    pixels(page);before=client.get('/api/project').json()['project']
    frame=import_music(page);page.get_by_label('生成音乐名称标题').check()
    preview(page,frame)
    expect(page.get_by_role('alert')).to_contain_text('标题名额不足')
    expect(page.get_by_role('button',name='应用到封面',exact=True)).to_be_disabled()
    page.get_by_label('关闭谱面生成').click()
    assert client.get('/api/project').json()['project']==before
    frame=import_music(page);preview(page,frame)
    page.get_by_role('button',name='应用到封面',exact=True).click();pixels(page)
    assert client.get('/api/project').json()['project']['titles']==before['titles']
