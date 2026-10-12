"""Where can she lounge?  Geometry only -- never contents.

``FieldProbe.sample()`` returns the screen rectangle (logical points, global coordinates with the origin at the
top-left of the primary display, i.e. the same space as Qt's global coordinates on macOS) of the thing she should
lie on, or ``None``.  Implementations: ``WindowEdgeProbe`` (front-most normal window via CoreGraphics, no special
permission), ``AXProbe`` (focused input field via Accessibility, see ax_probe.py), ``FakeProbe`` (tests).
Nothing here reads window titles, text values or screen pixels, and nothing is logged."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, Sequence


@dataclass(frozen=True)
class FieldGeom:
    x: float
    y: float
    w: float
    h: float
    kind: str = "window"  # "window" (top edge of a window) | "field" (top edge of an input field) | "dock" (top of the Dock)
    role: str = ""


class FieldProbe(Protocol):
    def sample(self) -> Optional[FieldGeom]: ...


class FakeProbe:
    """Scripted probe: returns the items in order, then repeats the last one."""

    def __init__(self, seq: Iterable[Optional[FieldGeom]] = ()) -> None:
        self._seq = list(seq)
        self._i = 0

    def set(self, value: Optional[FieldGeom]) -> None:
        self._seq = [value]
        self._i = 0

    def sample(self) -> Optional[FieldGeom]:
        if not self._seq:
            return None
        v = self._seq[min(self._i, len(self._seq) - 1)]
        self._i += 1
        return v


MIN_WINDOW_W = 200.0
MIN_WINDOW_H = 120.0


def pick_front_window(entries: Sequence[dict], own_pid: int) -> Optional[FieldGeom]:
    """entries: front-to-back dicts with layer,pid,x,y,w,h,alpha (pure, testable)."""
    for e in entries:
        if int(e.get("layer", 0)) != 0 or int(e.get("pid", -1)) == own_pid:
            continue
        if float(e.get("alpha", 1.0)) < 0.05:
            continue
        w, h = float(e["w"]), float(e["h"])
        if w < MIN_WINDOW_W or h < MIN_WINDOW_H:
            continue
        return FieldGeom(float(e["x"]), float(e["y"]), w, h, "window", "")
    return None


def anchor_for(g: FieldGeom, prefer_x: float, margin: float = 40.0) -> tuple[float, float]:
    """Anchor on the top edge: x as close to ``prefer_x`` as the geometry allows (centre if too narrow)."""
    lo, hi = g.x + margin, g.x + g.w - margin
    if hi <= lo:
        return (g.x + g.w / 2.0, g.y)
    return (min(max(prefer_x, lo), hi), g.y)


def clamp_anchor_to_screens(pt: tuple[float, float], screens: Sequence[tuple[float, float, float, float]]):
    """Keep the anchor on a real screen (multi-monitor, negative origins); None if it is on none."""
    x, y = pt
    for sx, sy, sw, sh in screens:
        if sx <= x <= sx + sw and sy - 40.0 <= y <= sy + sh:
            return (x, max(y, sy))
    return None


# ---- CoreGraphics window list (macOS only, ctypes, no pyobjc) -----------------------------------------------------

class _CGRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("w", ctypes.c_double), ("h", ctypes.c_double)]


_cg = None


def _libs():
    global _cg
    if _cg is None:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
        cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        cg.CGRectMakeWithDictionaryRepresentation.restype = ctypes.c_bool
        cg.CGRectMakeWithDictionaryRepresentation.argtypes = [ctypes.c_void_p, ctypes.POINTER(_CGRect)]
        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        cf.CFDictionaryGetValue.restype = ctypes.c_void_p
        cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        cf.CFNumberGetValue.restype = ctypes.c_bool
        cf.CFNumberGetValue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        _cg = (cg, cf)
    return _cg


def cg_window_entries() -> list[dict]:
    """Front-to-back on-screen windows (layer, pid, x, y, w, h, alpha, owner). Window titles are never read; the owner
name is only used to recognise the Dock."""
    cg, cf = _libs()
    arr = cg.CGWindowListCopyWindowInfo(1 | 16, 0)  # on-screen only | exclude desktop elements
    if not arr:
        return []
    keys = {k: cf.CFStringCreateWithCString(None, k.encode(), 0x08000100)
            for k in ("kCGWindowLayer", "kCGWindowBounds", "kCGWindowOwnerPID", "kCGWindowAlpha", "kCGWindowOwnerName")}
    out: list[dict] = []
    try:
        for i in range(cf.CFArrayGetCount(arr)):
            d = cf.CFArrayGetValueAtIndex(arr, i)
            layer, pid, alpha = ctypes.c_int32(0), ctypes.c_int32(-1), ctypes.c_double(1.0)
            cf.CFNumberGetValue(cf.CFDictionaryGetValue(d, keys["kCGWindowLayer"]), 3, ctypes.byref(layer))
            cf.CFNumberGetValue(cf.CFDictionaryGetValue(d, keys["kCGWindowOwnerPID"]), 3, ctypes.byref(pid))
            a = cf.CFDictionaryGetValue(d, keys["kCGWindowAlpha"])
            if a:
                cf.CFNumberGetValue(a, 13, ctypes.byref(alpha))
            r = _CGRect()
            b = cf.CFDictionaryGetValue(d, keys["kCGWindowBounds"])
            if not b or not cg.CGRectMakeWithDictionaryRepresentation(b, ctypes.byref(r)):
                continue
            owner = ""
            on = cf.CFDictionaryGetValue(d, keys["kCGWindowOwnerName"])
            if on:
                buf = ctypes.create_string_buffer(64)
                if cf.CFStringGetCString(on, buf, 64, 0x08000100):
                    owner = buf.value.decode("utf-8", "ignore")
            out.append({"layer": layer.value, "pid": pid.value, "x": r.x, "y": r.y, "w": r.w, "h": r.h,
                        "alpha": alpha.value, "owner": owner})
    finally:
        for k in keys.values():
            cf.CFRelease(k)
        cf.CFRelease(arr)
    return out


class WindowEdgeProbe:
    """Top edge of the front-most normal window of another app (no Accessibility permission needed)."""

    def __init__(self, own_pid: int | None = None) -> None:
        self._pid = own_pid if own_pid is not None else os.getpid()

    def sample(self) -> Optional[FieldGeom]:
        if sys.platform != "darwin":
            return None
        try:
            return pick_front_window(cg_window_entries(), self._pid)
        except Exception:  # noqa: BLE001
            return None


# ---- the Dock as a lounge edge (bottom Dock only) -----------------------------------------------------------------

Rect = tuple[float, float, float, float]
DOCK_MIN_H = 8.0  # visible-frame gap below which there is no (visible) Dock: auto-hide / none


def dock_from_screens(screens: Sequence[tuple[Rect, Rect]], entries: Sequence[dict] = ()) -> Optional[FieldGeom]:
    """Top edge of a visible bottom Dock. ``screens`` = [(frame, visible_frame), ...] in global top-left coordinates
    (QScreen.geometry / availableGeometry). The Dock's extent is the gap between the two at the bottom; a Dock on the
    left / right, an auto-hidden Dock (no gap) or no Dock give ``None``. Only the screen that carries the Dock counts.
    ``entries`` (cg_window_entries with ``owner``) narrow the x-span to the Dock's own window when it is recognisable."""
    best: Optional[tuple[float, Rect, Rect]] = None
    for frame, vis in screens:
        fx, fy, fw, fh = frame
        vx, vy, vw, vh = vis
        bottom = (fy + fh) - (vy + vh)
        side = max(vx - fx, (fx + fw) - (vx + vw))
        if side > DOCK_MIN_H and side >= bottom:
            return None  # the Dock sits on a side of its screen: not supported (it never counts as an edge)
        if bottom >= DOCK_MIN_H and (best is None or bottom > best[0]):
            best = (bottom, frame, vis)
    if best is None:
        return None
    bottom, frame, vis = best
    x, w = vis[0], vis[2]
    top_y = vis[1] + vis[3]
    cands = [e for e in entries if str(e.get("owner", "")) == "Dock"
             and 100.0 <= float(e["w"]) <= frame[2] + 1.0 and float(e["h"]) <= bottom + 40.0
             and abs((float(e["y"]) + float(e["h"])) - (frame[1] + frame[3])) <= 6.0
             and frame[0] - 1.0 <= float(e["x"]) and float(e["x"]) + float(e["w"]) <= frame[0] + frame[2] + 1.0]
    if cands:
        c = max(cands, key=lambda e: float(e["w"]))
        x, w = float(c["x"]), float(c["w"])
    return FieldGeom(x, top_y, w, bottom, "dock", "")


def dock_drop_accepts(geom: Optional[FieldGeom], foot: tuple[float, float], tol: float = 40.0) -> bool:
    """Pure: feet within ``tol`` px of the Dock's top edge (above or below) and within its span (+/- tol)."""
    if geom is None or geom.kind != "dock":
        return False
    fx, fy = foot
    return geom.x - tol <= fx <= geom.x + geom.w + tol and abs(fy - geom.y) <= tol


def _qt_screens() -> list[tuple[Rect, Rect]]:
    from PySide6.QtGui import QGuiApplication

    out = []
    for sc in QGuiApplication.screens():
        g, a = sc.geometry(), sc.availableGeometry()
        out.append(((float(g.x()), float(g.y()), float(g.width()), float(g.height())),
                    (float(a.x()), float(a.y()), float(a.width()), float(a.height()))))
    return out


class DockProbe:
    """``sample()`` -> the visible bottom Dock's top edge as a ``FieldGeom(kind="dock")`` or ``None``. No permission
    needed (screen geometry + the CoreGraphics window list); ``screens_fn`` / ``entries_fn`` are injectable for tests."""

    def __init__(self, screens_fn=None, entries_fn=None) -> None:
        self._screens = screens_fn or _qt_screens
        self._entries = entries_fn

    def sample(self) -> Optional[FieldGeom]:
        try:
            entries: Sequence[dict] = ()
            if self._entries is not None:
                entries = self._entries()
            elif sys.platform == "darwin":
                entries = cg_window_entries()
            return dock_from_screens(self._screens(), entries)
        except Exception:  # noqa: BLE001
            return None


def idle_seconds() -> float:
    """Seconds since the last keyboard/mouse event (a plain timer value; no input is observed). 0.0 if unknown."""
    if sys.platform != "darwin":
        return 0.0
    try:
        cg, _cf = _libs()
        f = cg.CGEventSourceSecondsSinceLastEventType
        f.restype = ctypes.c_double
        f.argtypes = [ctypes.c_int32, ctypes.c_uint32]
        return max(0.0, float(f(0, 0xFFFFFFFF)))  # combined session state, any event type
    except Exception:  # noqa: BLE001
        return 0.0
