import pytest
from backend.desktop import permitted_url


@pytest.mark.parametrize('url',['http://127.0.0.1:1234/','http://127.0.0.1:1234/api/assets/abc',
                                 'about:blank','about:srcdoc','data:image/png;base64,AA==',
                                 'blob:http://127.0.0.1:1234/abc','qrc:/qtwebchannel/qwebchannel.js'])
def test_embedded_runtime_accepts_only_needed_local_schemes(url):
    assert permitted_url(url,1234)


@pytest.mark.parametrize('url',['https://example.com/','http://127.0.0.1:9876/',
                                 'http://localhost:1234/','file:///C:/Windows/win.ini',
                                 'javascript:alert(1)','http://127.0.0.1.evil:1234/',
                                 'http://127.0.0.1:wrong/','ftp://127.0.0.1:1234/file'])
def test_runtime_blocks_external_network_and_arbitrary_local_file_navigation(url):
    assert not permitted_url(url,1234)
