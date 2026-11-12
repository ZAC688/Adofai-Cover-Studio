from tests.icon_checks import assert_pe_icon
from tests.e2e.test_app_icon import assert_desktop_logo
from .conftest import ROOT,BUNDLE


def test_executable_resource_contains_exact_seven_size_header_logo():
    assert_pe_icon(BUNDLE/'ADOFAI-Cover-Studio.exe',ROOT/'frontend/public/app-icon.ico')


def test_frozen_native_window_and_favicon_use_header_logo(tmp_path):
    assert_desktop_logo(tmp_path,binary=BUNDLE/'ADOFAI-Cover-Studio.exe')
