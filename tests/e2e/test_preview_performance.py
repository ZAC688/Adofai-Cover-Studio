"""Native-engine regression for large lights blocking unrelated edits in 0.8.0."""
from copy import deepcopy
import base64
import ctypes
import io
import json
import os

import numpy as np
import pytest
from PIL import Image
from playwright.sync_api import expect

from .conftest import ROOT
from .test_desktop_runtime import start_desktop,stop_desktop
from playwright.sync_api import sync_playwright


def start_visible_preview(directory,*,binary=None):
    assert os.environ.get('ADOFAI_VISIBLE_PERFORMANCE_TESTS')=='1', (
        'Native first-frame timing requires a visible desktop window. '
        'After desktop approval, use tools/test-all.ps1 -VisiblePerformanceTests '
        'or set ADOFAI_VISIBLE_PERFORMANCE_TESTS=1; do not time an occluded widget.'
    )
    host=start_desktop(directory,binary=binary,visible=True)
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    user.SetWindowPos.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
    try:
        state=json.loads(host['ready'].read_text(encoding='utf-8'))
        handle=state['windowHandle'];owner=ctypes.c_ulong()
        user.GetWindowThreadProcessId(handle,ctypes.byref(owner))
        assert owner.value==state['pid'],'Refuse to reposition an unrelated window.'
        # Keep only this disposable test window exposed, without taking keyboard
        # focus or sending physical input to the user's desktop applications.
        assert user.SetWindowPos(handle,ctypes.c_void_p(-1),20,20,1440,1000,0x0010|0x0040)
        return host
    except Exception:
        stop_desktop(host);raise


@pytest.fixture
def preview_desktop(tmp_path):
    host=start_visible_preview(tmp_path)
    try:
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp(f'http://127.0.0.1:{host["debug"]}',no_defaults=True)
            page=browser.contexts[0].pages[0];page.set_viewport_size({'width':1440,'height':1000})
            page.wait_for_url(host['url']+'/',timeout=30000)
            expect(page.get_by_label('标题内容',exact=True)).to_be_visible(timeout=30000)
            yield host,page
    finally:stop_desktop(host)


PROBE = '''()=>{
  window.previewProbe={jobs:0,paint:0,paintedAt:0,longTasks:[]};
  new PerformanceObserver(list=>{for(const item of list.getEntries())window.previewProbe.longTasks.push(item.duration);}).observe({type:'longtask'});
  const NativeWorker=window.Worker;
  window.Worker=class extends NativeWorker{
    postMessage(...args){window.previewProbe.jobs++;return super.postMessage(...args);}
  };
  const draw=CanvasRenderingContext2D.prototype.drawImage;
  CanvasRenderingContext2D.prototype.drawImage=function(...args){
    const result=draw.apply(this,args);
    if(this.canvas instanceof HTMLCanvasElement&&this.canvas.matches('canvas[aria-label="封面画布"]')){
      window.previewProbe.paint++;window.previewProbe.paintedAt=performance.now();
    }
    return result;
  };
}'''


def configure(page, host):
    # Keep document focus without physically taking the user's keyboard focus.
    session=page.context.new_cdp_session(page)
    session.send('Emulation.setFocusEmulationEnabled',{'enabled':True})
    client = host['client']
    client.headers['x-editor-token'] = client.get(host['url']+'/api/session').json()['token']
    loaded = client.get(host['url']+'/api/project').json()
    project = loaded['project']
    project['activeRatio'] = '4:3'
    project['layouts']['4:3'] = deepcopy(project['layouts']['16:9'])
    project['layouts']['4:3']['title1'].update(x=180, y=300, fontSize=237)
    project['titles'][0].update(text='性能测', color='#ffffff', glow=69)
    project['titles'][0]['effects'] = {
        kind: dict(enabled=True, color='#9d6dff', color2='#62bfff', intensity=intensity,
                   radius=radius, width=4, direction=90, blend='screen', followGradient=False)
        for kind, intensity, radius in [('outerGlow',69,39),('bloom',75,67),('horizontalBlur',89,87)]
    }
    payload=io.BytesIO();Image.new('RGB',(64,64),(24,32,48)).save(payload,'PNG')
    asset=client.post(host['url']+'/api/assets',files={'file':('background.png',payload.getvalue(),'image/png')}).json()
    project['bgAsset']=asset['id']
    project['layouts']['4:3']['bg'].update(x=720,y=540,scale=22.5)
    response=client.put(host['url']+'/api/project',json={'baseRevision':loaded['revision'],'project':project})
    assert response.status_code == 200,response.text
    page.add_init_script('('+PROBE+')()')
    page.reload()
    expect(page.get_by_label('标题内容',exact=True)).to_have_value('性能测')
    settled(page)
    assert page.evaluate("document.visibilityState==='visible'&&document.hasFocus()")


def settled(page):
    expect(page.get_by_label('封面画布',exact=True)).to_have_attribute('aria-busy','false',timeout=20000)
    expect(page.get_by_text('已保存到本机',exact=True)).to_be_visible(timeout=15000)


def edit(page, label, value):
    field=page.get_by_label(label,exact=True)
    before=page.evaluate('window.previewProbe.paint')
    metrics=field.evaluate('''async(input,value)=>{
      window.previewProbe.longTasks=[];
      const start=performance.now();
      const prototype=input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(prototype,'value').set.call(input,String(value));
      input.dispatchEvent(new Event('input',{bubbles:true}));
      const dispatchMs=performance.now()-start;
      const [uiFrameMs,timerMs]=await Promise.all([
        new Promise(resolve=>requestAnimationFrame(()=>resolve(performance.now()-start))),
        new Promise(resolve=>setTimeout(()=>resolve(performance.now()-start),16)),
      ]);
      return {start,dispatchMs,uiFrameMs,timerMs};
    }''',value)
    page.wait_for_function('''before=>window.previewProbe.paint>before&&document.querySelector('canvas[aria-label="封面画布"]').getAttribute('aria-busy')==='false' ''',arg=before,timeout=20000)
    metrics.update(page.evaluate('start=>({previewMs:window.previewProbe.paintedAt-start,jobs:window.previewProbe.jobs,longTasks:window.previewProbe.longTasks})',metrics.pop('start')))
    directory=ROOT/'artifacts/hotfix-081';directory.mkdir(parents=True,exist_ok=True)
    with (directory/(os.environ.get('PREVIEW_PHASE','source')+'-measurements.jsonl')).open('a',encoding='utf-8') as file:
        file.write(json.dumps({'field':label,'value':value,**metrics},ensure_ascii=False)+'\n')
    return {'field':label,'value':value,**metrics}


def canvas_pixels(page,label='封面画布'):
    encoded=page.get_by_label(label,exact=True).evaluate("canvas=>canvas.toDataURL().split(',')[1]")
    return np.array(Image.open(io.BytesIO(base64.b64decode(encoded))))


def exercise_preview(page,host):
    configure(page,host)
    initial=canvas_pixels(page)
    jobs=page.evaluate('window.previewProbe.jobs')
    results=[]
    for object_id in ['bg','title1']:
        page.locator(f'[data-object-id="{object_id}"]').click()
        field=page.get_by_label('水平位置',exact=True)
        start=float(field.input_value())
        for amount in [1,2,3]:
            result=edit(page,'水平位置',start+amount);results.append(result)
            assert result['previewMs']<250,result
            assert result['uiFrameMs']<120,result
            assert result['timerMs']<120,result
            assert result['jobs']==jobs,'Moving an object must reuse unchanged light pixels.'
    assert np.any(canvas_pixels(page)!=initial)
    for text in ['实时测','预览测','性能测']:
        result=edit(page,'标题内容',text);results.append(result)
        assert result['previewMs']<500,result
        assert result['uiFrameMs']<120,result
        assert result['timerMs']<120,result
    if not page.get_by_label('发光强度',exact=True).is_visible():page.get_by_text('基础发光设置',exact=True).click()
    for value in [70,71,72]:
        result=edit(page,'发光强度',value);results.append(result)
        assert result['previewMs']<500,result
        assert result['uiFrameMs']<120,result
        assert result['timerMs']<120,result
    settled(page)
    final=canvas_pixels(page)
    assert np.any(final!=initial)
    page.get_by_role('button',name='导出图片',exact=False).click()
    expect(page.get_by_role('dialog',name='导出图片').get_by_role('button',name='导出到电脑')).to_be_enabled(timeout=20000)
    np.testing.assert_array_equal(canvas_pixels(page,'导出预览'),final)
    page.get_by_role('button',name='返回编辑',exact=True).click()
    page.reload();settled(page)
    np.testing.assert_array_equal(canvas_pixels(page),final,err_msg='Cold rendering must match the cached preview exactly.')
    expect(page.locator('.error-banner')).to_have_count(0)
    directory=ROOT/'artifacts/hotfix-081';directory.mkdir(parents=True,exist_ok=True)
    (directory/(os.environ.get('PREVIEW_PHASE','source')+'-regression.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


def test_native_heavy_light_edits_are_fast_cached_and_export_exactly(preview_desktop):
    host,page=preview_desktop
    exercise_preview(page,host)
