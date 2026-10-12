import os

from PIL import Image

from desk_pet_grok import screen_mac as sm


def test_parse_lsappinfo():
    assert sm.parse_lsappinfo_name('"LSDisplayName"="Safari"\n') == "Safari"
    assert sm.parse_lsappinfo_name('"LSDisplayName" = "微信"') == "微信"
    assert sm.parse_lsappinfo_name("") is None


def test_shrink_jpeg_long_side_and_cleanup(tmp_path):
    p = tmp_path / "r.png"
    Image.new("RGB", (2880, 1800), (10, 120, 200)).save(p)
    data = sm.shrink_jpeg(str(p), str(tmp_path))
    import io
    im = Image.open(io.BytesIO(data))
    assert im.format == "JPEG" and max(im.size) == 768


def test_non_mac_is_safe():
    if not sm.IS_MAC:
        assert sm.front_context() is None and sm.capture_jpeg() is None and sm.has_screen_permission() is False
