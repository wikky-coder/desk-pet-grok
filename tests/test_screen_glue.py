import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu

from desk_pet_grok import menu as menu_mod
from desk_pet_grok.screen_glue import ScreenController, populate_screen_menu


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_no_marker_window_exists():
    import desk_pet_grok.screen_glue as sg
    assert not hasattr(sg, "ScreenMarker") and not hasattr(sg, "MARKER_WATCH")


class FakeBubble:
    def __init__(self): self.texts = []
    def show_text(self, t): self.texts.append(t)
    def reposition_above(self, w): pass


class FakeTimer:
    def start(self, ms): pass


class FakeChat:
    def __init__(self): self.bubble = FakeBubble(); self._line_clear_timer = FakeTimer()
    def _can_show_proactive_line(self): return True


def test_menu_and_default_off(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    from PySide6.QtWidgets import QWidget
    win = QWidget()
    chat = FakeChat()
    ctl = ScreenController(win, chat)
    menu = QMenu()
    populate_screen_menu(menu, ctl)
    sub = [a for a in menu.actions() if a.text() == "屏幕感知"][0].menu()
    texts = [a.text() for a in sub.actions()]
    assert any("今日已用 0/20" in t for t in texts)
    checks = [a for a in sub.actions() if a.isCheckable()]
    assert checks and not any(a.isChecked() for a in checks)
    ctl.set_flag("screen_aware", True)
    assert ctl.get("screen_aware") and not hasattr(ctl, "marker")
    ctl.set_flag("screen_aware", False)


def test_chat_hook_phrase(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    from PySide6.QtWidgets import QWidget
    ctl = ScreenController(QWidget(), FakeChat())
    called = []
    ctl.look_now = lambda: called.append(1)
    assert ctl.handle_chat_text("你看我屏幕") and called
    assert not ctl.handle_chat_text("你好")


def test_menu_builder_includes_screen_menu(qapp):
    cb = menu_mod.PetMenuCallbacks(
        get_height=lambda: 220, set_height=lambda h: None, is_quiet=lambda: False, set_quiet=lambda q: None,
        is_penetrate=lambda: False, set_penetrate=lambda p: None, is_always_on_top=lambda: True,
        set_always_on_top=lambda v: None, is_bubble_visible=lambda: True, set_bubble_visible=lambda v: None,
        get_motion_mode=lambda: "wander", set_motion_mode=lambda m: None, set_api_key=lambda: None,
        clear_chat=lambda: None, say_line=lambda: None, show_weather=lambda: None, show_about=lambda: None,
        is_autostart=lambda: False, set_autostart=lambda e: None, quit_app=lambda: None,
        screen_menu=lambda m: m.addMenu("屏幕感知"))
    m = menu_mod.build_pet_menu(None, cb)
    assert "屏幕感知" in [a.text() for a in m.actions()]
