from PIL import ImageFont

from experiments.static_track_probe import get_font


def test_android_tile_labels_use_bundled_scalable_font_instead_of_tiny_bitmap(monkeypatch):
    monkeypatch.setenv('ADOFAI_ANDROID','1')
    small,large=get_font(28),get_font(56)
    assert isinstance(small,ImageFont.FreeTypeFont)
    assert isinstance(large,ImageFont.FreeTypeFont)
    assert small.size==28 and large.size==56
    assert large.getlength('12345')>small.getlength('12345')*1.8
