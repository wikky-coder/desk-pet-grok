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
    ("小 (160)", 160),
    ("默认 (220)", DEFAULT_HEIGHT),
    ("中 (270)", 270),
    ("大 (320)", 320),
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
    is_part_rig: Callable[[], bool] = lambda: False
    set_part_rig: Callable[[bool], None] = lambda enabled: None
    part_rig_available: Callable[[], bool] = lambda: False
    is_part_turn: Callable[[], bool] = lambda: False
    set_part_turn: Callable[[bool], None] = lambda enabled: None
    is_lounge: Callable[[], bool] = lambda: False
    set_lounge: Callable[[bool], None] = lambda enabled: None
    is_lounge_dock: Callable[[], bool] = lambda: True
    set_lounge_dock: Callable[[bool], None] = lambda enabled: None
    is_lounge_selfwalk: Callable[[], bool] = lambda: False
    set_lounge_selfwalk: Callable[[bool], None] = lambda enabled: None
    is_lounge_ax: Callable[[], bool] = lambda: False
    set_lounge_ax: Callable[[bool], None] = lambda enabled: None
    is_look_at_mouse: Callable[[], bool] = lambda: True
    set_look_at_mouse: Callable[[bool], None] = lambda enabled: None
    is_petting: Callable[[], bool] = lambda: True
    set_petting: Callable[[bool], None] = lambda enabled: None
    get_petting_level: Callable[[], str] = lambda: "mid"
    set_petting_level: Callable[[str], None] = lambda level: None
    # v4: (label, getter, setter) triples shown as check items in the menu and the settings panel (see v4wire)
    extras: tuple = ()
    is_tail_boost: Callable[[], bool] = lambda: True
    set_tail_boost: Callable[[bool], None] = lambda enabled: None
    is_lounge_variants: Callable[[], bool] = lambda: False
    set_lounge_variants: Callable[[bool], None] = lambda enabled: None
    is_mood: Callable[[], bool] = lambda: False
    set_mood: Callable[[bool], None] = lambda enabled: None
    is_calibration_log: Callable[[], bool] = lambda: False
    set_calibration_log: Callable[[bool], None] = lambda enabled: None
    is_proactive: Callable[[], bool] = lambda: True
    set_proactive: Callable[[bool], None] = lambda enabled: None
    is_proactive_v2: Callable[[], bool] = lambda: False
    set_proactive_v2: Callable[[bool], None] = lambda enabled: None
    is_memory: Callable[[], bool] = lambda: False
    set_memory: Callable[[bool], None] = lambda enabled: None
    view_memory: Callable[[], None] = lambda: None
    clear_memory: Callable[[], None] = lambda: None
    open_settings: Callable[[], None] | None = None  # opens the settings panel (settings_panel.py)
    screen_menu: Callable[[QMenu], None] | None = None  # adds the 「屏幕感知」 submenu (screen_glue)


def build_pet_menu(parent: QWidget | None, callbacks: PetMenuCallbacks) -> QMenu:
    """Build the shared right-click / tray QMenu."""
    menu = QMenu(parent)

    if callbacks.open_settings is not None:
        st = QAction("设置…", menu)
        st.triggered.connect(lambda checked=False: callbacks.open_settings())
        menu.addAction(st)
        menu.addSeparator()

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

    look = QAction("眼睛看向鼠标", menu)
    look.setCheckable(True)
    look.setChecked(callbacks.is_look_at_mouse())
    look.triggered.connect(lambda checked=False: callbacks.set_look_at_mouse(look.isChecked()))
    menu.addAction(look)

    pat_menu = menu.addMenu("摸头")
    pat_on = QAction("开启摸头反应（鼠标在头顶来回摆动）", pat_menu)
    pat_on.setCheckable(True)
    pat_on.setChecked(callbacks.is_petting())
    pat_on.triggered.connect(lambda checked=False: callbacks.set_petting(pat_on.isChecked()))
    pat_menu.addAction(pat_on)
    pat_menu.addSeparator()
    lvl_group = QActionGroup(pat_menu)
    lvl_group.setExclusive(True)
    cur_lvl = callbacks.get_petting_level()
    for label, key in (("灵敏度：低", "low"), ("灵敏度：中", "mid"), ("灵敏度：高", "high")):
        a = QAction(label, pat_menu)
        a.setCheckable(True)
        a.setChecked(cur_lvl == key)
        a.triggered.connect(lambda checked=False, k=key: callbacks.set_petting_level(k))
        lvl_group.addAction(a)
        pat_menu.addAction(a)

    mood_a = QAction("表情情绪（开心/困/烦/惊讶/委屈，默认关）", menu)
    mood_a.setCheckable(True)
    mood_a.setChecked(callbacks.is_mood())
    mood_a.triggered.connect(lambda checked=False: callbacks.set_mood(mood_a.isChecked()))
    menu.addAction(mood_a)

    talk = QAction("主动开口（关 = 只在你点击/摸头时说话）", menu)
    talk.setCheckable(True)
    talk.setChecked(callbacks.is_proactive())
    talk.triggered.connect(lambda checked=False: callbacks.set_proactive(talk.isChecked()))
    menu.addAction(talk)

    mem_menu = menu.addMenu("记忆")
    mem_on = QAction("跨会话记忆（每天最多 5 次摘要调用）", mem_menu)
    mem_on.setCheckable(True)
    mem_on.setChecked(callbacks.is_memory())
    mem_on.triggered.connect(lambda checked=False: callbacks.set_memory(mem_on.isChecked()))
    mem_menu.addAction(mem_on)
    mem_view = QAction("查看记忆…", mem_menu)
    mem_view.triggered.connect(lambda checked=False: callbacks.view_memory())
    mem_menu.addAction(mem_view)
    mem_clear = QAction("清除记忆…", mem_menu)
    mem_clear.triggered.connect(lambda checked=False: callbacks.clear_memory())
    mem_menu.addAction(mem_clear)

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

    if callbacks.part_rig_available():
        rig = QAction("实验：部件骨架（待机+行走）", menu)
        rig.setCheckable(True)
        rig.setChecked(callbacks.is_part_rig())
        rig.triggered.connect(lambda checked=False: callbacks.set_part_rig(rig.isChecked()))
        menu.addAction(rig)
        turn = QAction("实验：部件转身（已做特征点配准）", menu)
        turn.setCheckable(True)
        turn.setChecked(callbacks.is_part_turn())
        turn.triggered.connect(lambda checked=False: callbacks.set_part_turn(turn.isChecked()))
        menu.addAction(turn)
        lounge = QAction("趴在窗口上沿（拖她到窗口顶边）", menu)
        lounge.setCheckable(True)
        lounge.setChecked(callbacks.is_lounge())
        lounge.triggered.connect(lambda checked=False: callbacks.set_lounge(lounge.isChecked()))
        menu.addAction(lounge)
        dock = QAction("　也趴程序坞（拖她到底部程序坞上沿）", menu)
        dock.setCheckable(True)
        dock.setChecked(callbacks.is_lounge_dock())
        dock.triggered.connect(lambda checked=False: callbacks.set_lounge_dock(dock.isChecked()))
        menu.addAction(dock)
        lvar = QAction("　多种趴姿（侧趴/托腮/伸懒腰/睡着蜷成一团，默认关）", menu)
        lvar.setCheckable(True)
        lvar.setChecked(callbacks.is_lounge_variants())
        lvar.triggered.connect(lambda checked=False: callbacks.set_lounge_variants(lvar.isChecked()))
        menu.addAction(lvar)
        tailb = QAction("尾巴摆动增强", menu)
        tailb.setCheckable(True)
        tailb.setChecked(callbacks.is_tail_boost())
        tailb.triggered.connect(lambda checked=False: callbacks.set_tail_boost(tailb.isChecked()))
        menu.addAction(tailb)
        for _label, _get, _set, *_ in callbacks.extras:
            act = QAction(_label, menu)
            act.setCheckable(True)
            act.setChecked(bool(_get()))
            act.triggered.connect(lambda checked=False, a=act, f=_set: f(a.isChecked()))
            menu.addAction(act)
            if _label.startswith("陪你做事") and _get() and _:
                st = _[0]()
                if st:
                    info = QAction("　" + st, menu)
                    info.setEnabled(False)
                    menu.addAction(info)
        selfwalk = QAction("　偶尔自己走过去（空闲 10 分钟后）", menu)
        selfwalk.setCheckable(True)
        selfwalk.setChecked(callbacks.is_lounge_selfwalk())
        selfwalk.triggered.connect(lambda checked=False: callbacks.set_lounge_selfwalk(selfwalk.isChecked()))
        menu.addAction(selfwalk)
        axact = QAction("　精确到输入框（需「辅助功能」权限，否则用窗口上沿）", menu)
        axact.setCheckable(True)
        axact.setChecked(callbacks.is_lounge_ax())
        axact.triggered.connect(lambda checked=False: callbacks.set_lounge_ax(axact.isChecked()))
        menu.addAction(axact)

    if callbacks.screen_menu is not None:
        callbacks.screen_menu(menu)

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
