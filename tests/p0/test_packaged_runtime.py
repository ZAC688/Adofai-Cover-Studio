import json
import os
from pathlib import Path
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_binary_runs_without_python_or_development_path(tmp_path):
    executable = ROOT / "dist/adofai-p0/adofai-p0.exe"
    assert executable.is_file(), "Build the P0 prototype before running the full P0 suite"
    clean_environment = {k: v for k, v in os.environ.items()
                         if k.upper() not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}}
    clean_environment["PATH"] = r"C:\Windows\System32;C:\Windows"
    output = tmp_path / "中文目录 with spaces"
    result = subprocess.run(
        [str(executable), "--input", str(ROOT / "test-assets/reference/user-reference.png"),
         "--output", str(output)],
        cwd=tmp_path, env=clean_environment, capture_output=True, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    report = json.loads(result.stdout)
    assert report["size"] == [1612, 1043]
    with Image.open(output / "u2netp-mask.png") as actual:
        assert actual.size == (1612, 1043)
        assert actual.getextrema()[1] > actual.getextrema()[0]


def test_frozen_binary_refuses_missing_explicit_offline_model(tmp_path):
    executable = ROOT / "dist/adofai-p0/adofai-p0.exe"
    assert executable.is_file(), "Build the P0 prototype before running the full P0 suite"
    result = subprocess.run(
        [str(executable), "--input", str(ROOT / "test-assets/reference/user-reference.png"),
         "--output", str(tmp_path), "--model", str(tmp_path / "not-present.onnx")],
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode != 0
    assert "Offline model is missing" in result.stderr.decode(errors="replace")
