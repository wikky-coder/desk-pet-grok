"""Dock as a lounge edge: pure geometry (fake screens / Dock windows) + driver behaviour with fake probes."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from PySide6.QtWidgets import QApplication

from desk_pet_grok import partrig
from desk_pet_grok.focus_probe import DockProbe, FakeProbe, FieldGeom, dock_drop_accepts, dock_from_screens
from desk_pet_grok.menu import PetMenuCallbacks, build_pet_menu
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow

SCREEN = (0.0, 0.0, 1440.0, 900.0)
MENUBAR_ONLY = (0.0, 25.0, 1440.0, 875.0)  # Dock auto-hidden: only the menu bar is subtracted
BOTTOM_DOCK = (0.0, 25.0, 1440.0, 785.0)  # 90 px Dock at the bottom
LEFT_DOCK = (70.0, 25.0, 1370.0, 875.0)
RIGHT_DOCK = (0.0, 25.0, 1370.0, 875.0)


def test_bottom_dock_geometry_from_visible_frame():
    g = dock_from_screens([(SCREEN, BOTTOM_DOCK)])
    assert g is not None and g.kind == "dock"
    assert (g.x, g.y, g.w, g.h) == (0.0, 810.0, 1440.0, 90.0)


def test_autohide_dock_is_not_an_edge():
    assert dock_from_screens([(SCREEN, MENUBAR_ONLY)]) is None


@pytest.mark.parametrize("vis", [LEFT_DOCK, RIGHT_DOCK])
def test_side_docks_are_ignored(vis):
    assert dock_from_screens([(SCREEN, vis)]) is None


def test_dock_window_narrows_the_span():
    entries = [{"owner": "Dock", "layer": 20, "x": 300.0, "y": 810.0, "w": 840.0, "h": 90.0},
               {"owner": "Finder", "layer": 0, "x": 0.0, "y": 0.0, "w": 1440.0, "h": 900.0}]
    g = dock_from_screens([(SCREEN, BOTTOM_DOCK)], entries)
    assert (g.x, g.w, g.y) == (300.0, 840.0, 810.0)
    # a full-screen "Dock" helper window does not shrink anything weirdly / bogus windows are ignored
    bogus = [{"owner": "Dock", "layer": 20, "x": 0.0, "y": 0.0, "w": 1440.0, "h": 900.0}]
    assert dock_from_screens([(SCREEN, BOTTOM_DOCK)], bogus).w == 1440.0


def test_multi_display_only_the_dock_screen_counts():
    second = ((1440.0, 0.0, 1920.0, 1080.0), (1440.0, 25.0, 1920.0, 1055.0))  # menu bar only: no Dock here
    g = dock_from_screens([(SCREEN, BOTTOM_DOCK), second])
    assert g.x == 0.0 and g.y == 810.0
    on_second = dock_from_screens([(SCREEN, MENUBAR_ONLY), ((1440.0, 0.0, 1920.0, 1080.0), (1440.0, 25.0, 1920.0, 965.0))])
    assert on_second.x == 1440.0 and on_second.y == 990.0 and on_second.h == 90.0


def test_dock_probe_uses_injected_geometry_and_never_raises():
    p = DockProbe(screens_fn=lambda: [(SCREEN, BOTTOM_DOCK)], entries_fn=lambda: [])
    assert p.sample().y == 810.0

    def boom():
        raise RuntimeError("no display")
    assert DockProbe(screens_fn=boom).sample() is None


def test_dock_drop_tolerance():
    g = FieldGeom(0.0, 810.0, 1440.0, 90.0, "dock")
    assert dock_drop_accepts(g, (700.0, 810.0))
    assert dock_drop_accepts(g, (700.0, 775.0), 40.0)  # 35 px above the edge
    assert not dock_drop_accepts(g, (700.0, 700.0), 40.0)  # 110 px above
    assert dock_drop_accepts(g, (700.0, 700.0), 120.0)  # tolerance is configurable
    assert not dock_drop_accepts(g, (1500.0, 810.0), 40.0)  # beside the Dock
    assert not dock_drop_accepts(FieldGeom(0, 810, 1440, 90, "window"), (700.0, 810.0))
    assert not dock_drop_accepts(None, (700.0, 810.0))


def _win(tmp_path, **settings):
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    base = {"puppet25d": True, "part_rig": True, "window_height": 220, "motion_mode": "still", "lounge_dock": True}
    base.update(settings)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.resize(220, 287)
    w.show()
    QApplication.instance().processEvents()
    return w


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


needs_rig = pytest.mark.skipif(not partrig.available(), reason="rig assets missing")


def _drop_on(win, dock_y):
    win.move(500, int(dock_y - win.height() + 10))  # feet just above the Dock's top edge
    return win._lounge.on_drop()


@needs_rig
def test_drop_near_dock_lounges_on_it(qapp, tmp_path):
    win = _win(tmp_path)
    win.set_lounge(True, persist=False)
    drv = win._lounge
    drv.probe = FakeProbe([None])  # no window edge anywhere
    drv.dock_probe = FakeProbe([FieldGeom(0.0, 810.0, 1440.0, 90.0, "dock")])
    assert _drop_on(win, 810.0)
    assert drv._src == "dock"
    for _ in range(90):
        drv._poll()
        assert drv.tick(1 / 30)
    assert drv.lounge.state == "lounge_loop" and win._pet.lounging()
    foot_y = win.y() + win.height() - 8 * win.height() / 470
    assert abs(foot_y - 810.0) < 12


@needs_rig
def test_dock_switch_off_and_far_drop(qapp, tmp_path):
    win = _win(tmp_path)
    win.set_lounge(True, persist=False)
    drv = win._lounge
    drv.probe = FakeProbe([None])
    drv.dock_probe = FakeProbe([FieldGeom(0.0, 810.0, 1440.0, 90.0, "dock")])
    win.set_lounge_dock(False, persist=False)
    assert not win.lounge_dock and not _drop_on(win, 810.0)
    win.set_lounge_dock(True, persist=False)
    win.move(500, 100)  # far above the Dock
    assert not drv.on_drop() and not drv.active()


@needs_rig
def test_window_edge_still_wins_over_dock(qapp, tmp_path):
    win = _win(tmp_path)
    win.set_lounge(True, persist=False)
    drv = win._lounge
    drv.probe = FakeProbe([FieldGeom(200.0, 780.0, 900.0, 400.0)])
    drv.dock_probe = FakeProbe([FieldGeom(0.0, 810.0, 1440.0, 90.0, "dock")])
    assert _drop_on(win, 780.0)
    assert drv._src == "window"


@needs_rig
def test_dock_hides_she_stands_up_dock_resizes_she_follows(qapp, tmp_path):
    win = _win(tmp_path)
    win.set_lounge(True, persist=False)
    drv = win._lounge
    drv.probe = FakeProbe([None])
    drv.dock_probe = FakeProbe([FieldGeom(0.0, 810.0, 1440.0, 90.0, "dock")])
    assert _drop_on(win, 810.0)
    for _ in range(60):
        drv._poll()
        drv.tick(1 / 30)
    drv.dock_probe = FakeProbe([FieldGeom(0.0, 790.0, 1440.0, 110.0, "dock")])  # bigger Dock: edge rises 20 px
    for _ in range(90):
        drv._poll()
        drv.tick(1 / 30)
    foot_y = win.y() + win.height() - 8 * win.height() / 470
    assert abs(foot_y - 790.0) < 12 and drv.lounge.state in ("lounge_loop", "lie_down")
    drv.dock_probe = FakeProbe([None])  # auto-hide kicked in / Dock moved to a side
    for _ in range(30 * 6):
        drv._poll()
        drv.tick(1 / 30)
    assert drv.lounge.state == "idle" and not win._pet.lounging()
    assert drv._src == "window"


def test_menu_has_dock_toggle_default_on(qapp):
    seen = []

    def cb(**kw):
        return PetMenuCallbacks(
            get_height=lambda: 220, set_height=lambda h: None, is_quiet=lambda: False, set_quiet=lambda q: None,
            is_penetrate=lambda: False, set_penetrate=lambda p: None, is_always_on_top=lambda: True,
            set_always_on_top=lambda v: None, is_bubble_visible=lambda: True, set_bubble_visible=lambda v: None,
            get_motion_mode=lambda: "wander", set_motion_mode=lambda m: None, set_api_key=lambda: None,
            clear_chat=lambda: None, say_line=lambda: None, show_weather=lambda: None, show_about=lambda: None,
            is_autostart=lambda: False, set_autostart=lambda e: None, quit_app=lambda: None, **kw)
    m = build_pet_menu(None, cb(part_rig_available=lambda: True, set_lounge_dock=seen.append, is_lounge_dock=lambda: True))
    acts = [a for a in m.actions() if "程序坞" in a.text()]
    assert len(acts) == 1 and acts[0].isChecked()
    acts[0].trigger()
    assert seen == [False]
