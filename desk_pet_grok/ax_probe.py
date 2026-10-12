"""Accessibility-based probe (macOS, ctypes, no pyobjc): geometry of the focused text input, nothing else.

Reads only AXFocusedUIElement -> AXRole / AXPosition / AXSize (+ owner pid to skip our own windows). Never reads
AXValue / titles / contents, skips secure fields, logs nothing. Without the Accessibility permission it is never
called (HybridProbe falls back to the window top edge)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from typing import Callable, Optional

from desk_pet_grok.focus_probe import FieldGeom, FieldProbe

EDITABLE = frozenset({"AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"})
SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


def is_editable_role(role: str | None) -> bool:
    return bool(role) and role in EDITABLE  # AXSecureTextField is deliberately not editable-for-us


class _Pt(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _Sz(ctypes.Structure):
    _fields_ = [("w", ctypes.c_double), ("h", ctypes.c_double)]


_libs_cache = None


def _libs():
    global _libs_cache
    if _libs_cache is None:
        ax = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        ax.AXIsProcessTrusted.restype = ctypes.c_bool
        ax.AXUIElementCreateSystemWide.restype = ctypes.c_void_p
        ax.AXUIElementCopyAttributeValue.restype = ctypes.c_int32
        ax.AXUIElementCopyAttributeValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        ax.AXUIElementGetPid.restype = ctypes.c_int32
        ax.AXUIElementGetPid.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int32)]
        ax.AXValueGetValue.restype = ctypes.c_bool
        ax.AXValueGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        _libs_cache = (ax, cf)
    return _libs_cache


def is_trusted() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        return bool(_libs()[0].AXIsProcessTrusted())
    except Exception:  # noqa: BLE001
        return False


def open_accessibility_settings() -> None:
    """Onboarding helper: open the Privacy > Accessibility pane (the user ticks the app themselves)."""
    if sys.platform == "darwin":
        try:
            subprocess.Popen(["open", SETTINGS_URL])
        except OSError:
            pass


class AXProbe:
    def __init__(self, own_pid: int | None = None) -> None:
        self._pid = own_pid if own_pid is not None else os.getpid()

    def sample(self) -> Optional[FieldGeom]:
        if sys.platform != "darwin":
            return None
        ax, cf = _libs()
        made = []

        def key(name: str):
            k = cf.CFStringCreateWithCString(None, name.encode(), 0x08000100)
            made.append(k)
            return k

        def attr(el, name):
            out = ctypes.c_void_p()
            if ax.AXUIElementCopyAttributeValue(el, key(name), ctypes.byref(out)) != 0 or not out.value:
                return None
            return out.value

        owned = []
        try:
            system = ax.AXUIElementCreateSystemWide()
            owned.append(system)
            el = attr(system, "AXFocusedUIElement")
            if not el:
                return None
            owned.append(el)
            pid = ctypes.c_int32(-1)
            ax.AXUIElementGetPid(el, ctypes.byref(pid))
            if pid.value == self._pid:
                return None  # never lounge on our own chat box
            r = attr(el, "AXRole")
            if not r:
                return None
            owned.append(r)
            buf = ctypes.create_string_buffer(64)
            if not cf.CFStringGetCString(r, buf, 64, 0x08000100):
                return None
            role = buf.value.decode()
            if not is_editable_role(role):
                return None
            pv, sv = attr(el, "AXPosition"), attr(el, "AXSize")
            if not pv or not sv:
                return None
            owned += [pv, sv]
            pt, sz = _Pt(), _Sz()
            if not (ax.AXValueGetValue(pv, 1, ctypes.byref(pt)) and ax.AXValueGetValue(sv, 2, ctypes.byref(sz))):
                return None
            if sz.w < 40 or sz.h < 10:
                return None
            return FieldGeom(pt.x, pt.y, sz.w, sz.h, "field", role)
        finally:
            for o in owned + made:
                try:
                    cf.CFRelease(o)
                except Exception:  # noqa: BLE001
                    pass


class HybridProbe:
    """AX field when permitted and available, else the window top edge. Permission re-checked every ``recheck_s``."""

    def __init__(self, ax: FieldProbe, fallback: FieldProbe, *, trusted: Callable[[], bool] = is_trusted,
                 recheck_s: float = 10.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.ax, self.fallback = ax, fallback
        self._trusted_fn, self._recheck, self._clock = trusted, recheck_s, clock
        self._trusted = False
        self._checked_at = -1e9

    @property
    def permission_missing(self) -> bool:
        return not self._trusted

    def sample(self) -> Optional[FieldGeom]:
        now = self._clock()
        if now - self._checked_at >= self._recheck:
            self._trusted, self._checked_at = bool(self._trusted_fn()), now
        if self._trusted:
            try:
                g = self.ax.sample()
            except Exception:  # noqa: BLE001
                g = None
            if g is not None:
                return g
        return self.fallback.sample()
