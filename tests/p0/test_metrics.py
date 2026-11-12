import numpy as np
from PIL import Image
import pytest

from experiments.p0 import quality_metrics, cutout, decode_image, structural_mask


def test_quality_measures_false_positive_and_missing_track_independently():
    truth = Image.fromarray(np.array([[255, 255, 0], [255, 0, 0]], dtype=np.uint8))
    guess = Image.fromarray(np.array([[255, 0, 255], [255, 0, 0]], dtype=np.uint8))
    metrics = quality_metrics(guess, truth)
    assert metrics["track_recall"] == pytest.approx(2 / 3)
    assert metrics["background_residual"] == pytest.approx(1 / 3)
    assert metrics["intersection_over_union"] == pytest.approx(.5)


@pytest.mark.parametrize("value", [0, 255])
def test_metrics_reject_uninformative_ground_truth(value):
    with pytest.raises(ValueError, match="track and background"):
        quality_metrics(Image.new("L", (3, 3)), Image.new("L", (3, 3), value))


def test_metrics_do_not_resize_misaligned_annotation():
    with pytest.raises(ValueError, match="sizes differ"):
        quality_metrics(Image.new("L", (3, 3)), Image.new("L", (4, 4)))


def test_mask_retains_original_transparency_and_color():
    source = Image.new("RGBA", (2, 1))
    source.putdata([(42, 80, 100, 0), (30, 60, 90, 128)])
    mask = Image.new("L", (2, 1), 255)
    result = cutout(source, mask)
    assert np.asarray(result).tolist() == [[[42, 80, 100, 0], [30, 60, 90, 128]]]


def test_cutout_does_not_accept_wrong_coordinate_system():
    with pytest.raises(ValueError, match="sizes differ"):
        cutout(Image.new("RGBA", (2, 1)), Image.new("L", (1, 2)))


def test_bad_image_and_overlimit_are_rejected():
    with pytest.raises(ValueError, match="Invalid image"):
        decode_image(b"not an image")
    with pytest.raises(ValueError, match="exceeds"):
        decode_image(b"0" * 10_000_001)


def test_structural_candidate_has_native_dimensions_without_modifying_source():
    source = Image.new("RGBA", (133, 97), (90, 30, 140, 255))
    before = source.tobytes()
    mask = structural_mask(source)
    assert mask.size == source.size
    assert mask.mode == "L"
    assert source.tobytes() == before
