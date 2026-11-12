from pathlib import Path
import time

from PIL import Image

from backend.app.jobs import Jobs
from backend.app.storage import Store
from backend.app.schema import Project, default_project

ROOT = Path(__file__).resolve().parents[2]


def wait(jobs, job_id):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        job = jobs.get(job_id)
        if job["status"] != "running":
            return job
        time.sleep(.05)
    raise AssertionError("Recognition job did not finish")


def test_real_inference_outputs_original_coordinate_mask_and_keeps_project(tmp_path):
    store = Store(tmp_path)
    asset = store.put_image((ROOT / "test-assets/reference/sample-09.png").read_bytes())
    jobs = Jobs(store)
    try:
        job = wait(jobs, jobs.start(asset["id"])["id"])
        assert job["status"] == "succeeded", job
        assert job["result"]["kind"] == "mask"
        assert (job["result"]["width"], job["result"]["height"]) == (1406, 1123)
        assert store.load()["revision"] == 0
    finally:
        jobs.close()


def test_cancel_discards_late_output_and_next_job_can_run(tmp_path):
    store = Store(tmp_path)
    asset = store.put_image((ROOT / "test-assets/reference/sample-09.png").read_bytes())
    jobs = Jobs(store)
    try:
        first = jobs.start(asset["id"])
        assert jobs.cancel(first["id"])["status"] == "cancelled"
        assert jobs.get(first["id"])["result"] is None
        second = wait(jobs, jobs.start(asset["id"])["id"])
        assert second["status"] == "succeeded"
        assert jobs.get(first["id"])["status"] == "cancelled"
    finally:
        jobs.close()


def test_missing_model_failure_preserves_existing_saved_mask(tmp_path):
    store = Store(tmp_path)
    source = store.put_image((ROOT / "test-assets/reference/sample-09.png").read_bytes())
    previous = store.put_pixels(Image.new("L", (1406, 1123), 90), "mask")
    project = default_project()
    project.update(trackAsset=source["id"], maskAsset=previous["id"], baseMaskAsset=previous["id"], removeBackground=True)
    store.save(0, Project.model_validate(project))
    jobs = Jobs(store, tmp_path / "missing.onnx")
    try:
        result = wait(jobs, jobs.start(source["id"])["id"])
        assert result["status"] == "failed"
        assert result["error"]
        assert store.load()["project"]["maskAsset"] == previous["id"]
    finally:
        jobs.close()
