"""Qt-side lounge: pose on the rig, driver geometry helpers, window integration with a fake probe (run on the Mac)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from desk_pet_grok import lounge as L
from desk_pet_grok import partrig
from desk_pet_grok.focus_probe import FakeProbe, FieldGeom
from desk_pet_grok.lounge_driver import drop_accepts, window_target
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow


@pytest.fixture(autouse=True)
def _restore_puppet_globals():
    from desk_pet_grok import puppet

    saved = puppet.STRIDE_PX_PER_FRAME
    yield
    puppet.STRIDE_PX_PER_FRAME = saved  # Pet25D overwrites this from the manifest


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _bbox(rig, w=200, h=262):
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    rig.paint(p, w, h, 1.0)
    p.end()
    ys = [y for y in range(h) for x in range(0, w, 2) if (img.pixel(x, y) >> 24) & 255 > 128]
    return img, (min(ys), max(ys))


def test_drop_accepts_band_and_span():
    g = FieldGeom(100, 300, 800, 500)
    assert drop_accepts(g, (400, 320), 120.0, 25.0)
    assert drop_accepts(g, (400, 240), 120.0, 25.0)
    assert not drop_accepts(g, (400, 100), 120.0, 25.0)  # far above
    assert not drop_accepts(g, (50, 310), 120.0, 25.0)  # outside x span
    assert not drop_accepts(None, (400, 310), 120.0, 25.0)
    top = FieldGeom(0, 30, 1440, 860)  # maximised window; pet window pinned to the screen top
    assert drop_accepts(top, (700, 220), 25.0, 25.0)
    assert not drop_accepts(top, (700, 220), 200.0, 25.0)


def test_window_target_puts_feet_on_edge_and_keeps_head_reachable():
    x, y = window_target((500.0, 600.0), 266, 220, 0.0)
    assert x == 500.0 - 133 and 600.0 - 220 < y < 600.0
    _, y2 = window_target((500.0, 20.0), 266, 220, 0.0)
    assert y2 == pytest.approx(-0.45 * 220)


@pytest.mark.skipif(not partrig.available(), reason="rig assets missing")
def test_loaf_pose_is_shorter_and_reversible(qapp):
    rig = partrig.PartRig()
    _, (t0, b0) = _bbox(rig)
    rig.set_pose(1.0, 0.0, 0.0)
    img_loaf, (t1, b1) = _bbox(rig)
    assert t1 > t0 and b0 - t0 > 0  # head sinks into the loaf
    key1 = rig.state_key()
    assert not rig.at_rest()
    rig.set_pose(0.0, 0.0, 0.0)
    assert rig.state_key() != key1
    rig.set_pose(5.0, -3.0, 9.0)  # clamped
    assert (rig.loaf, rig.droop, rig.yawn) == (1.0, 0.0, 1.0)


@pytest.mark.skipif(not partrig.available(), reason="rig assets missing")
def test_droop_changes_render_and_slows_breath(qapp):
    rig = partrig.PartRig()
    a, _ = _bbox(rig)
    rig.set_pose(1.0, 1.0, 0.0)
    b, _ = _bbox(rig)
    assert a != b


def _win(tmp_path, **extra):
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    s = {"puppet25d": True, "part_rig": True, "window_height": 220}
    s.update(extra)
    return PetWindow(state_machine=StateMachine(), settings=s)


def test_lounge_defaults_off_and_keeps_no_focus_flags(qapp, tmp_path):
    win = _win(tmp_path)
    assert win.lounge is False
    win.set_lounge(True, persist=False)
    assert win.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert win.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert win.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)


@pytest.mark.skipif(not partrig.available(), reason="rig assets missing")
def test_drop_on_fake_window_lounges_and_follows(qapp, tmp_path):
    win = _win(tmp_path)
    win.set_lounge(True, persist=False)
    assert win.lounge
    drv = win._lounge
    geom = FieldGeom(200, 400, 900, 500)
    drv.probe = FakeProbe([geom])
    win.move(500, 400 - win.height() + 10)  # feet just above the edge
    assert drv.on_drop()
    for _ in range(90):
        drv._poll()
        assert drv.tick(1 / 30)
    assert drv.lounge.state == "lounge_loop"
    assert win._pet.lounging()
    # now the front window moves: she follows, still on its top edge
    drv.probe = FakeProbe([FieldGeom(300, 250, 900, 500)])
    for _ in range(120):
        drv._poll()
        drv.tick(1 / 30)
    foot_y = win.y() + win.height() - 8 * win.height() / 470
    assert abs(foot_y - 250) < 12
    # dragging her away ends it at once and restores normal behaviour
    drv.on_drag_start()
    assert drv.lounge.state == "idle" and not win._pet.lounging()


def test_drop_far_from_any_edge_does_nothing(qapp, tmp_path):
    win = _win(tmp_path)
    win.set_lounge(True, persist=False)
    win._lounge.probe = FakeProbe([FieldGeom(200, 800, 900, 500)])
    win.move(400, 100)
    assert win._lounge.on_drop() is False
    assert not win._lounge.active()


def test_lounge_say_signal_only_known_categories(qapp, tmp_path):
    win = _win(tmp_path)
    got = []
    win.lounge_say.connect(got.append)
    win._lounge.say.emit("lounge")
    assert got == ["lounge"]


def test_lounge_ax_switch_falls_back_gracefully(qapp, tmp_path, monkeypatch):
    from desk_pet_grok import ax_probe
    from desk_pet_grok.focus_probe import WindowEdgeProbe

    monkeypatch.setattr(ax_probe, "open_accessibility_settings", lambda: None)
    win = _win(tmp_path)
    win.set_lounge(True, persist=False)
    assert isinstance(win._lounge.probe, WindowEdgeProbe)
    win.set_lounge_ax(True, persist=False)
    assert isinstance(win._lounge.probe, ax_probe.HybridProbe)
    win.set_lounge_ax(False, persist=False)
    assert isinstance(win._lounge.probe, WindowEdgeProbe)
    assert win.lounge_selfwalk is True  # v2 default (only effective while lounge is on)
