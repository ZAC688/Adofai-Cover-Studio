import subprocess
import sys

from .conftest import ROOT


def test_production_frontend_opens_in_real_edge(edge_page):
    assert edge_page.title() == "ADOFAI 封面制作器"
    assert edge_page.get_by_role("heading", name="ADOFAI 封面制作器").count() == 1


def test_launcher_reuses_live_instance(running_app, tmp_path):
    ready = tmp_path / "duplicate-ready.json"
    result = subprocess.run(
        [sys.executable, "-m", "backend.launcher", "--data-dir", str(running_app["data"]),
         "--ready-file", str(ready), "--no-browser"], cwd=ROOT, capture_output=True,
        timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert ready.read_bytes() == running_app["ready"].read_bytes()
