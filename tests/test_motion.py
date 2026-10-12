"""Pure math tests for MotionController (no GUI)."""

from __future__ import annotations

import math
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


def test_follow_looks_at_cursor_without_moving():
    ctrl = MotionController(mode=MotionMode.follow, rng=random.Random(1))
    pos = (200.0, 150.0)
    # Cursor to the right of pet center → face right
    x, y, facing = ctrl.tick(1 / 30, pos, _size(), _screen(), (900.0, 400.0), False)
    assert (x, y) == pos
    assert facing == 1
    # Cursor to the left → face left
    x, y, facing = ctrl.tick(1 / 30, pos, _size(), _screen(), (50.0, 400.0), False)
    assert (x, y) == pos
    assert facing == -1
    # Stay put across many ticks
    for _ in range(40):
        x, y, facing = ctrl.tick(1 / 30, pos, _size(), _screen(), (50.0, 400.0), False)
        assert (x, y) == pos


def test_wander_eventually_moves():
    ctrl = MotionController(mode=MotionMode.wander, rng=random.Random(42))
    x, y = 300.0, 200.0
    start = (x, y)
    moved = False
    for _ in range(400):
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


def test_wander_speed_under_cap():
    ctrl = MotionController(mode=MotionMode.wander, rng=random.Random(7))
    x, y = 400.0, 300.0
    max_speed = 0.0
    for _ in range(600):
        x, y, _ = ctrl.tick(1 / 30, (x, y), _size(), _screen(), (0.0, 0.0), False)
        speed = math.hypot(ctrl.vx, ctrl.vy)
        max_speed = max(max_speed, speed)
    # Cruise is ~65; hard cap ~75 — stay well under old 110 drone feel.
    assert max_speed < 90.0
    assert max_speed > 20.0  # actually walks, not frozen


def test_wander_facing_no_frame_flicker():
    """Facing must not reverse every frame during wander."""
    ctrl = MotionController(mode=MotionMode.wander, rng=random.Random(99))
    x, y = 500.0, 280.0
    facings: list[int] = []
    for _ in range(240):
        x, y, facing = ctrl.tick(1 / 30, (x, y), _size(), _screen(), (0.0, 0.0), False)
        facings.append(facing)
    flips = sum(1 for a, b in zip(facings, facings[1:]) if a != b)
    # At 30fps for 8s, tiny wobbles must not thrash facing.
    assert flips <= 12


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


def test_wander_rests_long_between_short_trips():
    """Pet should idle 25-60s between wanders and each trip is short."""
    ctrl = MotionController(mode=MotionMode.wander, rng=random.Random(3))
    pos = (400.0, 300.0)
    dt = 1 / 30
    trips, moving, run, start, longest = 0, False, 0, (400.0, 300.0), 0.0
    for _ in range(30 * 60 * 10):  # 10 minutes
        x, y, _f = ctrl.tick(dt, pos, _size(), _screen(), (50.0, 400.0), False)
        speed = math.hypot(x - pos[0], y - pos[1]) / dt
        pos = (x, y)
        if speed > 8.0:
            if not moving:
                trips += 1
                start = pos
            moving = True
            run = 0
            longest = max(longest, math.hypot(pos[0] - start[0], pos[1] - start[1]))
        else:
            run += 1
            if moving and run > 30:
                moving = False
    assert trips <= 22
    assert longest <= 260.0
