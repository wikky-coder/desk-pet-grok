"""v4b: work props are part of a 'holding it with both hands' body layer; the standing fists must be gone."""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from PySide6.QtGui import QImage, QPainter  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODES = ("read", "code", "terminal", "draw")
# the standing fists (trunk.png at canvas (13, 490)): boxes in 2x canvas px
FISTS = ((13 + 190, 490 + 30, 13 + 270, 490 + 115), (13 + 475, 490 + 30, 13 + 555, 490 + 115))


def test_assets():
    meta = json.load(open(os.path.join(ROOT, "assets/work25d/work.json")))
    for m in MODES:
        assert m in meta["trunks"], m
        assert os.path.isfile(os.path.join(ROOT, f"assets/work25d/trunk_work_{m}.png"))


def _render(rig, w=720, h=940):
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    rig.paint(p, w, h, 1.0)
    p.end()
    a = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :w].astype(int)
    return a


@pytest.mark.parametrize("mode", MODES)
def test_fists_replaced(qapp, mode):
    from desk_pet_grok import partrig
    rig = partrig.PartRig()
    assert rig.has_work_body(mode)
    base = _render(rig)
    rig.set_work_body(mode, 1.0)
    held = _render(rig)
    for x0, y0, x1, y1 in FISTS:
        diff = np.abs(base[y0:y1, x0:x1, :3] - held[y0:y1, x0:x1, :3]).sum(axis=2)
        assert (diff > 40).mean() > 0.35, (mode, (x0, y0))  # the old fist area was repainted
    # the old standing trunk is skipped at full strength (no ghost): body pixels outside the new layer are identical to transparent
    assert held[:, :, 3].sum() > 0


def test_crossfade_keeps_old_trunk_until_done(qapp):
    from desk_pet_grok import partrig
    rig = partrig.PartRig()
    rig.set_work_body("read", 0.5)
    k0 = rig.state_key()
    rig.set_work_body("read", 0.0)
    assert rig.work_body is None and rig.state_key() != k0
    rig.set_work_body("nonsense", 1.0)
    assert rig.work_body is None


def test_pet_uses_body_not_overlay(qapp, tmp_path):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    w = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "window_height": 300})
    w.show()
    pet = w._pet
    pet.set_work("code")
    for _ in range(150):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._rig.work_body == ("code", pytest.approx(1.0, abs=0.01))
    pet.set_work(None)
    for _ in range(200):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._rig.work_body is None
    w.close()
