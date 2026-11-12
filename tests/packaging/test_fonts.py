from playwright.sync_api import expect
from tests.e2e.test_fonts import test_bundled_chinese_and_english_fonts_change_real_glyphs_offline as verify_builtins
from tests.e2e.test_fonts import test_uploaded_font_persists_and_export_uses_same_face as verify_uploaded
from tests.backend.test_fonts import font_bytes
from tests.e2e.test_effects import pixels


def test_frozen_package_includes_all_four_offline_faces(edge_page):
    verify_builtins(edge_page)


def test_frozen_package_validates_and_restores_uploaded_font(edge_page,running_app,tmp_path):
    verify_uploaded(edge_page,running_app,tmp_path)


def test_frozen_package_accepts_and_renders_woff2(edge_page,running_app):
    client=running_app['client']
    response=client.post('/api/fonts',files={'file':('custom.woff2',font_bytes('woff2'),'font/woff2')})
    assert response.status_code==200,response.text
    font_id=response.json()['id']
    edge_page.reload()
    edge_page.get_by_label('标题内容',exact=True).fill('WOFF2 packaged')
    edge_page.get_by_label('字体',exact=True).select_option(font_id)
    pixels(edge_page)
    assert edge_page.evaluate('(id)=>[...document.fonts].some(face=>face.family==="CoverFont_"+id&&face.status==="loaded")',font_id)
