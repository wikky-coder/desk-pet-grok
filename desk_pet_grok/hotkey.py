"""Global hotkey without any permission prompt: macOS Carbon RegisterEventHotKey (ctypes). No Accessibility / Input Monitoring
needed (unlike key taps). Everything else (other OS, registration refused, the combo already taken) reports ``False`` so the
caller falls back to the menu item. The callback runs on the main thread (Carbon events ride the Cocoa run loop)."""

from __future__ import annotations

import ctypes
import sys
from typing import Callable, Optional

# macOS virtual key codes (ANSI layout)
KEYCODES = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05, "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B,
    "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10, "t": 0x11, "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16,
    "5": 0x17, "9": 0x19, "7": 0x1A, "8": 0x1C, "0": 0x1D, "o": 0x1F, "u": 0x20, "i": 0x22, "p": 0x23, "l": 0x25, "j": 0x26,
    "k": 0x28, "n": 0x2D, "m": 0x2E, "space": 0x31, "escape": 0x35,
}
MODS = {"cmd": 0x0100, "command": 0x0100, "shift": 0x0200, "alt": 0x0800, "option": 0x0800, "opt": 0x0800,
        "ctrl": 0x1000, "control": 0x1000}
DEFAULT_COMBO = "ctrl+alt+p"  # ⌃⌥P


def parse_combo(text: str) -> Optional[tuple[int, int]]:
    """'ctrl+alt+p' -> (keycode, carbon modifier mask); None when invalid (needs >= 1 modifier and one known key)."""
    parts = [p.strip().lower() for p in (text or "").replace("⌃", "ctrl+").replace("⌥", "alt+").replace("⌘", "cmd+").replace("⇧", "shift+").split("+") if p.strip()]
    if len(parts) < 2:
        return None
    key, mods = parts[-1], parts[:-1]
    if key not in KEYCODES or any(m not in MODS for m in mods):
        return None
    mask = 0
    for m in mods:
        mask |= MODS[m]
    return KEYCODES[key], mask


def pretty(text: str) -> str:
    parts = [p.strip().lower() for p in text.split("+")]
    sym = {"ctrl": "⌃", "control": "⌃", "alt": "⌥", "option": "⌥", "opt": "⌥", "cmd": "⌘", "command": "⌘", "shift": "⇧"}
    return "".join(sym.get(p, p.upper()) for p in parts)


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_SIG = 0x4750544B  # 'GPTK'


class GlobalHotkey:
    """register(combo, callback) -> bool. Idempotent; unregister() on quit / when switched off."""

    def __init__(self) -> None:
        self._carbon = None
        self._ref = ctypes.c_void_p()
        self._handler_ref = ctypes.c_void_p()
        self._cb: Optional[Callable[[], None]] = None
        self._c_handler = None
        self.registered = False
        self.combo = ""

    def _lib(self):
        if self._carbon is None:
            c = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Carbon.framework/Carbon")
            c.GetApplicationEventTarget.restype = ctypes.c_void_p
            c.InstallEventHandler.restype = ctypes.c_int32
            c.InstallEventHandler.argtypes = [ctypes.c_void_p, _HANDLER, ctypes.c_uint32, ctypes.POINTER(_EventTypeSpec),
                                              ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
            c.RegisterEventHotKey.restype = ctypes.c_int32
            c.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID, ctypes.c_void_p, ctypes.c_uint32,
                                              ctypes.POINTER(ctypes.c_void_p)]
            c.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
            c.RemoveEventHandler.argtypes = [ctypes.c_void_p]
            self._carbon = c
        return self._carbon

    def register(self, combo: str, callback: Callable[[], None]) -> bool:
        self.unregister()
        parsed = parse_combo(combo)
        if parsed is None or sys.platform != "darwin":
            return False
        try:
            c = self._lib()
            self._cb = callback

            def on_event(_next, _event, _data) -> int:  # noqa: ANN001
                try:
                    if self._cb:
                        self._cb()
                except Exception:  # noqa: BLE001
                    pass
                return 0

            self._c_handler = _HANDLER(on_event)
            spec = _EventTypeSpec(0x6B657962, 5)  # 'keyb', kEventHotKeyPressed
            if c.InstallEventHandler(c.GetApplicationEventTarget(), self._c_handler, 1, ctypes.byref(spec), None,
                                     ctypes.byref(self._handler_ref)) != 0:
                return False
            rc = c.RegisterEventHotKey(parsed[0], parsed[1], _EventHotKeyID(_SIG, 1), c.GetApplicationEventTarget(), 0,
                                       ctypes.byref(self._ref))
            if rc != 0:  # e.g. eventHotKeyExistsErr
                c.RemoveEventHandler(self._handler_ref)
                return False
        except Exception:  # noqa: BLE001
            return False
        self.registered, self.combo = True, combo
        return True

    def unregister(self) -> None:
        if self.registered and self._carbon is not None:
            try:
                self._carbon.UnregisterEventHotKey(self._ref)
                self._carbon.RemoveEventHandler(self._handler_ref)
            except Exception:  # noqa: BLE001
                pass
        self.registered = False
        self._cb = None
