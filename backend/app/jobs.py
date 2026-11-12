from __future__ import annotations

import multiprocessing
from pathlib import Path
import threading
import uuid

from PIL import Image
from experiments.p0 import resource_root
from .recognition import track_mask
from .storage import Store


def infer_worker(source: str, model: str, destination: str) -> None:
    with Image.open(source) as image:
        image.load()
        mask = track_mask(image, Path(model))
    mask.save(destination, "PNG")


class Jobs:
    def __init__(self, store: Store, model: Path | None = None):
        self.store = store
        self.model = model or resource_root() / "models/u2netp.onnx"
        self.records: dict[str, dict] = {}
        self.lock = threading.RLock()
        self.directory = store.directory / "jobs"
        self.directory.mkdir(exist_ok=True)

    def start(self, source: str) -> dict:
        info = self.store.asset_info(source)
        if info["kind"] != "image":
            raise ValueError("识别输入必须是轨道原始图片")
        with self.lock:
            for job_id in list(self.records):
                if self.records[job_id]["status"] == "running":
                    self.cancel(job_id)
            job_id = uuid.uuid4().hex
            output = self.directory / f"{job_id}.png"
            process = multiprocessing.get_context("spawn").Process(
                target=infer_worker, args=(str(self.store.asset_path(source)), str(self.model), str(output)), daemon=True)
            process.start()
            self.records[job_id] = {"id": job_id, "source": source, "status": "running", "process": process,
                                    "output": output, "result": None, "error": None}
            return self.public(self.records[job_id])

    @staticmethod
    def public(record: dict) -> dict:
        return {key: record[key] for key in ("id", "source", "status", "result", "error")}

    def get(self, job_id: str) -> dict:
        with self.lock:
            if job_id not in self.records:
                raise FileNotFoundError("识别任务不存在")
            record = self.records[job_id]
            process = record["process"]
            if record["status"] == "running" and not process.is_alive():
                process.join()
                if process.exitcode == 0 and record["output"].is_file():
                    try:
                        with Image.open(record["output"]) as mask:
                            source = self.store.asset_info(record["source"])
                            if mask.size != (source["width"], source["height"]):
                                raise ValueError("识别结果尺寸错误")
                            record["result"] = self.store.put_pixels(mask.convert("L"), "mask")
                        record["status"] = "succeeded"
                    except (OSError, ValueError) as error:
                        record["status"], record["error"] = "failed", str(error)
                else:
                    record["status"], record["error"] = "failed", "识别失败，请重试；原始图片与已有修正仍保留"
                process.close()
                record["process"] = None
                record["output"].unlink(missing_ok=True)
            return self.public(record)

    def latest(self, source: str) -> dict | None:
        with self.lock:
            for record in reversed(list(self.records.values())):
                if record["source"] == source:
                    return self.get(record["id"])
        return None

    def cancel(self, job_id: str) -> dict:
        with self.lock:
            if job_id not in self.records:
                raise FileNotFoundError("识别任务不存在")
            record = self.records[job_id]
            if record["status"] == "running":
                process = record["process"]
                if process.is_alive():
                    process.terminate()
                process.join(timeout=10)
                process.close()
                record["process"] = None
                record["status"] = "cancelled"
                record["output"].unlink(missing_ok=True)
            return self.public(record)

    def close(self) -> None:
        with self.lock:
            for job_id in self.records:
                self.cancel(job_id)
