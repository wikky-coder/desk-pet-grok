"""Head-pat detector on synthetic mouse trajectories (Qt-free)."""

from __future__ import annotations

import math

import pytest

from desk_pet_grok.petting import LEVELS, PettingDetector, head_zone, in_zone, params_for

ZONE = (100.0, 20.0, 300.0, 120.0)  # x0,y0,x1,y1 (screen px); 200 px wide


def run(det, pts, dt=1 / 30.0, t0=0.0):
    t, out = t0, []
    for x, y in pts:
        out.append(det.feed(t, x, y, in_zone(ZONE, x, y)))
        t += dt
    return out


def swipe(cycles, amp=40.0, period=0.4, cx=200.0, cy=60.0, dt=1 / 30.0):
    n = int(cycles * period / dt)
    return [(cx + amp * math.sin(2 * math.pi * i * dt / period), cy) for i in range(n)]


def test_back_and_forth_is_petting():
    det = PettingDetector("mid")
    assert any(run(det, swipe(3)))


def test_needs_enough_reversals():
    det = PettingDetector("mid")
    assert not any(run(det, swipe(1.0)))  # <3 folds


def test_straight_line_not_petting():
    det = PettingDetector("mid")
    pts = [(100.0 + i * 6.0, 60.0) for i in range(32)]
    assert not any(run(det, pts))


def test_still_not_petting():
    det = PettingDetector("high")
    assert not any(run(det, [(200.0, 60.0)] * 90))


def test_tiny_jitter_not_petting():
    det = PettingDetector("mid")
    pts = [(200.0 + (2.0 if i % 2 else -2.0), 60.0) for i in range(90)]
    assert not any(run(det, pts))


def test_slow_wobble_not_petting():
    det = PettingDetector("mid")
    assert not any(run(det, swipe(3, amp=40.0, period=4.0)))  # 40 px per 1 s: too slow / too spread out


def test_outside_zone_not_petting():
    det = PettingDetector("mid")
    pts = [(x, 300.0) for x, _ in swipe(4)]  # y far below zone
    assert not any(run(det, pts))


def test_holds_then_releases_after_stop():
    det = PettingDetector("mid")
    flags = run(det, swipe(4))
    assert flags[-1]
    # mouse parks inside the zone: stays active briefly, then releases (~1 s)
    park = run(det, [(200.0, 60.0)] * 60, t0=len(flags) / 30.0)
    assert park[0] and not park[-1]
    first_off = park.index(False)
    assert 15 <= first_off <= 45  # ~0.5..1.5 s at 30 fps


def test_leaving_zone_releases_immediately():
    det = PettingDetector("mid")
    flags = run(det, swipe(4))
    assert flags[-1]
    t = len(flags) / 30.0
    assert det.feed(t, 200.0, 500.0, False) is False


def test_reversals_must_fit_time_window():
    det = PettingDetector("mid")
    # three folds but spread over ~6 s (period 2 s)
    assert not any(run(det, swipe(3, amp=40.0, period=2.0)))


def test_sensitivity_levels_ordered():
    lo, mid, hi = (params_for(k) for k in LEVELS)
    assert lo.min_swing >= mid.min_swing >= hi.min_swing
    assert lo.min_speed >= mid.min_speed >= hi.min_speed
    assert lo.reversals >= hi.reversals
    assert params_for("bogus") == params_for("mid")


def test_high_catches_small_swing_low_does_not():
    small = swipe(4, amp=14.0, period=0.4)  # 28 px swing, 140 px/s
    assert any(run(PettingDetector("high"), small))
    assert not any(run(PettingDetector("low"), small))


def test_zone_helper_scales_with_window():
    x, y, w, h = 500.0, 300.0, 220.0, 287.0
    z = head_zone(x, y, w, h)
    assert x < z[0] < z[2] < x + w and y <= z[1] < z[3] < y + h * 0.5
    assert in_zone(z, (z[0] + z[2]) / 2, (z[1] + z[3]) / 2)
    assert not in_zone(z, x + w / 2, y + h * 0.9)


def test_reset():
    det = PettingDetector("mid")
    run(det, swipe(4))
    det.reset()
    assert not det.active
