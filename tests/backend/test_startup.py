import sys
from pathlib import Path

import pytest

from backend import launcher
from experiments.p0 import find_edge


def test_missing_edge_does_not_open_default_or_other_browser(tmp_path, monkeypatch):
    monkeypatch.setenv('PROGRAMFILES', str(tmp_path / 'missing-programfiles'))
    monkeypatch.setenv('PROGRAMFILES(X86)', str(tmp_path / 'missing-programfiles-x86'))
    with pytest.raises(FileNotFoundError, match='Microsoft Edge'):
        find_edge()


def test_missing_ui_is_reported_before_service_start(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['app', '--no-browser', '--data-dir', str(tmp_path / 'data')])
    monkeypatch.setattr(launcher, 'resource_root', lambda: tmp_path / 'missing-bundle')
    with pytest.raises(RuntimeError, match='界面资源缺失'):
        launcher.main()


def test_missing_model_is_reported_before_service_start(tmp_path, monkeypatch):
    bundle = tmp_path / 'bundle'
    frontend = bundle / 'frontend/dist'
    frontend.mkdir(parents=True)
    (frontend / 'index.html').write_text('test', encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['app', '--no-browser', '--data-dir', str(tmp_path / 'data')])
    monkeypatch.setattr(launcher, 'resource_root', lambda: bundle)
    with pytest.raises(RuntimeError, match='识别资源缺失'):
        launcher.main()
