"""Qt glue for screen awareness: polling timer, background worker, submenu (no marker window). Never takes focus."""

from __future__ import annotations

import time
from typing import Callable

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from desk_pet_grok import chat_theme as theme
from desk_pet_grok import config, macwin, screen_mac, screen_vision
from desk_pet_grok.api import DEFAULT_MODEL
from desk_pet_grok.meow import ensure_meow
from desk_pet_grok.screen_aware import STATUS_LINES, LookResult, ScreenAwareness, is_look_request

POLL_MS = 8000


class _LookWorker(QThread):
    done = Signal(object)

    def __init__(self, aware: ScreenAwareness, manual: bool, parent=None) -> None:
        super().__init__(parent)
        self._aware, self._manual = aware, manual

    def run(self) -> None:  # noqa: N802
        try:
            self.done.emit(self._aware.look(manual=self._manual))
        except Exception:  # noqa: BLE001
            self.done.emit(LookResult("error", STATUS_LINES["error"]))


class ScreenController(QObject):
    def __init__(self, window, chat, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window, self._chat = window, chat
        self._settings = config.load_settings()
        self.aware = ScreenAwareness(
            settings=self._settings, save=config.save_settings,
            get_context=screen_mac.front_context, capture=screen_mac.capture_jpeg,
            describe=self._describe, has_permission=screen_mac.has_screen_permission,
            has_key=lambda: screen_vision.api_key_from_env() is not None,
        )
        self._worker: _LookWorker | None = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._apply_running()

    # --- plumbing ---
    def _describe(self, jpeg: bytes) -> str:
        key = screen_vision.api_key_from_env()
        if not key:
            raise RuntimeError("no key")
        return screen_vision.describe(jpeg, key, model=self._settings.get("screen_model") or DEFAULT_MODEL)

    def _set(self, **kv) -> None:
        self._settings.update(kv)
        config.save_settings(kv)
        self._apply_running()

    def _apply_running(self) -> None:
        on = bool(self._settings.get("screen_aware"))
        if on and not self._timer.isActive():
            self._timer.start(POLL_MS)
        elif not on:
            self._timer.stop()

    def _say(self, text: str) -> None:
        if self._chat._angry():  # angry: no cute screen commentary
            self._chat.show_line("anger_idle", force=True, cooldown_key="anger_screen")
            return
        self._chat.bubble.show_text(ensure_meow(text))
        self._chat.bubble.reposition_above(self._window)
        from desk_pet_grok.chat import LINE_BUBBLE_HOLD_MS
        self._chat._line_clear_timer.start(LINE_BUBBLE_HOLD_MS)

    # --- triggers ---
    def _tick(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._chat._can_show_proactive_line():
            return
        line = self.aware.context_line()
        if line:
            self._say(line)
            return
        if self.aware.proactive_due():
            self._start(manual=False)

    def _start(self, manual: bool) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        w = _LookWorker(self.aware, manual, self)
        w.done.connect(self._on_done)
        self._worker = w
        w.start()

    def _on_done(self, res: LookResult) -> None:
        if res.text:
            if res.status == "ok" or self._manual_pending:
                self._say(res.text)
        self._manual_pending = False

    _manual_pending = False

    def look_now(self) -> None:
        """Menu 「现在看一眼屏幕」 / chat request. Manual: always answers (with a reason if she cannot look)."""
        self._manual_pending = True
        self._say("让本喵看看喵…")
        self._start(manual=True)

    def handle_chat_text(self, text: str) -> bool:
        if is_look_request(text):
            self.look_now()
            return True
        return False

    # --- menu model ---
    def get(self, key: str) -> bool:
        return bool(self._settings.get(key))

    def set_flag(self, key: str, on: bool) -> None:
        self._set(**{key: bool(on)})
        if key == "screen_vision" and on and not screen_mac.has_screen_permission():
            screen_mac.request_screen_permission()  # user must click Allow / tick the app themselves
            self._say(STATUS_LINES["no_permission"])

    def paused(self) -> bool:
        return time.time() < float(self._settings.get("screen_pause_until") or 0)

    def set_paused(self, on: bool) -> None:
        self._set(screen_pause_until=(time.time() + 3600) if on else 0)


def populate_screen_menu(menu: QMenu, ctl: ScreenController) -> None:
    sub = menu.addMenu("屏幕感知")

    def check(label: str, key: str) -> None:
        a = QAction(label, sub)
        a.setCheckable(True)
        a.setChecked(ctl.get(key))
        a.triggered.connect(lambda checked=False, k=key, act=a: ctl.set_flag(k, act.isChecked()))
        sub.addAction(a)

    check("读前台软件名（不花额度）", "screen_aware")
    check("　允许截屏看（花额度，需屏幕录制权限）", "screen_vision")
    check("　　偶尔主动评论（默认关）", "screen_proactive")
    check("安静时段 22:00–08:00 不截屏", "screen_quiet_hours")
    pause = QAction("专注：暂停 1 小时", sub)
    pause.setCheckable(True)
    pause.setChecked(ctl.paused())
    pause.triggered.connect(lambda checked=False: ctl.set_paused(pause.isChecked()))
    sub.addAction(pause)
    sub.addSeparator()
    look = QAction("现在看一眼屏幕", sub)
    look.triggered.connect(lambda checked=False: ctl.look_now())
    sub.addAction(look)
    usage = QAction(ctl.aware.usage_label(), sub)
    usage.setEnabled(False)
    sub.addAction(usage)
    perm = QAction("打开屏幕录制权限设置…", sub)
    perm.triggered.connect(lambda checked=False: screen_mac.open_screen_settings())
    sub.addAction(perm)
