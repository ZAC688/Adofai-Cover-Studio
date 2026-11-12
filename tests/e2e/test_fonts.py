import numpy as np
from playwright.sync_api import expect

from .conftest import ROOT
from .test_editor import saved
from .test_effects import pixels
from .test_export import export
from PIL import Image


def test_bundled_chinese_and_english_fonts_change_real_glyphs_offline(edge_page):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('Typography AVATAR')
    page.get_by_label('发光强度',exact=True).fill('0')
    page.get_by_label('字体',exact=True).select_option('inter');sans=pixels(page)
    page.get_by_label('字体',exact=True).select_option('noto-serif');serif=pixels(page)
    assert np.count_nonzero(np.any(sans!=serif,axis=2))>500
    page.get_by_label('标题内容',exact=True).fill('冰与火之舞中文字体')
    page.get_by_label('字体',exact=True).select_option('noto-sans-sc');chinese_sans=pixels(page)
    page.get_by_label('字体',exact=True).select_option('noto-serif-sc');chinese_serif=pixels(page)
    assert np.count_nonzero(np.any(chinese_sans!=chinese_serif,axis=2))>500
    assert page.evaluate("[...document.fonts].filter(face=>face.status==='loaded'&&face.family.startsWith('CoverFont_')).length")>=4


def test_uploaded_font_persists_and_export_uses_same_face(edge_page,running_app,tmp_path):
    page=edge_page
    page.get_by_label('标题内容',exact=True).fill('UPLOADED FONT · 字体')
    page.get_by_label('字体文件',exact=True).set_input_files(str(ROOT/'frontend/public/fonts/inter.ttf'))
    expect(page.get_by_label('字体',exact=True)).not_to_have_value('system')
    before=pixels(page)
    font_id=page.get_by_label('字体',exact=True).input_value()
    assert len(font_id)==32
    assert running_app['client'].get('/api/project').json()['project']['titles'][0]['fontId']==font_id
    page.reload();expect(page.get_by_label('字体',exact=True)).to_have_value(font_id)
    after=pixels(page);np.testing.assert_array_equal(before,after)
    export(page,tmp_path/'font.png');np.testing.assert_array_equal(after,np.array(Image.open(tmp_path/'font.png')))
    page.get_by_label('字体文件',exact=True).set_input_files({'name':'corrupt.ttf','mimeType':'font/ttf','buffer':b'OTTOinvalid'})
    expect(page.get_by_role('alert')).to_contain_text('字体')
    expect(page.get_by_label('字体',exact=True)).to_have_value(font_id)


def test_six_user_supplied_faces_render_real_distinct_glyphs_and_restore_styles(edge_page,running_app,tmp_path):
    page=edge_page;page.get_by_label('标题内容',exact=True).fill('AVATAR Mono 0123')
    page.get_by_label('发光强度',exact=True).fill('0')
    faces=['bebas-neue','russo-one','space-mono','space-mono-italic','space-mono-bold','space-mono-bold-italic']
    results=[]
    for font_id in faces:
        page.get_by_label('字体',exact=True).select_option(font_id);image=pixels(page)
        assert running_app['client'].get('/api/project').json()['project']['titles'][0]['fontId']==font_id
        page.reload();expect(page.get_by_label('字体',exact=True)).to_have_value(font_id)
        np.testing.assert_array_equal(pixels(page),image)
        info=page.evaluate('(id)=>{const f=[...document.fonts].find(f=>f.family==="CoverFont_"+id.replaceAll("-","_"));return {weight:f.weight,style:f.style,status:f.status}}',font_id)
        assert info=={'weight':'700' if 'bold' in font_id else '400','style':'italic' if 'italic' in font_id else 'normal','status':'loaded'}
        results.append(image)
    for i,image in enumerate(results):
        for other in results[:i]:assert np.count_nonzero(np.any(image!=other,axis=2))>500
    export(page,tmp_path/'supplied-font.png');np.testing.assert_array_equal(np.array(Image.open(tmp_path/'supplied-font.png')),results[-1])
    options=page.get_by_label('字体',exact=True).inner_text().lower()
    assert 'clash' not in options and 'tanker' not in options
