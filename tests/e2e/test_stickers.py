import io
import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .test_effects import pixels,color
from .test_export import export
from .test_editor import saved
from .test_objects import row,number
from .conftest import ROOT


def choose(page,preset,frame=0):
    page.get_by_role('button',name='选择贴纸',exact=True).click()
    dialog=page.get_by_role('dialog',name='选择贴纸',exact=True)
    dialog.get_by_role('button',name='分类 '+' / '.join(preset['category']),exact=True).click()
    dialog.locator(f'[data-preset-id="{preset["id"]}"]').click()
    if preset['frames']>1:dialog.get_by_label('贴纸帧',exact=True).fill(str(frame))
    dialog.get_by_role('button',name='添加贴纸',exact=True).click();expect(dialog).to_have_count(0);saved(page)


def drag_across_scroll(page,source,target):
    # Capture the real source before scrolling the destination into view. The
    # built-in drag_to scrolls both first and can grab a different scrolled row.
    source.scroll_into_view_if_needed();box=source.bounding_box()
    x=box['x']+box['width']/2;y=box['y']+box['height']/2
    page.mouse.move(x,y);page.mouse.down();page.mouse.move(x+20,y,steps=4)
    target.scroll_into_view_if_needed();end=target.bounding_box()
    page.mouse.move(end['x']+end['width']/2,end['y']+end['height']/2,steps=6);page.mouse.up()


def test_categories_selected_gif_frame_transform_shadow_order_and_export_restore(edge_page,running_app,tmp_path):
    page=edge_page;client=running_app['client'];items=client.get('/api/stickers').json();preset=next(item for item in items if item['frames']>10)
    choose(page,preset,preset['frames']-1)
    expect(page.locator('.object-row.selected')).to_contain_text('贴纸')
    before=pixels(page);doc=client.get('/api/project').json()['project'];id=next(iter(doc['stickers']));item=doc['stickers'][id]
    assert item['frame']==preset['frames']-1
    raw=client.get('/api/assets/'+item['asset']).content;reference=client.get(f'/api/stickers/{preset["id"]}/frames/{item["frame"]}').content
    np.testing.assert_array_equal(np.array(Image.open(io.BytesIO(raw))),np.array(Image.open(io.BytesIO(reference))))
    assert np.any(before[:,:,:3]!=[8,13,22])
    number(page,'贴纸宽度',400);number(page,'旋转角度',35);number(page,'水平位置',800)
    page.get_by_label('阴影开关',exact=True).check();color(page,'阴影颜色','#ff0000');number(page,'阴影距离',40)
    transformed=pixels(page);assert np.any(transformed!=before)
    drag_across_scroll(page,row(page,id),row(page,'bg'));saved(page)
    assert client.get('/api/project').json()['project']['layerOrder'][-2]==id
    page.get_by_role('button',name='4:3',exact=True).click();number(page,'旋转角度',-20)
    page.get_by_role('button',name='16:9',exact=True).click();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('35')
    rendered=pixels(page);export(page,tmp_path/'sticker.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'sticker.png')),rendered)
    page.reload();row(page,id).click();expect(page.get_by_label('阴影开关',exact=True)).to_be_checked();np.testing.assert_array_equal(pixels(page),rendered)
    page.get_by_role('button',name='删除对象',exact=True).click();expect(row(page,id)).to_have_count(0)
    page.get_by_role('button',name='撤销',exact=True).click();row(page,id).click();expect(page.get_by_label('旋转角度',exact=True)).to_have_value('35')
    np.testing.assert_array_equal(pixels(page),rendered)
    page.screenshot(path=str(ROOT/'artifacts/upgrade-03/04-stickers/editor.png'))


def test_duplicate_stickers_exceed_old_layer_limit_without_consuming_title_track_slots(edge_page,running_app):
    page=edge_page;preset=next(item for item in running_app['client'].get('/api/stickers').json() if item['frames']==1)
    for _ in range(12):choose(page,preset)
    expect(page.locator('.object-row')).to_have_count(16);pixels(page)
    p=running_app['client'].get('/api/project').json()['project'];assert len(p['stickers'])==12
    assert len({item['asset'] for item in p['stickers'].values()})==12
    expect(page.get_by_role('button',name='添加标题 2/5',exact=True)).to_be_enabled()
    expect(page.get_by_role('button',name='添加轨道 1/5',exact=True)).to_be_enabled()
    page.reload();expect(page.locator('.object-row')).to_have_count(16)


def test_all_and_every_category_display_complete_naturally_sorted_names(edge_page,running_app):
    page=edge_page;items=running_app['client'].get('/api/stickers').json()
    page.get_by_role('button',name='选择贴纸',exact=True).click();dialog=page.get_by_role('dialog',name='选择贴纸',exact=True)
    expect(dialog.locator('[data-preset-id]')).to_have_count(len(items))
    groups={tuple(item['category'][:depth]) for item in items for depth in range(1,len(item['category'])+1)}
    for category in [(),*sorted(groups)]:
        if category:dialog.get_by_role('button',name='分类 '+' / '.join(category),exact=True).click()
        else:dialog.get_by_role('button',name='全部素材',exact=False).click()
        expected=[item['id'] for item in items if tuple(item['category'][:len(category)])==category]
        expect(dialog.locator('[data-preset-id]')).to_have_count(len(expected))
        actual=dialog.locator('[data-preset-id]').evaluate_all('(buttons)=>buttons.map(b=>({id:b.dataset.presetId,name:b.querySelector("span").textContent}))')
        assert {entry['id'] for entry in actual}==set(expected)
        groups_to_check=[actual]
        if category and category[-1]=='新等级':
            leading=[v for v in actual if v['name'].lower().startswith('p')]
            trailing=[v for v in actual if v['name'].lower()=='crazy']
            middle=[v for v in actual if v not in leading and v not in trailing]
            assert actual==leading+middle+trailing
            groups_to_check=[leading,middle,trailing]
        for group in groups_to_check:
            assert page.evaluate('(items)=>{const c=new Intl.Collator("zh-CN",{numeric:true,sensitivity:"base"});return items.every((v,i)=>!i||c.compare(items[i-1].name,v.name)<=0)}',group)
    dialog.get_by_role('button',name='取消',exact=True).click()
