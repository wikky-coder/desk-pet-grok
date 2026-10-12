"""fallfix2: real running path (window + lounge driver + edge drop, the user's settings). The window mask only keeps pixels with alpha >= 50 %,
so mid hand-off the figure must never thin out (that left floating eyes / fragments): opaque pixel count stays near the standing figure's."""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from PySide6.QtGui import QImage  # noqa: E402


def _alpha(img):
    return np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[:, :img.width(), 3]


def _fall_frames(tmp_path, variant=None, sleep=False):
    from desk_pet_grok.focus_probe import FakeProbe, FieldGeom
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "lounge_variants": True, "mood": True, "look_at_mouse": True,
                                                            "tail_boost": True, "rig_auto": False, "window_height": 220})
    win._motion_timer.stop()
    win.show()
    win.set_lounge(True, persist=False)
    pet, drv = win._pet, win._lounge
    drv.probe = FakeProbe([FieldGeom(200, 600, 900, 500)])
    win.move(500, 600 - win.height() + 10)
    assert drv.on_drop()
    pet.set_gaze_enabled(True)

    def tick():
        drv._poll()
        drv.tick(1 / 60)
        pet.set_gaze(0.7, -0.4)

    for _ in range(60 * 3):
        tick()
    if variant:
        pet._var_start(variant, instant=True)
        for _ in range(20):
            tick()
    if sleep:
        drv.lounge.t_lounge = 1e6
        for _ in range(60 * 3):
            tick()
    lying = (_alpha(pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)) >= 128).sum()
    drv.probe = FakeProbe([FieldGeom(200, 1400, 900, 500)])
    counts = []
    for i in range(60 * 2):
        tick()
        img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        counts.append(int((_alpha(img) >= 128).sum()))
        if drv.lounge.state == "idle" and i > 30:
            break
    win.close()
    return int(lying), counts


@pytest.mark.parametrize("variant,sleep", [(None, False), ("side", False), ("chin", True), ("curl", True), ("stretch", False)])
def test_fall_never_thins_out(qapp, tmp_path, variant, sleep):
    lying, counts = _fall_frames(tmp_path, variant, sleep)
    stand = max(counts[-10:])
    assert stand > 3000
    ref = min(stand, lying)
    assert all(c > 0.6 * ref for c in counts[1:]), (variant, sleep, [c for c in counts if c <= 0.6 * ref])
