import pytest
from playwright.sync_api import expect
from .test_editor import saved
from .test_effects import pixels
from .test_objects import row
from .test_stickers import choose


@pytest.mark.parametrize('kind',['title1','track','sticker'])
def test_delete_removes_selected_object_undo_restores_and_reload_persists(edge_page,running_app,kind):
    page=edge_page;pixels(page)
    if kind=='sticker':
        item=next(item for item in running_app['client'].get('/api/stickers').json() if item['frames']==1);choose(page,item)
        id=page.locator('.object-row.selected').get_attribute('data-object-id')
    else:id=kind;row(page,id).click()
    pixels(page);before=running_app['client'].get('/api/project').json()['project']
    row(page,id).focus();page.keyboard.press('Delete');expect(row(page,id)).to_have_count(0);saved(page)
    page.get_by_role('button',name='撤销',exact=True).click();expect(row(page,id)).to_have_count(1);pixels(page)
    assert running_app['client'].get('/api/project').json()['project']==before
    row(page,id).focus();page.evaluate("window.dispatchEvent(new KeyboardEvent('keydown',{key:'Delete',repeat:true,bubbles:true}))")
    expect(row(page,id)).to_have_count(1)
    page.keyboard.press('Delete');expect(row(page,id)).to_have_count(0);saved(page)
    page.reload();expect(row(page,id)).to_have_count(0)


def test_delete_edits_text_and_protects_numeric_fields_editable_content_dialogs_and_background(edge_page,running_app):
    page=edge_page;field=page.get_by_label('标题内容',exact=True);field.fill('ABCD');field.press('Home');field.press('Delete')
    expect(field).to_have_value('BCD');expect(row(page,'title1')).to_have_count(1)
    numeric=page.get_by_label('字号',exact=True);numeric.focus();numeric.press('Delete');expect(row(page,'title1')).to_have_count(1)
    page.evaluate("{const e=document.createElement('div');e.id='editing-test';e.contentEditable='true';e.textContent='EDIT';document.body.append(e);e.focus();}")
    page.keyboard.press('Delete');expect(row(page,'title1')).to_have_count(1);page.locator('#editing-test').evaluate('e=>e.remove()')
    page.get_by_role('button',name='导出图片',exact=False).click();dialog=page.get_by_role('dialog',name='导出图片')
    dialog.get_by_role('button',name='返回编辑',exact=True).focus();page.keyboard.press('Delete');expect(row(page,'title1')).to_have_count(1)
    dialog.get_by_role('button',name='返回编辑',exact=True).click()
    row(page,'bg').click();row(page,'bg').focus();page.keyboard.press('Delete');expect(row(page,'bg')).to_have_count(1)
    saved(page);assert running_app['client'].get('/api/project').json()['project']['titles'][0]['text']=='BCD'
