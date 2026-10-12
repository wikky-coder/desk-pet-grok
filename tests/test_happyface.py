"""Standing head-pat: the generated 'enjoying it' face layer (assets/rig25d/face_happy.png)."""
import os
import shutil
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import mkwin, qapp  # noqa: E402,F401

from desk_pet_grok import eyefx, partrig  # noqa: E402

RIG = partrig.RIG_DIR


def test_face_layer_matches_head_box_and_is_soft_edged():
    hb = Image.open(RIG / "head_base.png"); fh = Image.open(RIG / "face_happy.png")
    assert fh.size == hb.size and fh.mode == "RGBA"
    a = np.array(fh)[..., 3].astype(int)
    assert a[:, :2].max() == 0 and a[:, -2:].max() == 0 and a[:2].max() == 0 and a[-2:].max() == 0  # no hard cut at the layer border
    assert a[330, 230] == 255 and a[330, 360] == 255  # eye centres fully replaced
    assert a[:230].max() == 0  # hair / headband / ears untouched
    hb_a = np.array(hb)[..., 3]
    assert (a[hb_a < 10] > 0).sum() == 0  # never paints outside the head silhouette (no white / halo edge)
    ys, xs = np.where(a > 0)
    assert 240 <= ys.min() and ys.max() <= 460 and xs.min() >= 70 and xs.max() <= 520


def test_closed_eye_pixels_are_one_arc_each_no_pupil_colour():
    px = np.array(Image.open(RIG / "face_happy.png").convert("RGBA")).astype(int)
    amber = (px[..., 0] > 190) & (px[..., 1] > 110) & (px[..., 1] < 180) & (px[..., 2] < 100) & (px[..., 3] > 200)
    assert amber[300:400, 190:460].sum() < 60  # no orange iris left in the closed eyes
    dark = (px[..., :3].sum(2) < 180) & (px[..., 3] > 200)
    for lo, hi in ((195, 280), (330, 450)):  # one eye each: a single thin band of lash pixels, no big dark block
        rows = np.where(dark[285:385, lo:hi].sum(1) >= 5)[0]
        assert 0 < len(rows) and rows.max() - rows.min() <= 36 and len(rows) <= 36


def _petted(w, secs, on=True):
    pet = w._pet
    pet.set_petting(on)
    for _ in range(int(secs * 60)):
        pet.drive(1 / 60.0, want_walk=False, facing=1, look=False, dragging=False)
    return pet


def test_happy_fades_in_0p2s_and_out_0p25s(qapp):
    w = mkwin(qapp, part_rig=True); w._motion_timer.stop()
    pet = w._pet
    assert pet._rig is not None or pet._ensure_rig()
    assert pet._rig.has_happy_face()
    _petted(w, 0.1)
    assert 0.3 < pet._happy < 0.7
    _petted(w, 0.12)
    assert pet._happy == pytest.approx(1.0)
    _petted(w, 0.12, on=False)
    assert 0.3 < pet._happy < 0.7
    _petted(w, 0.15, on=False)
    assert pet._happy == pytest.approx(0.0)


def test_eye_overlay_is_off_while_the_face_layer_is_up(qapp, monkeypatch):
    w = mkwin(qapp, part_rig=True); w._motion_timer.stop()
    calls = []
    monkeypatch.setattr(eyefx, "apply", lambda *a, **k: calls.append(k.get("squint")))
    _petted(w, 0.5); w._pet.grab()
    calls.clear(); w._pet.update(); w._pet.grab()
    assert calls == []


def test_falls_back_to_eyefx_when_face_asset_missing(qapp, monkeypatch):
    monkeypatch.setattr(partrig.PartRig, "has_happy_face", lambda self: False)
    w = mkwin(qapp, part_rig=True); w._motion_timer.stop()
    calls = []
    real = eyefx.apply
    monkeypatch.setattr(eyefx, "apply", lambda *a, **k: (calls.append(k.get("squint")), real(*a, **k))[1])
    pet = _petted(w, 0.5)
    assert pet._happy == 0.0
    pet.grab()
    assert calls and max(calls) > 0.5


def test_rig_without_face_file_loads_fine(tmp_path):
    for f in RIG.iterdir():
        if f.is_file() and f.name != "face_happy.png":
            shutil.copy(f, tmp_path / f.name)
    r = partrig.PartRig(tmp_path)
    assert not r.has_happy_face()


def test_lid_reveal_sweeps_top_down_without_blending_layers(qapp):
    from PySide6.QtGui import QImage
    r = partrig.PartRig()
    fim, k = r._get("face_happy", 940)
    top = r._lid_reveal(fim, k, 0.10)
    full = np.frombuffer(fim.constBits(), np.uint8).reshape(fim.height(), fim.bytesPerLine() // 4, 4)
    cut = np.frombuffer(top.constBits(), np.uint8).reshape(top.height(), top.bytesPerLine() // 4, 4)
    y_eye, y_chin = int(330 * k), int(405 * k)
    assert cut[y_chin, :, 3].max() == 0 and full[y_chin, :, 3].max() > 0  # lower face not yet revealed
    assert (cut[int(300 * k), :, 3] == full[int(300 * k), :, 3]).all() or cut[int(300 * k), :, 3].sum() > 0
    late = r._lid_reveal(fim, k, 0.60)
    assert np.frombuffer(late.constBits(), np.uint8).reshape(late.height(), late.bytesPerLine() // 4, 4)[y_chin, :, 3].max() > 0
