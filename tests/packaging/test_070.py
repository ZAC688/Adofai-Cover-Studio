import json
from .conftest import BUNDLE,ROOT
from tests.e2e.test_070_manual import test_desktop_version_and_track_instructions_are_available_offline as manual_case


def test_frozen_manual_is_current_and_matches_embedded_content(edge_page,running_app):
    assert (BUNDLE/'使用说明.md').read_bytes()==(ROOT/'docs/使用说明.md').read_bytes()
    manifest=json.loads((BUNDLE/'release-manifest.json').read_text(encoding='utf-8'))
    assert manifest['version']=='0.8.0'
    assert manifest['external_browser_required'] is False
    assert manifest['runtime_download_on_start'] is False
    assert manifest['generated_tracks'] is True and manifest['persistent_chart_recipes'] is True
    assert manifest['chart_styles']==['gold','chart'] and manifest['chart_default_style']=='gold'
    assert manifest['chart_resolution_long_edges']==[1920,2560,3840,4096]
    license_dir=BUNDLE/'_internal/licenses/QtWebEngine'
    credits=json.loads((license_dir/'credits-manifest.json').read_text(encoding='utf-8'))
    assert credits['version']=='6.140.0' and len(credits['documents'])>=100
    assert (license_dir/'Chromium-credits.html').stat().st_size>500000
    assert (license_dir/'LGPL-3.0.txt').is_file()
    manual_case(edge_page,running_app)
