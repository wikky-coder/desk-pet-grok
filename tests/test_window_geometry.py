"""Unit tests for pet window geometry helpers (no GUI required)."""

from desk_pet_grok.window import (
    DEFAULT_HEIGHT,
    MAX_HEIGHT,
    MIN_HEIGHT,
    clamp_window_height,
    size_for_height,
)


def test_default_height_in_range():
    assert MIN_HEIGHT <= DEFAULT_HEIGHT <= MAX_HEIGHT
    assert DEFAULT_HEIGHT == 220
    assert MIN_HEIGHT == 140
    assert MAX_HEIGHT == 360


def test_clamp_window_height():
    assert clamp_window_height(100) == 140
    assert clamp_window_height(140) == 140
    assert clamp_window_height(220) == 220
    assert clamp_window_height(360) == 360
    assert clamp_window_height(999) == 360


def test_size_for_height_keeps_canvas_aspect():
    w, h = size_for_height(220)
    assert h == 220
    # Authoring canvas 412×344 → width scales with height.
    assert w == round(220 * 412 / 344)
    w2, h2 = size_for_height(50)
    assert h2 == 140
    assert w2 == round(140 * 412 / 344)
