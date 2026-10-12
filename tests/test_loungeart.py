from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from desk_pet_grok import loungeart as LA


def test_pingpong_is_a_seamless_loop():
    seq = [LA.pingpong(i, 7) for i in range(24)]
    assert seq[:13] == [0, 1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1, 0]
    assert seq[12:24] == seq[0:12]


def test_opacity_curves_hand_off_without_a_dip():
    assert LA.standing_opacity(0.0) == 1.0 and LA.standing_opacity(1.0) == 0.0
    assert LA.art_opacity(0.0) == 0.0 and LA.art_opacity(1.0) == 1.0
    # the standing figure only leaves once the lying art is (nearly) in: the figure never thins out mid hand-off
    assert min(LA.coverage(x / 200) for x in range(201)) > 0.93


def test_overlay_weights_map_sleep_ramp_through_half():
    w = LA.overlay_weights(0.25, 0.0)
    assert w["half"] == pytest.approx(0.5) and w["sleep"] == 0.0 and w["yawn"] == 0.0
    w = LA.overlay_weights(1.0, 0.0)
    assert w["half"] == 1.0 and w["sleep"] == 1.0
    assert LA.overlay_weights(0.0, 0.4)["yawn"] == 1.0


@pytest.mark.skipif(not LA.available(), reason="lounge art missing")
def test_art_loads_all_poses_and_ledge_is_the_bottom_row():
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    art = LA.LoungeArt()
    assert set(art._src) >= {"base", "half", "yawn", "sleep"}
    w, h = 266, 220
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    art.paint(p, w, h, 1.0, 1.0, 0.0, 0.0)
    p.end()
    rows = [y for y in range(h) if any((img.pixel(x, y) >> 24) & 255 > 128 for x in range(0, w, 2))]
    assert rows, "nothing drawn"
    expect = h * (1 - 12 / 470) + 0.008 * h
    assert abs(rows[-1] - expect) <= 3  # sprite bottom row sits on the ledge line (window top edge anchor)
    assert rows[0] > 2  # head fits inside the window
    cols = [x for x in range(w) if any((img.pixel(x, y) >> 24) & 255 > 128 for y in range(0, h, 2))]
    assert cols[0] >= 0 and cols[-1] <= w - 1


@pytest.mark.skipif(not LA.available(), reason="lounge art missing")
def test_poses_differ_and_flick_frames_exist():
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    art = LA.LoungeArt()

    def render(loaf, droop, yawn):
        img = QImage(266, 220, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        art.paint(p, 266, 220, 1.0, loaf, droop, yawn)
        p.end()
        return img

    base, sleep, yawn = render(1, 0, 0), render(1, 1, 0), render(1, 0, 1)
    assert base != sleep and base != yawn and sleep != yawn
    art.set_pose(1.0, 0.0, 0.0)
    art.t = art.next_flick + 0.1
    art.step(0.05)
    assert art.flick_t >= 0 and art.frame_index() >= art.nb  # flick frames 7..10
    art.set_pose(1.0, 0.6, 0.0)
    assert art.frame_index() < art.nb  # never during half/sleep overlays


@pytest.mark.skipif(not LA.available(), reason="lounge art missing")
def test_pet25d_uses_art_and_falls_back_when_missing(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from desk_pet_grok.pet25d import Pet25D

    pet = Pet25D()
    pet.set_lounge((1.0, 0.0, 0.0))
    if pet._rig is not None:
        assert pet._lounge_art is not None
    pet.set_lounge(None)
    pet2 = Pet25D()
    monkeypatch.setattr(LA, "available", lambda root=None: False)
    pet2.set_lounge((1.0, 0.0, 0.0))
    assert pet2._lounge_art is None  # old squashed loaf stays as the fallback
    pet2.resize(266, 220)
    pet2.grab()  # paints without the art
