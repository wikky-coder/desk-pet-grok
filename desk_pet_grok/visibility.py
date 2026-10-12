"""Hide / show the pet: 暂时隐藏 (menu / global hotkey) and automatic hiding while a full-screen app / video is on HER screen.

Fullscreen = a normal (layer 0) window of another app that covers its whole screen *including the menu bar strip*
(maximised windows stop below the menu bar, so they do not count). Only window geometry is read (never titles or contents).
Showing again never activates our app / steals focus (the pet window is a ShowWithoutActivating tool window)."""

from __future__ import annotations

import os
import sys
from typing import Callable, Optional, Sequence

from PySide6.QtCore import QObject, QTimer, Signal

POLL_MS = 1500
Rect = tuple[float, float, float, float]
IGNORE_OWNERS = {"Window Server", "Dock", "Finder", "SystemUIServer", "Control Centre", "Control Center", "Notification Center"}


def fullscreen_on_screen(entries: Sequence[dict], screen: Rect, own_pid: int, tol: float = 1.5) -> bool:
    sx, sy, sw, sh = screen
    for e in entries:
        if e.get("pid") == own_pid or e.get("layer", 0) != 0 or e.get("owner", "") in IGNORE_OWNERS:
            continue
        if e.get("alpha", 1.0) < 0.5:
            continue
        if (abs(e["x"] - sx) <= tol and abs(e["y"] - sy) <= tol and e["w"] >= sw - tol and e["h"] >= sh - tol):
            return True
    return False


def screen_of(point: tuple[float, float], screens: Sequence[Rect]) -> Optional[Rect]:
    px, py = point
    for r in screens:
        if r[0] <= px < r[0] + r[2] and r[1] <= py < r[1] + r[3]:
            return r
    best, bd = None, 1e18
    for r in screens:
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        d = (cx - px) ** 2 + (cy - py) ** 2
        if d < bd:
            best, bd = r, d
    return best


class VisibilityController(QObject):
    """hidden = manual or auto. ``entries_fn`` -> window entries (macOS CoreGraphics), ``screens_fn`` -> [Rect] (global, logical)."""

    changed = Signal(bool)

    def __init__(self, window, screens_fn: Callable[[], Sequence[Rect]], entries_fn: Optional[Callable[[], list]] = None,
                 extra_widgets: Callable[[], Sequence] = lambda: (), own_pid: Optional[int] = None, parent=None) -> None:
        super().__init__(parent)
        self.window = window
        self.screens_fn = screens_fn
        self.entries_fn = entries_fn
        self.extra_widgets = extra_widgets
        self.own_pid = os.getpid() if own_pid is None else own_pid
        self.manual = False
        self.auto = False
        self.auto_enabled = False  # setting 「全屏时自动隐藏」
        self._applied = False
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self.poll)

    # ---- settings ----
    def set_auto_enabled(self, on: bool) -> None:
        self.auto_enabled = bool(on)
        if on:
            self._timer.start()
            self.poll()
        else:
            self._timer.stop()
            self.auto = False
            self._apply()

    def hidden(self) -> bool:
        return self.manual or self.auto

    def set_manual(self, on: bool) -> None:
        self.manual = bool(on)
        self._apply()

    def toggle_manual(self) -> bool:
        self.set_manual(not self.manual)
        return self.manual

    # ---- fullscreen watch ----
    def poll(self) -> None:
        if not self.auto_enabled or self.entries_fn is None:
            return
        try:
            w = self.window
            c = w.geometry().center()
            scr = screen_of((c.x(), c.y()), list(self.screens_fn()))
            full = bool(scr) and fullscreen_on_screen(self.entries_fn(), scr, self.own_pid)
        except Exception:  # noqa: BLE001
            full = False
        if full != self.auto:
            self.auto = full
            self._apply()

    def _apply(self) -> None:
        hide = self.hidden()
        if hide == self._applied:
            return
        self._applied = hide
        if hide:
            for w in (self.window, *self.extra_widgets()):
                if w is not None:
                    w.hide()
        else:
            self.window.show()  # WA_ShowWithoutActivating: no focus change
        self.changed.emit(hide)
