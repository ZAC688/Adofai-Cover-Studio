import json
import os
import numpy as np
from PIL import Image
from playwright.sync_api import expect
from .conftest import ROOT
from .test_effects import pixels,open_effects
from .test_export import export

def test_continuous_palette_coalesces_work_and_preserves_final_color_history_and_png(edge_page,running_app,tmp_path):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('COLOR 光效测试')
    page.get_by_label('字号',exact=True).fill('200');open_effects(page)
    for name in ['多尺度 Bloom','水平模糊','发光描边']:page.get_by_label(name+'开关',exact=True).check()
    baseline=pixels(page);old=running_app['client'].get('/api/project').json()['project']['titles'][0]['color']
    field=page.get_by_label('文字颜色',exact=True);field.focus()
    profile=field.evaluate('''async input=>{
      const canvas=document.querySelector('canvas[aria-label="封面画布"]');let writes=0;
      const descriptor=Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype,'width');
      Object.defineProperty(canvas,'width',{get(){return descriptor.get.call(this)},set(v){writes++;descriptor.set.call(this,v)},configurable:true});
      const start=performance.now();const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
      for(let i=0;i<60;i++){setter.call(input,'#'+(0x102030+i*0x010203).toString(16).padStart(6,'0'));input.dispatchEvent(new Event('input',{bubbles:true}));await new Promise(r=>setTimeout(r,8));}
      setter.call(input,'#e7c3a1');input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));input.blur();
      await new Promise(r=>setTimeout(r,400));delete canvas.width;
      return {events:61,elapsedMs:performance.now()-start,canvasWrites:writes};
    }''')
    result=pixels(page);assert running_app['client'].get('/api/project').json()['project']['titles'][0]['color']=='#e7c3a1'
    output=ROOT/'artifacts/upgrade-04/06-palette';output.mkdir(parents=True,exist_ok=True)
    (output/(os.environ.get('PALETTE_PHASE','optimized')+'.json')).write_text(json.dumps(profile,indent=2),encoding='utf-8')
    page.get_by_role('button',name='撤销',exact=True).click();expect(field).to_have_value(old);np.testing.assert_array_equal(pixels(page),baseline)
    page.get_by_role('button',name='重做',exact=True).click();np.testing.assert_array_equal(pixels(page),result)
    export(page,tmp_path/'palette.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'palette.png')),result)
    page.reload();expect(page.get_by_label('文字颜色',exact=True)).to_have_value('#e7c3a1');np.testing.assert_array_equal(pixels(page),result)
    assert profile['canvasWrites']<=4,profile


def test_input_only_color_is_flushed_before_object_switch_ratio_and_export(edge_page,running_app,tmp_path):
    page=edge_page;client=running_app['client'];pixels(page)
    def input_only(label,value):
        page.get_by_label(label,exact=True).focus()
        page.get_by_label(label,exact=True).evaluate('''(field,value)=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(field,value);field.dispatchEvent(new Event('input',{bubbles:true}));}''',value)
    input_only('文字颜色','#123456')
    page.locator('[data-object-id="title2"]').click();pixels(page)
    doc=client.get('/api/project').json()['project']
    assert doc['titles'][0]['color']=='#123456' and doc['titles'][1]['color']!='#123456'
    input_only('文字颜色','#fedcba');page.get_by_role('button',name='4:3',exact=True).click();pixels(page)
    assert client.get('/api/project').json()['project']['titles'][1]['color']=='#fedcba'
    input_only('文字颜色','#986543');export(page,tmp_path/'last-color.png')
    rendered=pixels(page);np.testing.assert_array_equal(np.array(Image.open(tmp_path/'last-color.png')),rendered)
    assert client.get('/api/project').json()['project']['titles'][1]['color']=='#986543'
