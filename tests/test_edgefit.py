"""Lying poses sit on the edge line (same baseline for every pose, <= 2 px off), and the window mask always matches the frame drawn."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from test_lounge_pet import _lie, _restore_cfg_env, needs_art, qapp  # noqa: E402,F401

from desk_pet_grok import loungeart  # noqa: E402


@needs_art
@pytest.mark.parametrize("H", [300, 500])
def test_every_pose_baseline_within_2px_of_the_edge_and_consistent(qapp, tmp_path, H):
    import render_edgefit as R
    win, drv = _lie(tmp_path)
    win._motion_timer.stop(); win.show()
    win.setMinimumSize(0, 0); win.setMaximumSize(4000, 4000); win.resize(int(H * 0.7659), H)
    qapp.processEvents(); win._pet.resize(win.size())
    devs = {}
    for var, name, pose in R.POSES:
        _img, dev, _edge = R.measure(win, win._pet, var, pose, H)
        devs[f"{var}/{name}"] = dev
    assert all(-0.5 <= d <= 2.5 for d in devs.values()), devs  # never floating, at most ~2 px pressed into the edge
    assert max(devs.values()) - min(devs.values()) <= 1.2, devs  # switching poses does not make the baseline jump


@needs_art
def test_base_offsets_and_sink():
    for n in loungeart.variant_names():
        a = loungeart.LoungeArt(loungeart.VARIANT_DIR / n)
        assert 0 <= a.base_off <= 8, (n, a.base_off)  # curl: the tail tip hangs a little below the body baseline
    assert 0 <= loungeart.LoungeArt().base_off <= 4
    for h in (150, 220, 500, 900):
        assert 1.0 <= loungeart.sink_px(h) <= 2.0


@needs_art
def test_mask_follows_the_drawn_frame_even_when_the_animation_key_would_not_change(qapp, tmp_path):
    from PySide6.QtGui import QBitmap, QRegion
    win, drv = _lie(tmp_path)
    win.show()
    pet = win._pet
    def sync():
        qapp.processEvents(); pet.repaint(); qapp.processEvents()
    sync()
    big = win.mask().boundingRect().height()
    pet._fall_sq = (1.15, 0.5)  # landing squash: same frame / loaf / droop, different pixels
    sync()
    squashed = win.mask().boundingRect().height()
    assert squashed < big - 20
    pet._fall_sq = (1.0, 1.0)
    sync()
    assert abs(win.mask().boundingRect().height() - big) <= 2
    am = QRegion(QBitmap.fromImage(pet._buf.createAlphaMask()))
    extra = win.mask().subtracted(am)  # only the thin grow-pad around the silhouette, never a block
    assert extra.boundingRect().height() <= am.boundingRect().height() + 2 * 4
    assert sum(r.width() * r.height() for r in win.mask().subtracted(am.united(am.translated(0, 2)).united(am.translated(0, -2)).united(am.translated(2, 0)).united(am.translated(-2, 0)))) == 0
