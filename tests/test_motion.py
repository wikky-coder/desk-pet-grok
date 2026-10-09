"""Pure math tests for MotionController (no GUI)."""

from __future__ import annotations

import random

from desk_pet_grok.motion import MotionController, MotionMode, parse_mode, soft_clamp


def _screen() -> tuple[float, float, float, float]:
    return (0.0, 0.0, 1280.0, 720.0)


def _size() -> tuple[float, float]:
    return (120.0, 100.0)


def test_parse_mode():
    assert parse_mode("follow") is MotionMode.follow
    assert parse_mode("nope") is MotionMode.wander
    assert parse_mode(MotionMode.still) is MotionMode.still


def test_still_unchanged():
    ctrl = MotionController(mode=MotionMode.still, rng=random.Random(0))
    pos = (200.0, 150.0)
    for _ in range(40):
        x, y, facing = ctrl.tick(
            1 / 30,
            pos,
            _size(),
            _screen(),
            (900.0, 400.0),
            False,
        )
        assert (x, y) == pos
        assert facing == 1
    assert ctrl.mode is MotionMode.still


def test_follow_moves_toward_cursor():
    ctrl = MotionController(mode=MotionMode.follow, rng=random.Random(1))
    x, y = 50.0, 50.0
    cursor = (800.0, 400.0)
    start = (x, y)
    for _ in range(90):
        x, y, facing = ctrl.tick(
            1 / 30,
            (x, y),
            _size(),
            _screen(),
            cursor,
            False,
        )
    # Should have closed a substantial portion of the gap toward the cursor area.
    assert abs(x - start[0]) + abs(y - start[1]) > 80
    # Closer to cursor than at start (account for follow offset).
    assert abs(x - cursor[0]) < abs(start[0] - cursor[0])
    assert facing in (-1, 1)


def test_wander_eventually_moves():
    ctrl = MotionController(mode=MotionMode.wander, rng=random.Random(42))
    x, y = 300.0, 200.0
    start = (x, y)
    moved = False
    for _ in range(300):
        x, y, facing = ctrl.tick(
            1 / 30,
            (x, y),
            _size(),
            _screen(),
            (10.0, 10.0),
            False,
        )
        if abs(x - start[0]) + abs(y - start[1]) > 30:
            moved = True
            break
    assert moved
    assert facing in (-1, 1)


def test_dragging_no_auto_move_updates_facing():
    ctrl = MotionController(mode=MotionMode.wander, rng=random.Random(3))
    # Seed last position.
    ctrl.tick(1 / 30, (100.0, 100.0), _size(), _screen(), (0.0, 0.0), False)
    x, y, facing = ctrl.tick(
        1 / 30,
        (140.0, 100.0),  # dragged right
        _size(),
        _screen(),
        (0.0, 0.0),
        True,
    )
    assert (x, y) == (140.0, 100.0)
    assert facing == 1
    x, y, facing = ctrl.tick(
        1 / 30,
        (90.0, 100.0),  # dragged left
        _size(),
        _screen(),
        (0.0, 0.0),
        True,
    )
    assert (x, y) == (90.0, 100.0)
    assert facing == -1


def test_soft_clamp_pulls_inward():
    x, y = soft_clamp(-80.0, -50.0, 100.0, 80.0, 0.0, 0.0, 800.0, 600.0)
    assert x > -80.0
    assert y > -50.0


def test_set_mode_resets_velocity():
    ctrl = MotionController(mode=MotionMode.follow, rng=random.Random(0))
    ctrl.vx = 50.0
    ctrl.vy = -20.0
    ctrl.set_mode("still")
    assert ctrl.mode is MotionMode.still
    assert ctrl.vx == 0.0 and ctrl.vy == 0.0
