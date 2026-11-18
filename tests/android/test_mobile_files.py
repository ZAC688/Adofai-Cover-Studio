"""Browser-to-native contract tests; real Android picker tests are separate."""
import base64
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect
import pytest

from tests.android.test_server import runtime_client
from tests.android.test_mobile_layout import phone, mobile_browser

ROOT=Path(__file__).resolve().parents[2]

BRIDGE=r"""(()=>{
window.nativeFiles=[];window.nativeSaveState='saved';window.nativeClosed=[];
window.AndroidDevice={version:()=> '0.8.1-android.1',closeResult:ok=>nativeClosed.push(ok),
beginDownload:(name,mime,size)=>{const id='file-'+nativeFiles.length;nativeFiles.push({id,name,mime,size,chunks:[],written:0,done:false});return JSON.stringify({id});},
appendDownload:(id,offset,chunk)=>{const file=nativeFiles.find(file=>file.id===id);if(offset!==file.written)return JSON.stringify({error:'wrong offset'});file.chunks.push(chunk);file.written+=atob(chunk).length;return JSON.stringify({written:file.written});},
finishDownload:id=>{const file=nativeFiles.find(file=>file.id===id);file.done=true;queueMicrotask(()=>window.adofaiDownloadResult(id,nativeSaveState,''));return JSON.stringify({queued:true});},
cancelDownload:id=>{nativeFiles.find(file=>file.id===id).cancelled=true;}};
})()"""


@pytest.fixture
def android_contract(phone):
    page, client=phone
    page.context.add_init_script(BRIDGE)
    page.reload()
    expect(page.get_by_label('标题内容',exact=True)).to_be_visible()
    return page,client


def file_bytes(page,index=0):
    page.wait_for_function('(i)=>nativeFiles[i]?.done',arg=index)
    return base64.b64decode(page.evaluate('(i)=>btoa(nativeFiles[i].chunks.map(chunk=>atob(chunk)).join(""))',index))


def test_native_png_export_matches_full_resolution_preview(android_contract):
    page,client=android_contract
    page.get_by_label('标题内容',exact=True).fill('手机导出 PNG')
    page.locator('.export-trigger').tap()
    button=page.get_by_role('button',name='保存到手机',exact=True)
    expect(button).to_be_enabled()
    canvas=page.get_by_label('导出预览',exact=True)
    expected=Image.open(io.BytesIO(base64.b64decode(canvas.evaluate('canvas=>canvas.toDataURL().split(",")[1]')))).convert('RGBA')
    button.tap()
    image=Image.open(io.BytesIO(file_bytes(page))).convert('RGBA')
    assert image.size==(1920,1080) and image.tobytes()==expected.tobytes()
    expect(page.locator('[data-native-download-status]')).to_have_text('文件已保存到所选位置')
    assert page.evaluate('nativeFiles[0].mime')=='image/png'
    assert client.get('/api/project').json()['project']['titles'][0]['text']=='手机导出 PNG'


def test_native_save_cancel_keeps_project_and_allows_retry(android_contract):
    page,client=android_contract
    page.get_by_label('标题内容',exact=True).fill('取消不会丢失')
    page.locator('.export-trigger').tap()
    expect(page.get_by_role('button',name='保存到手机',exact=True)).to_be_enabled()
    expect(page.locator('.save-state')).to_have_text('已保存到本机')
    before=client.get('/api/project').json()
    page.evaluate("nativeSaveState='cancelled'")
    page.get_by_role('button',name='保存到手机',exact=True).tap()
    expect(page.locator('[data-native-download-status]')).to_have_text('已取消保存，作品仍保留')
    assert client.get('/api/project').json()==before
    page.evaluate("nativeSaveState='saved'")
    page.get_by_role('button',name='保存到手机',exact=True).tap()
    expect(page.locator('[data-native-download-status]')).to_have_text('文件已保存到所选位置')
    assert len(page.evaluate('nativeFiles'))==2


def test_native_text_and_filter_presets_include_font_bytes_and_roundtrip(android_contract):
    page,client=android_contract
    font=ROOT/'frontend/public/fonts/inter.ttf'
    page.get_by_label('标题内容',exact=True).fill('手机预设')
    page.get_by_label('字体文件',exact=True).set_input_files(str(font))
    page.wait_for_function('document.querySelector("select[aria-label=字体]").value.length===32')
    page.get_by_role('tab',name='滤镜',exact=True).tap()
    page.get_by_label('文字预设名称',exact=True).fill('手机文字')
    page.get_by_role('button',name='保存为文字预设',exact=True).tap()
    export=page.get_by_role('button',name='导出文字预设',exact=True)
    expect(export).to_be_enabled()
    export.tap()
    document=json.loads(file_bytes(page))
    assert document['format']=='adofai-text-preset'
    assert base64.b64decode(document['font']['data'])==font.read_bytes()
    assert document['font']['sha256']==hashlib.sha256(font.read_bytes()).hexdigest()
    assert page.evaluate('nativeFiles[0].chunks.length')>1
    page.get_by_label('文字预设文件',exact=True).set_input_files({'name':'mobile.adofai-text.json','mimeType':'application/json','buffer':json.dumps(document).encode()})
    page.get_by_label('选择滤镜',exact=True).select_option('GrayscaleFilter')
    page.get_by_role('button',name='添加滤镜',exact=True).tap()
    page.get_by_label('滤镜预设名称',exact=True).fill('手机滤镜')
    page.get_by_role('button',name='保存为滤镜预设',exact=True).tap()
    expect(page.get_by_role('button',name='导出滤镜预设',exact=True)).to_be_enabled()
    page.get_by_role('button',name='导出滤镜预设',exact=True).tap()
    filters=json.loads(file_bytes(page,1))
    assert filters['format']=='adofai-filter-preset' and filters['filters'][0]['type']=='GrayscaleFilter'
    assert len(client.get('/api/text-presets').json())==2


def test_android_information_and_back_save_current_work(android_contract):
    page,client=android_contract
    page.get_by_label('标题内容',exact=True).fill('返回键保存')
    page.get_by_role('button',name='信息',exact=True).tap()
    expect(page.get_by_label('应用版本',exact=True)).to_have_text('0.8.1-android.1')
    page.get_by_role('tab',name='使用说明',exact=True).tap()
    expect(page.get_by_role('tabpanel')).to_contain_text('安卓使用说明')
    assert page.evaluate('window.adofaiBackRequest()') is False
    expect(page.get_by_role('dialog')).to_have_count(0)
    assert page.evaluate('window.adofaiBackRequest()') is True
    assert client.get('/api/project').json()['project']['titles'][0]['text']=='返回键保存'
