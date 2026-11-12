import base64
import io
import re

import numpy as np
from PIL import Image
from playwright.sync_api import expect

from .conftest import ROOT
from .test_editor import saved


def test_monochrome_chrome_keeps_colored_artwork_and_controls(edge_page):
    page = edge_page
    expect(page.locator('.save-state')).to_have_text('已保存到本机')
    selectors = ['body','.topbar','.brand-mark','.workspace','.objects-panel',
                 '.properties-panel','.object-row.selected','.primary','.upload-card']
    for selector in selectors:
        for property_name in ['backgroundColor','color','borderTopColor']:
            color = page.locator(selector).first.evaluate('(element, property) => getComputedStyle(element)[property]',property_name)
            components = re.findall(r'[\d.]+',color)
            assert len(components)>=3, (selector,property_name,color)
            r,g,b=map(float,components[:3])
            assert r==g==b, (selector,property_name,color)
    page.get_by_label('标题内容',exact=True).fill('彩色作品仍然可用')
    page.get_by_label('文字颜色',exact=True).evaluate('''input => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'#ff3044');
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
    }''')
    page.locator('.panel-heading').first.click()
    saved(page)
    expect(page.get_by_label('文字颜色',exact=True)).to_have_value('#ff3044')
    raw=page.get_by_label('封面画布',exact=True).evaluate("canvas=>canvas.toDataURL('image/png').split(',')[1]")
    pixels=np.array(Image.open(io.BytesIO(base64.b64decode(raw))))
    assert ((pixels[:,:,0]>200)&(pixels[:,:,1]<100)&(pixels[:,:,2]<120)).sum()>100
    directory=ROOT/'artifacts/upgrade/01-theme';directory.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(directory/'editor.png'))
