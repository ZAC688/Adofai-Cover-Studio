import io
import json
from pathlib import Path
import sqlite3

from PIL import Image
import pytest

from backend.app.schema import Project, default_project
from backend.app.storage import Store, ConflictError


def png_bytes(size=(40, 30)):
    output = io.BytesIO()
    Image.new("RGBA", size, (130, 60, 80, 128)).save(output, "PNG")
    return output.getvalue()


def test_save_reopens_with_images_masks_and_both_layouts(tmp_path):
    store = Store(tmp_path)
    original = png_bytes()
    track = store.put_image(original)
    mask = store.put_pixels(Image.new("L", (40, 30), 90), "mask")
    project = default_project()
    project.update(trackAsset=track["id"], maskAsset=mask["id"], baseMaskAsset=mask["id"], removeBackground=True)
    project["titles"][0]["text"] = "轨道测试，重开恢复"
    project["layouts"]["4:3"] = json.loads(json.dumps(project["layouts"]["16:9"]))
    store.save(0, Project.model_validate(project))
    restored = Store(tmp_path).load()
    assert restored["project"] == project
    assert restored["revision"] == 1
    assert store.asset_path(track["id"]).with_suffix(".original").read_bytes() == original
    assert Image.open(store.asset_path(mask["id"])).getpixel((3, 3)) == 90


def test_stale_writer_cannot_overwrite_newer_project(tmp_path):
    first, second = Store(tmp_path), Store(tmp_path)
    project = default_project()
    project["name"] = "新的作品"
    first.save(0, Project.model_validate(project))
    with pytest.raises(ConflictError):
        second.save(0, Project.model_validate(default_project()))
    assert first.load()["project"]["name"] == "新的作品"


def test_missing_resource_never_replaces_existing_project(tmp_path):
    store = Store(tmp_path)
    project = default_project()
    project["trackAsset"] = "a" * 32
    with pytest.raises(FileNotFoundError):
        store.save(0, Project.model_validate(project))
    assert store.load()["revision"] == 0


def test_failed_disk_write_does_not_change_project(tmp_path, monkeypatch):
    store = Store(tmp_path)
    before = store.load()
    def fail(*_args, **_kwargs):
        raise OSError("simulated disk failure")
    monkeypatch.setattr("backend.app.storage.os.replace", fail)
    with pytest.raises(OSError):
        store.put_image(png_bytes())
    assert store.load() == before


def test_database_failure_rolls_back_save(tmp_path):
    store = Store(tmp_path)
    with store.connect() as db:
        db.execute("CREATE TRIGGER reject_save BEFORE UPDATE ON project BEGIN SELECT RAISE(ABORT,'write failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.save(0, Project.model_validate(default_project()))
    assert store.load()["revision"] == 0


def test_invalid_asset_paths_and_mask_coordinates_rejected(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(ValueError):
        store.asset_path("../../PRD.md")
    track = store.put_image(png_bytes())
    mask = store.put_pixels(Image.new("L", (4, 3)), "mask")
    project = default_project()
    project.update(trackAsset=track["id"], maskAsset=mask["id"], removeBackground=True)
    with pytest.raises(ValueError, match="尺寸"):
        store.save(0, Project.model_validate(project))
