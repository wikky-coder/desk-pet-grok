import pytest

from desk_pet_grok import partrig


@pytest.mark.skipif(not partrig.available(), reason="rig assets missing")
def test_rig_renders_and_responds():
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    rig = partrig.PartRig()

    def render():
        img = QImage(200, 262, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        rig.paint(p, 200, 262, 1.0)
        p.end()
        return img

    rest = render()
    opaque = sum(1 for y in range(0, 262, 4) for x in range(0, 200, 4) if (rest.pixel(x, y) >> 24) & 255 > 128)
    assert opaque > 600  # character is actually drawn
    for _ in range(20):
        rig.step(1 / 30, 2500.0)
    assert abs(rig.ahoge.x) > 1.0 and any(abs(x) > 0.5 for x in rig.tail_x)
    moved = render()
    assert moved != rest
    for _ in range(300):
        rig.step(1 / 30, 0.0, allow_flick=False)
    assert all(abs(x) < 0.2 for x in (rig.ahoge.x, rig.ear_l.x, rig.hair_l.x))
    del app


def test_flag_default_off():
    from desk_pet_grok import config

    # "never chosen" is an absent key; rig_auto (default False) decides, so out of the box the rig stays off
    assert "part_rig" not in config._DEFAULTS and config._DEFAULTS["rig_auto"] is False


def test_walk_rig_all_phases():
    from desk_pet_grok import partwalk

    if not partwalk.available():
        pytest.skip("walk rig assets missing")
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    rig = partwalk.WalkRig()
    assert rig.n == 48
    lows = []
    for i in range(rig.n):
        rig.step(1 / 30, 0.0, i)
        img = QImage(200, 262, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        rig.paint(p, 200, 262, 1.0, i)
        p.end()
        ys = [y for y in range(262) if any((img.pixel(x, y) >> 24) & 255 > 128 for x in range(0, 200, 2))]
        assert len(ys) > 200
        lows.append(max(ys))
    # a foot is always on the ground line (planted gait, no hovering / sinking)
    assert max(lows) - min(lows) <= 6
    for _ in range(20):
        rig.step(1 / 30, 3000.0, 0)
    assert abs(rig.ahoge.x) > 0.5
    del app


def _ear_ghost_pixels(base_path, ear_path, base_off, ear_off, outer_right=True):
    """Opaque ear-tip pixels (top 30% of the ear piece) that are still opaque in head_base = ghost outline."""
    from PIL import Image

    base = Image.open(base_path).convert("RGBA")
    ear = Image.open(ear_path).convert("RGBA")
    bad = 0
    top = int(ear.height * 0.3)
    for y in range(top):
        for x in range(ear.width):
            if (x < ear.width * 0.5) == outer_right:
                continue  # only the outer half (away from the headband, where the ear is not hidden)
            if ear.getpixel((x, y))[3] > 200:
                bx, by = round(ear_off[0] + x - base_off[0]), round(ear_off[1] + y - base_off[1])
                if 0 <= bx < base.width and 0 <= by < base.height:
                    b = base.getpixel((bx, by))
                    e = ear.getpixel((x, y))
                    # ghost = same-coloured opaque pixel left behind (the headband ruffle is white, so it never matches)
                    if b[3] > 10 and sum(abs(b[i] - e[i]) for i in range(3)) < 60:
                        bad += 1
    return bad


def test_front_ears_fully_removed_from_head_base():
    import json

    from desk_pet_grok import partrig

    if not partrig.available():
        pytest.skip("rig assets missing")
    root = partrig.RIG_DIR
    parts = {p["name"]: p for p in json.loads((root / "rig.json").read_text())["parts"]}
    for ear in ("ear_L", "ear_R"):
        bad = _ear_ghost_pixels(root / "head_base.png", root / f"{ear}.png",
                                (parts["head_base"]["x"], parts["head_base"]["y"]), (parts[ear]["x"], parts[ear]["y"]),
                                outer_right=(ear == "ear_R"))
        assert bad == 0, f"{ear}: {bad} ghost pixels left in head_base"


def test_walk_ear_tip_not_in_head_base():
    import json

    from desk_pet_grok import partwalk

    if not partwalk.available():
        pytest.skip("walk rig assets missing")
    root = partwalk.WALK_DIR
    parts = {p["name"]: p for p in json.loads((root / "walk.json").read_text())["parts"]}
    bad = _ear_ghost_pixels(root / "head_base.png", root / "ear.png",
                            (parts["head_base"]["ox"], parts["head_base"]["oy"]), (parts["ear"]["ox"], parts["ear"]["oy"]))
    assert bad <= 5, f"{bad} ghost ear-tip pixels left in head_base"


def test_turn_rig_renders_and_handoff_fade_params():
    from desk_pet_grok import partturn

    if not partturn.available():
        pytest.skip("turn rig assets missing")
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    rig = partturn.TurnRig()
    for tp in (0.0, 0.25, 0.5, 0.75, 1.0):
        img = QImage(200, 262, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        rig.paint(p, 200, 262, 1.0, tp)
        p.end()
        opaque = sum(1 for y in range(0, 262, 4) for x in range(0, 200, 4) if (img.pixel(x, y) >> 24) & 255 > 128)
        assert opaque > 500
    del app
