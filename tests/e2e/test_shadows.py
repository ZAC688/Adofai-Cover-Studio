import numpy as np
from PIL import Image
import pytest
from playwright.sync_api import expect
from .test_effects import pixels,color
from .test_editor import select,upload_track
from .test_export import export
from .test_selection import upload_shape


def number(page,label,value):
    page.get_by_label(label,exact=True).fill(str(value));page.locator('.panel-heading').first.click()


@pytest.mark.parametrize('target',['text','track'])
def test_shadow_follows_body_has_soft_edges_can_be_disabled_and_exports(edge_page,running_app,tmp_path,target):
    page=edge_page
    if target=='track':upload_track(page);number(page,'缩放 (%)',25)
    else:page.get_by_label('标题内容',exact=True).fill('SHADOW')
    number(page,'发光强度',0);baseline=pixels(page)
    page.get_by_label('阴影开关',exact=True).check();color(page,'阴影颜色','#ff0000')
    number(page,'阴影不透明度',100);number(page,'阴影方向',0);number(page,'阴影距离',90);number(page,'阴影模糊',0)
    hard=pixels(page);changed=np.any(hard!=baseline,axis=2);assert changed.sum()>100
    # Red shadow must fall to the right of the original alpha silhouette.
    ys,xs=np.where(changed);assert xs.mean()>100
    number(page,'阴影模糊',24);soft=pixels(page)
    assert np.count_nonzero(np.any(soft!=baseline,axis=2))>changed.sum()
    assert np.any((soft[:,:,0]>baseline[:,:,0])&(soft[:,:,0]<240))
    page.get_by_label('阴影开关',exact=True).uncheck();np.testing.assert_array_equal(pixels(page),baseline)
    page.get_by_label('阴影开关',exact=True).check();expect(page.get_by_label('阴影模糊',exact=True)).to_have_value('24')
    np.testing.assert_array_equal(pixels(page),soft)
    number(page,'旋转角度',30);rotated=pixels(page)
    export(page,tmp_path/f'{target}-shadow.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/f'{target}-shadow.png')),rotated)
    page.reload()
    if target=='track':select(page,'轨道图形')
    expect(page.get_by_label('阴影开关',exact=True)).to_be_checked();expect(page.get_by_label('阴影方向',exact=True)).to_have_value('0')
    np.testing.assert_array_equal(pixels(page),rotated)
    doc=running_app['client'].get('/api/project').json()['project']
    assert (doc['titles'][0]['shadow'] is None) if target=='track' else (doc['trackShadow'] is None)


def test_shadow_direction_uses_visible_alpha_including_transparent_holes(edge_page,tmp_path):
    page=edge_page;upload_shape(page,tmp_path);number(page,'缩放 (%)',50);number(page,'发光强度',0)
    page.get_by_label('阴影开关',exact=True).check();color(page,'阴影颜色','#ff0000')
    number(page,'阴影不透明度',100);number(page,'阴影距离',90);number(page,'阴影模糊',0);number(page,'阴影方向',0)
    right=pixels(page)
    np.testing.assert_array_equal(right[536,1026,:3],[255,0,0])
    np.testing.assert_array_equal(right[526,1041,:3],[8,13,22])
    number(page,'阴影方向',90);down=pixels(page)
    np.testing.assert_array_equal(down[626,936,:3],[255,0,0])
    np.testing.assert_array_equal(down[536,1026,:3],[8,13,22])
