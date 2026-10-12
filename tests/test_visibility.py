"""v4-1: fullscreen auto-hide, manual hide, global hotkey parsing / fallback (no real key events needed)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from test_lounge_pet import qapp  # noqa: E402,F401

from PySide6.QtWidgets import QWidget  # noqa: E402

from desk_pet_grok import hotkey  # noqa: E402
from desk_pet_grok.visibility import VisibilityController, fullscreen_on_screen, screen_of  # noqa: E402

SCR = (0.0, 0.0, 1512.0, 982.0)
SCR2 = (1512.0, 0.0, 1920.0, 1080.0)


def E(x=0, y=0, w=1512, h=982, layer=0, pid=99, owner="IINA", alpha=1.0):
    return {"x": x, "y": y, "w": w, "h": h, "layer": layer, "pid": pid, "owner": owner, "alpha": alpha}


def test_fullscreen_detection_rules():
    assert fullscreen_on_screen([E()], SCR, 1)
    assert not fullscreen_on_screen([E(y=38, h=944)], SCR, 1)  # maximised below the menu bar != fullscreen
    assert not fullscreen_on_screen([E(pid=1)], SCR, 1)  # our own window
    assert not fullscreen_on_screen([E(layer=25)], SCR, 1)  # menu bar / overlays
    assert not fullscreen_on_screen([E(owner="Finder")], SCR, 1) and not fullscreen_on_screen([E(owner="Dock")], SCR, 1)
    assert not fullscreen_on_screen([E(alpha=0.0)], SCR, 1)
    assert not fullscreen_on_screen([E(w=800, h=600)], SCR, 1)
    assert fullscreen_on_screen([E(x=1512, w=1920, h=1080)], SCR2, 1)
    assert not fullscreen_on_screen([E(x=1512, w=1920, h=1080)], SCR, 1)  # fullscreen on the OTHER screen


def test_screen_of():
    assert screen_of((100, 100), [SCR, SCR2]) == SCR
    assert screen_of((2000, 50), [SCR, SCR2]) == SCR2
    assert screen_of((-50, 5000), [SCR, SCR2]) == SCR


def _ctl(entries):
    w = QWidget(); w.setGeometry(100, 100, 120, 160); w.show()
    box = {"e": entries}
    c = VisibilityController(w, lambda: [SCR, SCR2], lambda: box["e"], own_pid=1)
    return w, c, box


def test_auto_hide_and_restore(qapp):
    w, c, box = _ctl([])
    c.set_auto_enabled(True)
    assert w.isVisible() and not c.hidden()
    box["e"] = [E(x=1512, w=1920, h=1080)]  # other screen: stays
    c.poll(); assert w.isVisible()
    box["e"] = [E()]
    c.poll(); assert not w.isVisible() and c.hidden()
    box["e"] = []
    c.poll(); assert w.isVisible() and not c.hidden()


def test_manual_and_auto_combine(qapp):
    w, c, box = _ctl([E()])
    c.set_auto_enabled(True); assert not w.isVisible()
    c.set_manual(True)
    box["e"] = []; c.poll()
    assert not w.isVisible()  # still manually hidden after leaving fullscreen
    c.toggle_manual(); assert w.isVisible()
    c.set_auto_enabled(False)
    box["e"] = [E()]; c.poll(); assert w.isVisible()  # switch off: never auto-hides


def test_hidden_signals_and_extra_widgets(qapp):
    w, c, _ = _ctl([])
    other = QWidget(); other.show()
    c.extra_widgets = lambda: (other,)
    got = []
    c.changed.connect(got.append)
    c.set_manual(True); c.set_manual(True); c.set_manual(False)
    assert got == [True, False]
    c.set_manual(True)
    assert not other.isVisible()


def test_hotkey_combo_parse():
    assert hotkey.parse_combo("ctrl+alt+p") == (0x23, 0x1000 | 0x0800)
    assert hotkey.parse_combo("⌃⌥P") == (0x23, 0x1800)
    assert hotkey.parse_combo("cmd+shift+space") == (0x31, 0x0300)
    assert hotkey.parse_combo("p") is None and hotkey.parse_combo("ctrl+alt+") is None and hotkey.parse_combo("foo+p") is None
    assert hotkey.pretty("ctrl+alt+p") == "⌃⌥P"


def test_hotkey_falls_back_off_mac_or_bad_combo():
    h = hotkey.GlobalHotkey()
    assert h.register("nonsense", lambda: None) is False
    if sys.platform != "darwin":
        assert h.register("ctrl+alt+p", lambda: None) is False
    h.unregister()
    assert not h.registered
