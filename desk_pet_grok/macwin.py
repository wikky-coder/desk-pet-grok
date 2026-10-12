"""macOS-only helpers: keep a Qt window floating above other apps (all Spaces, over full-screen apps) without ever
activating our app / stealing keyboard focus. Uses the Objective-C runtime through ctypes (no pyobjc needed); every
function is a safe no-op on other platforms or when anything goes wrong."""

from __future__ import annotations

import ctypes
import ctypes.util
import sys

IS_MAC = sys.platform == "darwin"

NS_FLOATING_WINDOW_LEVEL = 3
NS_STATUS_WINDOW_LEVEL = 25
NS_NORMAL_WINDOW_LEVEL = 0
# NSWindowCollectionBehavior
CAN_JOIN_ALL_SPACES = 1 << 0
STATIONARY = 1 << 4
FULLSCREEN_AUXILIARY = 1 << 8
BEHAVIOR = CAN_JOIN_ALL_SPACES | STATIONARY | FULLSCREEN_AUXILIARY
NS_WINDOW_OCCLUSION_VISIBLE = 1 << 1

_objc = None


def _rt():
    global _objc
    if _objc is None:
        lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.A.dylib")
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        _objc = lib
    return _objc


def _send(obj: int, sel: str, restype, argtypes=(), *args):
    lib = _rt()
    fn = ctypes.cast(lib.objc_msgSend, ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes))
    return fn(obj, lib.sel_registerName(sel.encode()), *args)


def _nswindow(widget) -> int | None:
    try:
        from PySide6.QtGui import QGuiApplication

        if QGuiApplication.platformName() != "cocoa":  # offscreen/test platforms: winId is not an NSView
            return None
        view = int(widget.winId())
        if not view:
            return None
        win = _send(view, "window", ctypes.c_void_p)
        return int(win) if win else None
    except Exception:  # noqa: BLE001
        return None


def apply(widget, *, on_top: bool = True) -> bool:
    """Level above normal windows, visible on every Space and over full-screen apps, not hidden when the app
    deactivates. Click-through (ignoresMouseEvents) and focus behaviour are left to Qt."""
    if not IS_MAC:
        return False
    win = _nswindow(widget)
    if win is None:
        return False
    try:
        _send(win, "setLevel:", None, (ctypes.c_long,), NS_STATUS_WINDOW_LEVEL if on_top else NS_NORMAL_WINDOW_LEVEL)
        if on_top:
            _send(win, "setCollectionBehavior:", None, (ctypes.c_ulong,), BEHAVIOR)
        _send(win, "setHidesOnDeactivate:", None, (ctypes.c_bool,), False)
        return True
    except Exception:  # noqa: BLE001
        return False


def is_covered(widget) -> bool:
    """True when the window is not (fully) visible: occluded by other windows or ordered out."""
    if not IS_MAC:
        return False
    win = _nswindow(widget)
    if win is None:
        return False
    try:
        state = _send(win, "occlusionState", ctypes.c_ulong)
        return not (int(state) & NS_WINDOW_OCCLUSION_VISIBLE)
    except Exception:  # noqa: BLE001
        return False


def reassert(widget, *, on_top: bool = True) -> bool:
    """Gentle keep-visible: if covered/hidden, re-apply level and order front *without* activating the app
    (orderFrontRegardless). Never uses raise_()/activateWindow(). Returns True if it acted."""
    if not IS_MAC or not on_top or not widget.isVisible():
        return False
    if not is_covered(widget):
        return False
    win = _nswindow(widget)
    if win is None:
        return False
    try:
        apply(widget, on_top=True)
        _send(win, "orderFrontRegardless", None)
        return True
    except Exception:  # noqa: BLE001
        return False
