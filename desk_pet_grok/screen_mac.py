"""macOS adapters for screen awareness (ctypes only, no pyobjc). Every function is a safe no-op / False / None off macOS
or when anything fails. Never reads AXValue (contents); window titles stay in memory and are never logged."""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

from desk_pet_grok.screen_aware import FrontContext

IS_MAC = sys.platform == "darwin"
SCREEN_SETTINGS_URL = "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
OWN_NAMES = ("desk pet grok", "desk-pet-grok", "python", "桌宠grok")
MAX_SIDE = 768
JPEG_QUALITY = 60


def parse_lsappinfo_name(out: str) -> Optional[str]:
    m = re.search(r'"LSDisplayName"\s*=\s*"([^"]*)"', out)
    if m:
        return m.group(1) or None
    m = re.search(r'"?name"?\s*=\s*"([^"]*)"', out)
    return m.group(1) if m and m.group(1) else None


_NS = None


def _nsworkspace_name() -> Optional[str]:
    """Front app's localized name via NSWorkspace (ctypes objc, no PyObjC / permissions needed; works from a worker thread)."""
    global _NS
    import ctypes
    import ctypes.util
    if _NS is None:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        addr = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        _NS = (objc, ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(addr),
               ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)(addr))
    objc, obj, txt = _NS
    sel = objc.sel_registerName
    pool = obj(obj(objc.objc_getClass(b"NSAutoreleasePool"), sel(b"alloc")), sel(b"init"))
    try:
        ws = obj(objc.objc_getClass(b"NSWorkspace"), sel(b"sharedWorkspace"))
        app = obj(ws, sel(b"frontmostApplication"))
        if not app:
            return None
        name = obj(app, sel(b"localizedName"))
        raw = txt(name, sel(b"UTF8String")) if name else None
        return raw.decode("utf-8", "replace") if raw else None
    finally:
        obj(pool, sel(b"drain"))


def front_app_name() -> Optional[str]:
    if not IS_MAC:
        return None
    try:
        name = _nsworkspace_name()
        if name:
            return name
    except Exception:  # noqa: BLE001
        pass
    try:
        asn = subprocess.run(["lsappinfo", "front"], capture_output=True, text=True, timeout=2).stdout.strip()
        if not asn:
            return None
        out = subprocess.run(["lsappinfo", "info", "-only", "name", asn], capture_output=True, text=True, timeout=2).stdout
        return parse_lsappinfo_name(out)
    except Exception:  # noqa: BLE001
        return None


def _ax_details() -> tuple[str, bool, bool]:
    """(window title, is full screen, focus is in a secure text field) via Accessibility; ('', False, False) if unavailable."""
    from desk_pet_grok import ax_probe
    if not IS_MAC or not ax_probe.is_trusted():
        return "", False, False
    ax, cf = ax_probe._libs()
    cf.CFBooleanGetValue.restype = ctypes.c_bool
    cf.CFBooleanGetValue.argtypes = [ctypes.c_void_p]
    held: list[int] = []

    def key(name: str):
        k = cf.CFStringCreateWithCString(None, name.encode(), 0x08000100)
        held.append(k)
        return k

    def attr(el, name):
        out = ctypes.c_void_p()
        if ax.AXUIElementCopyAttributeValue(el, key(name), ctypes.byref(out)) != 0 or not out.value:
            return None
        held.append(out.value)
        return out.value

    def text(v) -> str:
        buf = ctypes.create_string_buffer(512)
        return buf.value.decode("utf-8", "ignore") if cf.CFStringGetCString(v, buf, 512, 0x08000100) else ""

    title, full, secure = "", False, False
    try:
        system = ax.AXUIElementCreateSystemWide()
        held.append(system)
        focused = attr(system, "AXFocusedUIElement")
        if focused:
            role = attr(focused, "AXRole")
            sub = attr(focused, "AXSubrole")
            secure = "AXSecureTextField" in ((text(role) if role else "") + (text(sub) if sub else ""))
        app = attr(system, "AXFocusedApplication")
        win = attr(app, "AXFocusedWindow") if app else None
        if win:
            t = attr(win, "AXTitle")
            title = text(t) if t else ""
            fs = attr(win, "AXFullScreen")
            full = bool(fs and cf.CFBooleanGetValue(fs))
    except Exception:  # noqa: BLE001
        pass
    finally:
        for o in held:
            try:
                cf.CFRelease(o)
            except Exception:  # noqa: BLE001
                pass
    return title, full, secure


def front_context() -> Optional[FrontContext]:
    name = front_app_name()
    if not name or name.lower() in OWN_NAMES:
        return None
    try:
        title, full, secure = _ax_details()
    except Exception:  # noqa: BLE001
        title, full, secure = "", False, False
    return FrontContext(name, title, full, secure)


def _cg():
    return ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")


def has_screen_permission() -> bool:
    if not IS_MAC:
        return False
    try:
        cg = _cg()
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        return bool(cg.CGPreflightScreenCaptureAccess())
    except Exception:  # noqa: BLE001
        return False


def request_screen_permission() -> None:
    """Shows the system prompt (the user must click it themselves) and opens the Screen Recording settings page."""
    if not IS_MAC:
        return
    try:
        cg = _cg()
        cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        cg.CGRequestScreenCaptureAccess()
    except Exception:  # noqa: BLE001
        pass
    open_screen_settings()


def open_screen_settings() -> None:
    if IS_MAC:
        try:
            subprocess.Popen(["open", SCREEN_SETTINGS_URL])
        except OSError:
            pass


def shrink_jpeg(src_path: str, work_dir: str) -> Optional[bytes]:
    """Return a long-side<=MAX_SIDE JPEG as bytes (Pillow if present, else macOS ``sips``)."""
    try:
        from PIL import Image
        with Image.open(src_path) as im:
            im = im.convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE))
            import io
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=JPEG_QUALITY)
            return buf.getvalue()
    except ImportError:
        pass
    except Exception:  # noqa: BLE001
        return None
    try:
        out = os.path.join(work_dir, "s.jpg")
        subprocess.run(["sips", "-Z", str(MAX_SIDE), "-s", "format", "jpeg", "-s", "formatOptions", str(JPEG_QUALITY),
                        src_path, "--out", out], capture_output=True, timeout=10, check=True)
        with open(out, "rb") as f:
            return f.read()
    except Exception:  # noqa: BLE001
        return None


def capture_jpeg() -> Optional[bytes]:
    """Main display -> small JPEG bytes. ``screencapture`` can only write files, so the raw shot lives in a private
    0700 temp dir for a moment and is removed in ``finally``. Nothing is kept or logged."""
    if not IS_MAC or not has_screen_permission():
        return None
    work = tempfile.mkdtemp(prefix="dpg-")
    try:
        os.chmod(work, 0o700)
        raw = os.path.join(work, "r.png")
        subprocess.run(["screencapture", "-x", "-m", "-t", "png", raw], capture_output=True, timeout=10, check=True)
        return shrink_jpeg(raw, work)
    except Exception:  # noqa: BLE001
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
