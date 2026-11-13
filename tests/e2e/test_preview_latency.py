import json
import os
import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .test_effects import pixels,open_effects
from .test_export import export
from .conftest import ROOT


def test_heavy_slider_stays_responsive_and_shows_intermediate_previews(edge_page,running_app,tmp_path):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('实时光效 PREVIEW')
    page.get_by_label('字号',exact=True).fill('180');open_effects(page)
    for name in ['多尺度 Bloom','发光描边','水平模糊']:
        page.get_by_label(name+'开关',exact=True).check()
    baseline=pixels(page)
    slider=page.get_by_label('多尺度 Bloom强度滑块',exact=True)
    slider.dispatch_event('pointerdown')
    profile=slider.evaluate('''async input=>{
      const canvas=document.querySelector('canvas[aria-label="封面画布"]');let writes=0,maxDelay=0;
      const context=canvas.getContext('2d'),draw=context.drawImage;
      context.drawImage=function(...args){writes++;return draw.apply(this,args);};
      const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set,start=performance.now();
      for(let i=0;i<36;i++){
        setter.call(input,String(20+i*2));input.dispatchEvent(new Event('input',{bubbles:true}));
        const t=performance.now();await new Promise(r=>setTimeout(r,16));maxDelay=Math.max(maxDelay,performance.now()-t-16);
      }
      const result={events:36,elapsedMs:performance.now()-start,maxTimerDelayMs:maxDelay,intermediateFrames:writes};
      delete context.drawImage;return result;
    }''')
    slider.dispatch_event('pointerup')
    final=pixels(page)
    directory=ROOT/'artifacts/upgrade-05/03-preview';directory.mkdir(parents=True,exist_ok=True)
    (directory/(os.environ.get('PREVIEW_PHASE','optimized')+'.json')).write_text(json.dumps(profile,indent=2),encoding='utf-8')
    assert profile['elapsedMs']<1400,profile
    assert profile['maxTimerDelayMs']<120,profile
    assert profile['intermediateFrames']>=2,profile
    assert running_app['client'].get('/api/project').json()['project']['titles'][0]['effects']['bloom']['intensity']==90
    assert np.any(final!=baseline)
    page.get_by_role('button',name='撤销',exact=True).click();np.testing.assert_array_equal(pixels(page),baseline)
    page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),final)
    export(page,tmp_path/'fast-preview.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'fast-preview.png')),final)
    page.reload();np.testing.assert_array_equal(pixels(page),final)
    expect(page.locator('.error-banner')).to_have_count(0)
