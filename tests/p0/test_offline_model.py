import socket
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from experiments.p0 import saliency_mask, validate_model

ROOT = Path(__file__).resolve().parents[2]


def test_model_checksum_and_missing_or_modified_model(tmp_path):
    validate_model(ROOT / "models/u2netp.onnx")
    with pytest.raises(FileNotFoundError):
        validate_model(tmp_path / "missing.onnx")
    corrupt = tmp_path / "modified.onnx"
    corrupt.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        validate_model(corrupt)


def test_real_model_inference_uses_no_network(monkeypatch):
    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("Offline inference attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", network_forbidden)
    with Image.open(ROOT / "test-assets/reference/user-reference.png") as source:
        mask = saliency_mask(source, ROOT / "models/u2netp.onnx")
        values = np.asarray(mask)
        assert mask.size == source.size
        assert values.max() > values.min()
        assert np.isfinite(values).all()
