import threading
import time

import numpy as np
from PIL import Image

from backend.android_server import ThreadJobs
from backend.app.storage import Store
from experiments.p0 import resource_root, saliency_mask


def test_android_inference_path_keeps_the_existing_model_pre_and_postprocessing(monkeypatch):
    import onnxruntime as ort
    import backend.android_inference

    model = resource_root() / 'models/u2netp.onnx'
    values = np.zeros((120, 160, 3), dtype=np.uint8)
    values[:, :, 0] = np.arange(160)
    values[20:100, 30:130, 1:] = (190, 230)
    image = Image.fromarray(values)
    expected = saliency_mask(image, model)
    observed = []

    def native_engine(tensor, path):
        assert path == model and tensor.shape == (1, 3, 320, 320)
        assert tensor.dtype == np.float32 and tensor.flags.c_contiguous
        observed.append(True)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        session = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
        return session.run(None, {session.get_inputs()[0].name: tensor})[0][0, 0]

    monkeypatch.setattr(backend.android_inference, 'predict', native_engine)
    monkeypatch.setenv('ADOFAI_ANDROID', '1')
    actual = saliency_mask(image, model)
    assert observed == [True]
    assert actual.size == image.size and actual.tobytes() == expected.tobytes()


def test_cancelled_android_job_cannot_save_a_late_mask(tmp_path, monkeypatch):
    import backend.app.recognition

    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def delayed(image, _model):
        started.set()
        assert release.wait(5)
        finished.set()
        return Image.new('L', image.size, 255)

    monkeypatch.setattr(backend.app.recognition, 'track_mask', delayed)
    store = Store(tmp_path)
    asset = store.put_pixels(Image.new('RGBA', (64, 64), 'red'), 'image')
    before = set((tmp_path / 'assets').iterdir())
    jobs = ThreadJobs(store, resource_root() / 'models/u2netp.onnx')
    try:
        job = jobs.start(asset['id'])
        assert started.wait(5)
        assert jobs.cancel(job['id'])['status'] == 'cancelled'
        release.set()
        assert finished.wait(5)
        jobs.records[job['id']]['future'].result(timeout=5)
        assert jobs.get(job['id'])['result'] is None
        assert jobs.get(job['id'])['status'] == 'cancelled'
        assert set((tmp_path / 'assets').iterdir()) == before
        assert store.load()['revision'] == 0
    finally:
        release.set()
        jobs.close()
