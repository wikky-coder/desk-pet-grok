"""Offscreen tests: PetWindow in 2.5D puppet mode."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from desk_pet_grok import puppet
from desk_pet_grok.state import StateMachine
from desk_pet_grok.window import PetWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def make(tmp_path, **settings):
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    return PetWindow(state_machine=StateMachine(), settings=settings)


def test_puppet_mode_and_height_clamp(qapp, tmp_path):
    win = make(tmp_path)
    assert win.puppet_mode
    win.apply_height(500, persist=False)
    assert win.height() == 320
    win.apply_height(10, persist=False)
    assert win.height() == 160
    assert win.width() == puppet.size_for_height(160)[0]


def test_blank_pixels_do_not_hit(qapp, tmp_path):
    win = make(tmp_path)
    win.show()
    win.grab()  # paint once
    assert not win.pet.hit(QPoint(1, 1))
    assert win.pet.hit(QPoint(win.width() // 2, win.height() // 2))


def test_saved_position_clamped_on_screen(qapp, tmp_path):
    win = make(tmp_path, window_x=99999, window_y=-5000)
    rect = win._screen_rect()
    assert win.x() + win.width() <= rect[0] + rect[2]
    assert win.y() >= rect[1]


def test_walk_stays_in_bounds_and_horizontal(qapp, tmp_path):
    win = make(tmp_path, window_x=300, window_y=300)
    win.show()
    y0 = win.y()
    rect = win._screen_rect()
    for _ in range(600):
        win._puppet_tick(1 / 30, False)
        assert rect[0] <= win.x() <= rect[0] + rect[2] - win.width()
    assert win.y() == y0


def test_fallback_to_2d_when_disabled(qapp, tmp_path):
    win = make(tmp_path, puppet25d=False)
    assert not win.puppet_mode
