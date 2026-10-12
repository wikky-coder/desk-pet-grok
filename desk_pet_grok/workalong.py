"""v4-6: 「陪你做事」 (Qt-free). Looks only at the NAME of the front app (never titles / contents), classifies it and tells the pet
which prop to show next to her: reading -> book, coding -> laptop, terminal -> small terminal window, drawing -> palette.
A change needs the new app to stay in front for ENTER_STABLE_S and at least COOLDOWN_S since the last change (no flicker)."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

MODES = ("read", "code", "terminal", "draw")
ENTER_STABLE_S = 3.0
EXIT_STABLE_S = 5.0
COOLDOWN_S = 25.0
POLL_S = 2.5

_TERMINAL = ("terminal", "iterm", "warp", "kitty", "alacritty", "ghostty", "wezterm", "hyper", "终端", "tabby", "termius", "windows terminal")
_DRAW = ("photoshop", "illustrator", "figma", "sketch", "procreate", "krita", "clip studio", "clipstudio", "affinity", "pixelmator",
         "paint tool sai", "medibang", "aseprite", "adobe xd", "inkscape", "gimp", "blender", "画图", "paintbrush", "sai2", "lightroom", "fresco", "concepts", "tayasui")
_CODE = ("xcode", "visual studio", "code", "cursor", "pycharm", "intellij", "webstorm", "clion", "goland", "rider", "rubymine", "phpstorm", "datagrip",
         "sublime", "nova", "bbedit", "textmate", "zed", "android studio", "emacs", "macvim", "vim", "atom", "fleet", "windsurf", "trae", "textedit",
         "coteditor", "jupyter", "positron", "rstudio", "eclipse", "netbeans", "codex", "kiro")
_READ = ("safari", "chrome", "firefox", "arc", "edge", "brave", "opera", "vivaldi", "orion", "preview", "预览", "books", "图书", "kindle", "pages",
         "word", "notion", "obsidian", "typora", "notes", "备忘录", "acrobat", "reader", "zotero", "微信读书", "bear", "pdf", "calibre", "marginnote",
         "goodnotes", "readwise", "reeder", "wps", "logseq", "craft", "evernote", "onenote", "flomo", "语雀", "飞书文档", "mweb", "ulysses", "scrivener")
_ORDER = (("terminal", _TERMINAL), ("draw", _DRAW), ("code", _CODE), ("read", _READ))
# short tokens that must match a whole word (so "code" does not match "Xcode"'s sibling "Barcode", "vim" does not match "...")
_WORD_ONLY = {"code", "zed", "arc", "sketch", "nova", "edge", "word", "notes", "reader", "pdf", "bear", "craft", "atom", "vim", "books", "hyper", "warp", "kitty", "trae", "fleet", "rider"}
_NEVER = ("desk pet", "桌宠", "python", "finder", "访达", "dock", "系统设置", "system settings", "system preferences", "activity monitor", "活动监视器")


def classify(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    low = name.strip().lower()
    if not low or any(n in low for n in _NEVER):
        return None
    words = set(low.replace("-", " ").replace("_", " ").replace(".", " ").split())
    for mode, keys in _ORDER:
        for key in keys:
            if key in _WORD_ONLY:
                if key in words or low == key:
                    return mode
            elif key in low:
                return mode
    return None


@dataclass
class WorkAlong:
    enabled: bool = False
    mode: Optional[str] = None
    _cand: Optional[str] = None
    _stable: float = 0.0
    _last_change: float = -1e9

    def feed(self, now: float, dt: float, app: Optional[str], blocked: bool = False) -> Optional[tuple]:
        """One observation; returns ("enter", mode) / ("switch", mode) / ("exit", old) when the shown prop changes."""
        if not self.enabled:
            return self._drop("exit") if self.mode else None
        if blocked:  # lying down, clinging, angry, hidden, being dragged ...: props go away at once
            self._cand, self._stable = None, 0.0
            return self._drop("exit") if self.mode else None
        cand = classify(app)
        if cand == self._cand:
            self._stable += dt
        else:
            self._cand, self._stable = cand, 0.0
        if cand == self.mode:
            return None
        if cand is None:  # a non-matching app: leave after EXIT_STABLE_S (the cooldown never keeps a prop around)
            if self.mode and self._stable >= EXIT_STABLE_S:
                return self._drop("exit", now)
            return None
        if self._stable >= ENTER_STABLE_S and now - self._last_change >= COOLDOWN_S:
            kind = "switch" if self.mode else "enter"
            self.mode, self._last_change = cand, now
            return (kind, cand)
        return None

    def _drop(self, kind: str, now: Optional[float] = None):
        old, self.mode = self.mode, None
        if now is not None:
            self._last_change = now
        return (kind, old) if old else None


class FrontPoller:
    """Reads the front app name off the GUI thread (lsappinfo may take a moment). ``name`` is the last value read."""

    def __init__(self, fn: Callable[[], Optional[str]], interval: float = POLL_S) -> None:
        self.fn, self.interval = fn, interval
        self.name: Optional[str] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="front-app-poll", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.name = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.name = self.fn()
            except Exception:  # noqa: BLE001
                self.name = None
            self._stop.wait(self.interval)
