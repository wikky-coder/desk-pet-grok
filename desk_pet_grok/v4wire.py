"""Glue for the v4 companion features: builds the (label, getter, setter, note) extras for the menu / settings panel and
owns the helper objects. Each feature sits behind its own switch (settings key)."""

from __future__ import annotations

from typing import Callable

from desk_pet_grok import config, hotkey
from desk_pet_grok.visibility import VisibilityController


class V4:
    def __init__(self, window, app, chat, bubble, panel, settings: dict) -> None:
        self.window, self.app, self.chat, self.bubble, self.panel = window, app, chat, bubble, panel
        self.settings = settings
        self.hotkey = hotkey.GlobalHotkey()
        self.hotkey_ok = False
        screens = lambda: [(g.x(), g.y(), g.width(), g.height()) for g in (s.geometry() for s in app.screens())]  # noqa: E731
        entries = None
        try:
            from desk_pet_grok import focus_probe
            import sys
            if sys.platform == "darwin":
                entries = focus_probe.cg_window_entries
        except Exception:  # noqa: BLE001
            entries = None
        self.vis = VisibilityController(window, screens, entries, extra_widgets=lambda: (bubble, panel), parent=app)
        self.vis.changed.connect(self._on_hidden)
        chat.hidden_fn = self.vis.hidden
        chat.anger_fn = lambda: window._anger.stage
        window.chat_busy_fn = lambda: bool(panel.isVisible() or bubble.isVisible())
        app.aboutToQuit.connect(self.hotkey.unregister)

    # ---- helpers ----
    def flag(self, key: str, default: bool = False) -> bool:
        return bool(self.settings.get(key, default))

    def set_flag(self, key: str, on: bool) -> None:
        self.settings[key] = bool(on)
        config.save_settings({key: bool(on)})

    def start(self) -> None:
        """Apply saved switches (called once after the window is up)."""
        self.vis.set_auto_enabled(self.flag("fullscreen_hide"))
        if self.flag("hotkey_hide"):
            self._set_hotkey(True)

    def _on_hidden(self, hidden: bool) -> None:
        if hidden:
            self.bubble.hide()
            self.panel.hide()

    # ---- 1) hide / hotkey ----
    def combo(self) -> str:
        return str(self.settings.get("hotkey_combo") or hotkey.DEFAULT_COMBO)

    def _toggle_from_hotkey(self) -> None:
        self.vis.toggle_manual()

    def _set_hotkey(self, on: bool) -> None:
        if on:
            self.hotkey_ok = self.hotkey.register(self.combo(), self._toggle_from_hotkey)
        else:
            self.hotkey.unregister()
            self.hotkey_ok = False

    def set_hotkey(self, on: bool) -> None:
        self.set_flag("hotkey_hide", on)
        self._set_hotkey(on)

    def hotkey_note(self) -> str:
        if not self.flag("hotkey_hide"):
            return ""
        return "" if self.hotkey_ok else "这台电脑上注册失败（组合键被占用或系统不支持），请用菜单里的「暂时隐藏」。"

    def set_fullscreen_hide(self, on: bool) -> None:
        self.set_flag("fullscreen_hide", on)
        self.vis.set_auto_enabled(on)

    def extras(self) -> list[tuple]:
        pretty = hotkey.pretty(self.combo())
        return [
            ("陪你做事（只读前台软件名：看书/写码/终端/画画时手里拿起对应道具）", lambda: self.window.work_along, self.window.set_work_along, self.window.work_status),
            ("贴边扒着（拖到屏幕左/右边缘松手；靠近会探头）", lambda: self.window.cling_edge, self.window.set_cling_edge),
            ("时段问候（早/中/下午/晚/深夜，每时段第一次见面打招呼）", lambda: self.window.time_greeting, self.window.set_time_greeting),
            ("节日小饰品（万圣/圣诞/元旦/春节/元宵/端午/中秋/国庆当天）", lambda: self.window.holiday_outfit, self.window.set_holiday_outfit),
            ("省电模式（闲 30 秒降到约 12 帧，闲 1 分钟约 6 帧；一动就恢复）", lambda: self.window.power_save, self.window.set_power_save),
            ("甩她会红温（按住左右快速甩；摸头才哄好）", lambda: self.window.shake_anger, self.window.set_shake_anger),
            ("暂时隐藏（再点一次叫回来）", lambda: self.vis.manual, self.vis.set_manual),
            (f"全局快捷键 {pretty} 隐藏 / 叫回（不需要额外权限）", lambda: self.flag("hotkey_hide"), self.set_hotkey, self.hotkey_note),
            ("全屏应用 / 视频时自动隐藏", lambda: self.flag("fullscreen_hide"), self.set_fullscreen_hide),
        ]
