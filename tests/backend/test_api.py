import io
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from backend.app.api import create_app
from backend.app.schema import default_project


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        token = client.get("/api/session").json()["token"]
        client.headers["x-editor-token"] = token
        yield client


def valid_png(length=None):
    stream = io.BytesIO()
    Image.new("RGBA", (16, 12), (60, 120, 200, 80)).save(stream, "PNG")
    raw = stream.getvalue()
    return raw if length is None else raw + bytes(length - len(raw))


def test_session_and_cross_origin_requests(client):
    assert client.post("/api/shutdown", headers={"origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/api/shutdown", headers={"x-editor-token": "incorrect"}).status_code == 403
    assert client.get("/api/project").status_code == 200


@pytest.mark.parametrize("size, expected", [(9_999_999, 200), (10_000_000, 200), (10_000_001, 413)])
def test_exact_upload_boundary_counts_file_not_multipart(client, size, expected):
    response = client.post("/api/assets", files={"file": ("截图.png", valid_png(size), "image/png")})
    assert response.status_code == expected, response.text
    assert client.get("/api/project").json()["revision"] == 0


def test_invalid_image_and_restore_without_original_file(client):
    assert client.post("/api/assets", files={"file": ("fake.png", b"not image", "image/png")}).status_code == 400
    upload = client.post("/api/assets", files={"file": ("track.png", valid_png(), "image/png")}).json()
    project = default_project()
    project["trackAsset"] = upload["id"]
    saved = client.put("/api/project", json={"baseRevision": 0, "project": project})
    assert saved.status_code == 200
    assert client.get("/api/assets/" + upload["id"]).headers["content-type"] == "image/png"
    assert client.put("/api/project", json={"baseRevision": 0, "project": project}).status_code == 409


def test_corrupt_saved_resource_is_reported_without_reset(client):
    upload = client.post("/api/assets", files={"file": ("track.png", valid_png(), "image/png")}).json()
    project = default_project()
    project["trackAsset"] = upload["id"]
    client.put("/api/project", json={"baseRevision": 0, "project": project})
    client.app.state.store.asset_path(upload["id"]).unlink()
    assert client.get("/api/project").status_code == 404
    with client.app.state.store.connect() as db:
        assert db.execute("SELECT revision FROM project").fetchone()[0] == 1


def test_invalid_project_shape_is_not_persisted(client):
    project = default_project()
    project["titles"] = [project["titles"][0]]
    assert client.put("/api/project", json={"baseRevision": 0, "project": project}).status_code == 422
    assert client.get("/api/project").json()["revision"] == 0
    project = default_project()
    project["layouts"]["16:9"]["track"]["scale"] = 0
    assert client.put("/api/project", json={"baseRevision": 0, "project": project}).status_code == 422


def test_mask_requires_matching_original_coordinates(client):
    track = client.post("/api/assets", files={"file": ("track.png", valid_png(), "image/png")}).json()
    wrong = io.BytesIO()
    Image.new("L", (3, 7), 128).save(wrong, "PNG")
    result = client.post("/api/masks/" + track["id"], files={"file": ("mask.png", wrong.getvalue(), "image/png")})
    assert result.status_code == 400
    assert "尺寸" in result.json()["detail"]
    assert client.get("/api/project").json()["revision"] == 0


def test_jpeg_orientation_is_normalized_and_pixels_survive_upload(client):
    raw = io.BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (24, 12), "red").save(raw, "JPEG", exif=exif)
    result = client.post("/api/assets", files={"file": ("portrait.jpg", raw.getvalue(), "image/jpeg")})
    assert result.status_code == 200
    assert (result.json()["width"], result.json()["height"]) == (12, 24)
