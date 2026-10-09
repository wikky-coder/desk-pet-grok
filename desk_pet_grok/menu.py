"""Shared context / tray menu for 桌宠grok."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from desk_pet_grok.about import show_about
from desk_pet_grok.window import (
    DEFAULT_HEIGHT,
    MAX_HEIGHT,
    MIN_HEIGHT,
    PRODUCT_TITLE,
)

SIZE_PRESETS: tuple[tuple[str, int], ...] = (
    ("小 (140)", MIN_HEIGHT),
    ("默认 (220)", DEFAULT_HEIGHT),
    ("中 (280)", 280),
    ("大 (360)", MAX_HEIGHT),
)


@dataclass
class PetMenuCallbacks:
    """Hooks the shared menu invokes."""

    get_height: Callable[[], int]
    set_height: Callable[[int], None]
    is_quiet: Callable[[], bool]
    set_quiet: Callable[[bool], None]
    is_penetrate: Callable[[], bool]
    set_penetrate: Callable[[bool], None]
    is_always_on_top: Callable[[], bool]
    set_always_on_top: Callable[[bool], None]
    is_bubble_visible: Callable[[], bool]
    set_bubble_visible: Callable[[bool], None]
    get_motion_mode: Callable[[], str]
    set_motion_mode: Callable[[str], None]
    set_api_key: Callable[[], None]
    clear_chat: Callable[[], None]
    say_line: Callable[[], None]
    show_weather: Callable[[], None]
    show_about: Callable[[], None]
    is_autostart: Callable[[], bool]
    set_autostart: Callable[[bool], None]
    quit_app: Callable[[], None]


def build_pet_menu(parent: QWidget | None, callbacks: PetMenuCallbacks) -> QMenu:
    """Build the shared right-click / tray QMenu."""
    menu = QMenu(parent)

    size_menu = menu.addMenu("大小")
    size_group = QActionGroup(size_menu)
    size_group.setExclusive(True)
    current_h = callbacks.get_height()
    for label, height in SIZE_PRESETS:
        action = QAction(label, size_menu)
        action.setCheckable(True)
        action.setChecked(current_h == height)
        action.triggered.connect(
            lambda checked=False, h=height: callbacks.set_height(h)
        )
        size_group.addAction(action)
        size_menu.addAction(action)

    mode_menu = menu.addMenu("模式")
    mode_group = QActionGroup(mode_menu)
    mode_group.setExclusive(True)
    current_mode = callbacks.get_motion_mode()
    for label, mode_key in (
        ("散步", "wander"),
        ("看向鼠标", "follow"),
        ("原地", "still"),
    ):
        action = QAction(label, mode_menu)
        action.setCheckable(True)
        action.setChecked(current_mode == mode_key)
        action.triggered.connect(
            lambda checked=False, m=mode_key: callbacks.set_motion_mode(m)
        )
        mode_group.addAction(action)
        mode_menu.addAction(action)

    quiet = QAction("安静模式", menu)
    quiet.setCheckable(True)
    quiet.setChecked(callbacks.is_quiet())
    quiet.triggered.connect(
        lambda checked=False: callbacks.set_quiet(quiet.isChecked())
    )
    menu.addAction(quiet)

    penetrate = QAction("鼠标穿透", menu)
    penetrate.setCheckable(True)
    penetrate.setChecked(callbacks.is_penetrate())
    penetrate.triggered.connect(
        lambda checked=False: callbacks.set_penetrate(penetrate.isChecked())
    )
    menu.addAction(penetrate)

    on_top = QAction("置顶", menu)
    on_top.setCheckable(True)
    on_top.setChecked(callbacks.is_always_on_top())
    on_top.triggered.connect(
        lambda checked=False: callbacks.set_always_on_top(on_top.isChecked())
    )
    menu.addAction(on_top)

    bubble = QAction("显示气泡", menu)
    bubble.setCheckable(True)
    bubble.setChecked(callbacks.is_bubble_visible())
    bubble.triggered.connect(
        lambda checked=False: callbacks.set_bubble_visible(bubble.isChecked())
    )
    menu.addAction(bubble)

    menu.addSeparator()

    set_key = QAction("设置 API Key…", menu)
    set_key.triggered.connect(lambda checked=False: callbacks.set_api_key())
    menu.addAction(set_key)

    clear_chat = QAction("清空本次对话", menu)
    clear_chat.triggered.connect(lambda checked=False: callbacks.clear_chat())
    menu.addAction(clear_chat)

    say_line = QAction("说句话", menu)
    say_line.triggered.connect(lambda checked=False: callbacks.say_line())
    menu.addAction(say_line)

    weather = QAction("查看天气", menu)
    weather.triggered.connect(lambda checked=False: callbacks.show_weather())
    menu.addAction(weather)

    autostart = QAction("开机自启", menu)
    autostart.setCheckable(True)
    autostart.setChecked(callbacks.is_autostart())
    autostart.triggered.connect(
        lambda checked=False: callbacks.set_autostart(autostart.isChecked())
    )
    menu.addAction(autostart)

    about = QAction("关于", menu)
    about.triggered.connect(lambda checked=False: callbacks.show_about())
    menu.addAction(about)

    menu.addSeparator()

    quit_action = QAction("退出", menu)
    quit_action.triggered.connect(lambda checked=False: callbacks.quit_app())
    menu.addAction(quit_action)

    return menu


def default_about(parent: QWidget | None = None) -> None:
    """Show the about dialog."""
    show_about(parent)
