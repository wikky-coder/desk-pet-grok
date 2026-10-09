"""Offscreen smoke for BubbleWidget."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desk_pet_grok.bubble import BubbleWidget


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_bubble_show_append_and_pref(qapp: QApplication) -> None:
    b = BubbleWidget()
    b.show_text("在想。")
    assert b.full_text == "在想。"
    assert b.isVisible() or b.pref_visible
    b.append_text("续")
    assert b.full_text == "在想。续"
    b.set_pref_visible(False)
    assert not b.isVisible()
    b.set_pref_visible(True)
    assert b.isVisible()
    b.clear()
    assert b.full_text == ""
    assert not b.isVisible()
