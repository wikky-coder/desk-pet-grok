"""Focus-stealing guards: the pet window and bubble must never take keyboard focus from other apps."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desk_pet_grok import macwin
from desk_pet_grok.bubble import BubbleWidget
from desk_pet_grok.chat_panel import ChatPanel
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_pet_window_is_non_activating(qapp, tmp_path) -> None:
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": False})
    assert win.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert win.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert win.focusPolicy() == Qt.FocusPolicy.NoFocus
    win.set_always_on_top(False)  # flag rebuild must keep the guard
    assert win.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert win.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)


def test_bubble_is_non_activating(qapp) -> None:
    b = BubbleWidget()
    assert b.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert b.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert b.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_chat_panel_may_take_focus(qapp) -> None:
    p = ChatPanel()  # only opened on explicit double-click / menu
    assert not (p.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)


def test_tool_windows_stay_when_app_inactive(qapp, tmp_path) -> None:
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": False})
    assert win.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
    win.set_always_on_top(True)
    assert win.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
    assert BubbleWidget().testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
    assert ChatPanel().testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)


def test_macwin_is_safe_without_cocoa(qapp) -> None:
    b = BubbleWidget()
    b.show()
    # offscreen platform: must be a harmless no-op (never touch a non-NSView handle)
    assert macwin.apply(b) is False
    assert macwin.is_covered(b) is False
    assert macwin.reassert(b) is False
    assert macwin.BEHAVIOR == (1 | (1 << 4) | (1 << 8))
    assert macwin.NS_STATUS_WINDOW_LEVEL > macwin.NS_FLOATING_WINDOW_LEVEL > 0
