"""Chat card / speech bubble restyle: behaviour hooks only (looks are checked via _gen25d/rounds/chatui renders)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desk_pet_grok import chat_theme
from desk_pet_grok.chat_panel import THINKING_TEXT, ChatPanel


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_avatar_and_paw_render(qapp) -> None:
    assert chat_theme.AVATAR_PATH.exists()
    assert not chat_theme.circle_avatar(38).isNull()
    assert not chat_theme.paw_pixmap(22).isNull()


def test_submit_echo_and_thinking(qapp) -> None:
    p = ChatPanel()
    got: list[str] = []
    p.send_requested.connect(got.append)
    p._input.setPlainText("  你好  ")
    p._on_submit()
    assert got == ["你好"]
    assert p._mine_bubble.text() == "你好"
    p.set_streaming(True)
    assert p._think_bubble.text() == THINKING_TEXT == "本喵想想…"
    assert not p._send_btn.isEnabled() and p._stop_btn.isEnabled()
    p.set_streaming(False)
    assert p._send_btn.isEnabled() and not p._stop_btn.isEnabled()
    p._input.setPlainText("   ")
    p._on_submit()
    assert got == ["你好"]


def test_focus_flags_unchanged(qapp) -> None:
    p = ChatPanel()
    assert not (p.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
    assert p.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert p.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
