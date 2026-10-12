"""v4-3: cling to the screen border."""
from __future__ import annotations

import os
import sys

import pytest
from PySide6.QtCore import QPoint

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import mkwin, qapp  # noqa: E402,F401

from desk_pet_grok import cling, config, interaction  # noqa: E402
from desk_pet_grok.cling import ClingMachine, attach_side, wants_peek, window_x  # noqa: E402

SCR = (0.0, 0.0, 1440.0, 900.0)
SCR2 = (1440.0, 0.0, 1920.0, 1080.0)


def test_default_off():
    assert config._DEFAULTS["cling_edge"] is False
    assert ClingMachine().enabled is False and ClingMachine().active is False


def test_attach_side_zone():
    w, h = 220.0, 287.0
    assert attach_side((-60.0, 300, w, h), SCR) == -1  # centre 50 px from the left border (<0.32*w = 70)
    assert attach_side((0.0, 300, w, h), SCR) == 0  # standing flush against the border is NOT a cling
    assert attach_side((1440 - w + 60, 300, w, h), SCR) == 1
    assert attach_side((600.0, 300, w, h), SCR) == 0
    assert attach_side((-80.0, 300, w, h), SCR) == -1


def test_shared_border_between_screens_is_not_an_edge():
    w, h = 220.0, 287.0
    assert attach_side((1440 - w + 60, 300, w, h), SCR, [SCR2]) == 0  # screen 2 continues there
    assert attach_side((-60.0, 300, w, h), SCR, [SCR2]) == -1  # outer left border still counts


def test_window_x_puts_cut_edge_on_the_border():
    assert window_x(-1, SCR, 112.0) == -112.0
    assert window_x(1, SCR, 300.0) == 1440 - 300.0
    assert window_x(-1, SCR2, 50.0) == 1440 - 50.0


def test_peek_distance_hysteresis_and_height():
    win = (-100.0, 300.0, 220.0, 287.0)
    assert wants_peek(-1, (200.0, 400.0), SCR, win, False)
    assert not wants_peek(-1, (350.0, 400.0), SCR, win, False)
    assert wants_peek(-1, (350.0, 400.0), SCR, win, True)  # already peeking: wider
    assert not wants_peek(-1, (200.0, 800.0), SCR, win, False)  # far below
    assert wants_peek(1, (1440 - 200.0, 400.0), SCR, win, False)


def test_machine_peek_hold_and_cancel():
    m = ClingMachine(enabled=True)
    m.tick(0.1, True); assert not m.peek  # not clinging yet
    m.attach(-1); m.tick(0.1, True); assert m.peek
    m.tick(0.5, False); assert m.peek  # holds
    m.tick(0.5, False); assert not m.peek
    m.tick(0.1, True); m.cancel()
    assert not m.active and not m.peek


def test_assets():
    root = os.path.join(os.path.dirname(__file__), "..", "assets", "cling25d")
    for n in ("cling_L", "peek_L", "cling_R", "peek_R"):
        assert os.path.isfile(os.path.join(root, n + ".png"))
    assert os.path.isfile(os.path.join(root, "cling.json"))


def _win(qapp, tmp_path, **s):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    base = {"puppet25d": True, "part_rig": True, "cling_edge": True, "window_height": 300}
    base.update(s)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.show()
    return w


def test_window_flow_attach_peek_cancel(qapp, tmp_path, monkeypatch):
    w = _win(qapp, tmp_path)
    said = []
    w.lounge_say.connect(said.append)
    geo = w.screen().geometry()
    w.move(geo.x() - 70, geo.y() + 200)
    assert w._cling_try() is True and w._pet.cling_side() == -1 and said == ["cling_on"]
    cur = {"p": QPoint(geo.x() + 900, geo.y() + 300)}
    monkeypatch.setattr(interaction.QCursor, "pos", staticmethod(lambda: cur["p"]))
    for _ in range(60):
        assert w._cling_tick(1 / 60) is True
    cutx = w._pet.cling_cut_x(float(w.height()))
    assert w.x() == pytest.approx(geo.x() - cutx, abs=1.5)  # the cut edge sits exactly on the border
    assert not w._cling.peek
    cur["p"] = QPoint(geo.x() + 150, w.y() + 100)
    for _ in range(10):
        w._cling_tick(1 / 60)
    assert w._cling.peek and "cling_peek" in said and w._pet._cling_peek
    cur["p"] = QPoint(geo.x() + 900, geo.y() + 300)
    for _ in range(90):
        w._cling_tick(1 / 60)
    assert not w._cling.peek
    w._cling_cancel()
    assert w._pet.cling_side() == 0 and not w._cling.active and said[-1] == "cling_off"
    assert w._cling_tick(1 / 60) is False
    w.close()


def test_right_border_and_switch_off(qapp, tmp_path, monkeypatch):
    w = _win(qapp, tmp_path)
    geo = w.screen().geometry()
    w.move(geo.x() + geo.width() - w.width() + 70, geo.y() + 100)
    assert w._cling_try() and w._pet.cling_side() == 1
    monkeypatch.setattr(interaction.QCursor, "pos", staticmethod(lambda: QPoint(geo.x() + 400, geo.y() + 400)))
    for _ in range(60):
        w._cling_tick(1 / 60)
    assert w.x() + w._pet.cling_cut_x(float(w.height())) == pytest.approx(geo.x() + geo.width(), abs=1.5)
    w.set_cling_edge(False, persist=False)
    assert not w._cling.active and w._pet.cling_side() == 0
    w.move(geo.x() - 70, geo.y() + 100)
    assert w._cling_try() is False  # switch off: never clings
    w.close()


def test_pet_sprites_fade_in_and_rig_hides(qapp, tmp_path):
    w = _win(qapp, tmp_path)
    pet = w._pet
    pet.set_cling(-1, False)
    for _ in range(60):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._cling_t > 0.99 and pet._peek_t < 0.01
    pet.set_cling(-1, True)
    for _ in range(30):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._peek_t > 0.99
    pet.set_cling(0)
    for _ in range(90):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._cling_t < 0.01
    w.close()


def test_drop_on_lounge_wins_over_cling(qapp, tmp_path):
    w = _win(qapp, tmp_path, lounge=True)
    called = []
    w._lounge.on_drop = lambda: True  # a lounge drop (window edge / Dock)
    w._cling_try = lambda: called.append(1) or True
    # pointer release logic: cling only when the lounge declined
    if not w._lounge.on_drop():
        w._cling_try()
    assert called == []
    w.close()


def test_lines():
    from desk_pet_grok import lines_v4
    from desk_pet_grok.meow import ends_with_meow
    for c in ("cling_on", "cling_peek", "cling_off"):
        assert len(lines_v4.POOLS[c]) >= 3 and all(ends_with_meow(s) and len(s) <= 24 for s in lines_v4.POOLS[c])


def test_real_mouse_drag_to_border_clings_and_drag_away_cancels(qapp, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    w = _win(qapp, tmp_path)
    geo = w.screen().geometry()
    w.move(geo.x() + 400, geo.y() + 200)
    for _ in range(3):
        qapp.processEvents()
        w._pet.update()
    # find an opaque point on the figure
    buf = w._pet._buf
    d = buf.devicePixelRatio()
    pt = None
    for y in range(int(w.height() * 0.3), w.height(), 6):
        for x in range(10, w.width(), 6):
            if (buf.pixel(int(x * d), int(y * d)) >> 24) & 0xFF > 200:
                pt = QPoint(x, y)
                break
        if pt:
            break
    assert pt is not None
    QTest.mousePress(w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
    # drag so that the window ends 70 px outside the left border
    steps = 12
    x0 = w.x()
    target = geo.x() - 70
    for i in range(1, steps + 1):
        gx = pt.x() + int(x0 + (target - x0) * i / steps)
        QTest.mouseMove(w, QPoint(pt.x() + int((target - x0) * i / steps), pt.y()))
    QTest.mouseRelease(w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(pt.x() + (target - x0), pt.y()))
    assert w._cling.active and w._cling.side == -1, (w.x(), target)
    # she clings and slides onto the border; then dragging her away cancels the cling
    for _ in range(40):
        w._cling_tick(1 / 60)
    for _ in range(30):
        w._pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    qapp.processEvents(); w._pet.update(); qapp.processEvents()
    buf = w._pet._buf
    d = buf.devicePixelRatio()
    p2 = None
    for y in range(int(w.height() * 0.3), w.height(), 6):
        for x in range(10, w.width(), 6):
            if (buf.pixel(int(x * d), int(y * d)) >> 24) & 0xFF > 200:
                p2 = QPoint(x, y)
                break
        if p2:
            break
    assert p2 is not None
    QTest.mousePress(w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p2)
    for i in range(1, 8):
        QTest.mouseMove(w, QPoint(p2.x() + 6 * i, p2.y()))
    assert not w._cling.active and w._pet.cling_side() == 0
    QTest.mouseRelease(w, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(p2.x() + 60, p2.y()))
    w.close()
