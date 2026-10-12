"""fall fix: face / mood / happy layers follow the figure's opacity, so no eyes-only afterimage during the lie-down <-> stand hand-off."""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from PySide6.QtGui import QImage, QPainter  # noqa: E402


def _alpha_max(rig, op, w=360, h=470):
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setOpacity(op)
    rig.paint(p, w, h, 1.0)
    p.end()
    a = np.frombuffer(img.constBits(), np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :w, 3]
    return int(a.max())


@pytest.mark.parametrize("face", ["calm", "surprised", "annoyed", "happy", "pouty"])
@pytest.mark.parametrize("happy", [0.0, 0.6, 1.0])
def test_rig_layers_follow_painter_opacity(qapp, face, happy):
    from desk_pet_grok import partrig
    rig = partrig.PartRig()
    rig.mood_mix = (face, face, 1.0)
    rig.happy = happy
    for op in (0.2, 0.3):
        # overlapping translucent layers (head, hair, ears, face) add up to at most 1-(1-op)^4; a face layer drawn at full opacity would hit 255
        assert _alpha_max(rig, op) <= int(255 * (1 - (1 - op) ** 4)) + 10, (face, happy, op)
    assert _alpha_max(rig, 1.0) >= 250


def test_work_body_and_face_fade_together(qapp):
    from desk_pet_grok import partrig
    rig = partrig.PartRig()
    rig.set_work_body("read", 1.0)
    rig.mood_mix = ("happy", "happy", 1.0)
    assert _alpha_max(rig, 0.2) <= int(255 * (1 - 0.8 ** 4)) + 10


def test_lounge_handoff_frames_have_no_opaque_face(qapp, tmp_path):
    """Every frame of lie-down -> stand-up with face layers active: the pixels above the faded-out figure never exceed ~its opacity."""
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    w = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "mood": True, "window_height": 400})
    w._motion_timer.stop()
    w.show()
    pet = w._pet
    pet.set_lounge((0.0, 0.0, 0.0))
    pet._mood_on = True
    pet._apply_face("surprised")
    h = pet.height()
    worst = 0
    for i in range(50):
        loaf = max(0.0, 1.0 - i / 30.0)
        pet.set_lounge((loaf, 0.0, 0.0))
        pet.set_fall(min(1.0, i / 15.0), 1.0, 1.0)
        pet._happy = 0.8 if 8 < i < 35 else 0.0
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
        img = pet.grab().toImage()
        # head region (upper 45 % of the window): standing rig fades with stand = 1 - 2 loaf; the lounge art is drawn separately,
        # so only check frames where the lounge art is still invisible-ish (loaf < 0.25) -> face must not exceed the standing opacity
        if loaf < 0.25:
            stand = max(0.0, 1.0 - 2.0 * loaf)
            a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)[: int(h * 0.45), :, 3]
            worst = max(worst, a.max() / 255.0 - (1 - (1 - stand) ** 4))
    assert worst < 0.06, worst
    w.close()
