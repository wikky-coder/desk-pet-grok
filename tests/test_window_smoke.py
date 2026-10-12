"""Offscreen smoke test for PetWindow (no interactive GUI)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from desk_pet_grok.state import PetState, StateMachine
from desk_pet_grok.window import DEFAULT_HEIGHT, PetWindow, size_for_height


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_pet_window_flags_and_default_size(qapp: QApplication, tmp_path) -> None:
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    sm = StateMachine()
    win = PetWindow(state_machine=sm, settings={"puppet25d": False})
    flags = win.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint
    assert flags & Qt.WindowType.Tool
    w, h = size_for_height(DEFAULT_HEIGHT)
    assert win.height() == h
    assert win.width() == w
    assert win.windowTitle() == "桌宠grok"


def test_quiet_mode_updates_state(qapp: QApplication, tmp_path) -> None:
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    sm = StateMachine()
    win = PetWindow(state_machine=sm, settings={"puppet25d": False})
    win.set_quiet(True)
    assert sm.state is PetState.sleep
    assert win.pet.state is PetState.sleep
    win.set_quiet(False)
    assert sm.state is PetState.idle
