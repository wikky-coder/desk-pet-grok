import random

from desk_pet_grok import lounge as L
from desk_pet_grok.focus_probe import FieldGeom

G = FieldGeom(100, 200, 800, 500, "window")


def mk(**kw):
    return L.Lounge(rng=random.Random(1), **kw)


def run(lg, secs, geom=G, dt=0.1, **kw):
    frames = []
    for _ in range(int(secs / dt)):
        frames.append(lg.tick(dt, geom, **kw))
    return frames


def says(frames):
    return [f.say for f in frames if f.say]


def test_starts_idle_and_disabled_ignores_drop():
    lg = mk()
    assert lg.state == "idle" and lg.tick(0.1, G).anchor is None
    lg.set_enabled(False)
    assert lg.on_drop(G, 300) is False and lg.state == "idle"


def test_drop_lies_down_then_loops_with_start_line():
    lg = mk()
    assert lg.on_drop(G, 300.0)
    assert lg.state == "lie_down"
    fr = run(lg, 3.0)
    assert lg.state == "lounge_loop"
    assert fr[-1].pose_loaf == 1.0
    assert "lounge_start" in says(fr)
    assert fr[-1].anchor == (300.0, 200.0)


def test_anchor_follows_moving_window_and_clamps():
    lg = mk()
    lg.on_drop(G, 120.0)
    f = lg.tick(0.1, FieldGeom(400, 230, 800, 500))  # small drop: followed, not fallen from
    assert f.anchor == (440.0, 230.0)  # clamped by margin to the new window
    assert lg.state == "lie_down"


def test_field_gone_gets_up_after_hysteresis_and_cooldown():
    lg = mk()
    lg.on_drop(G, 300.0)
    run(lg, 3.0)
    run(lg, 1.0, geom=None)  # 1 s lost: still lounging
    assert lg.state == "lounge_loop"
    fr = run(lg, 2.0, geom=None)
    assert lg.state in ("get_up", "idle")
    assert "lounge_end" in says(fr)
    run(lg, 2.0, geom=None)
    assert lg.state == "idle" and lg.cooldown_left > 0


def test_brief_loss_is_forgiven():
    lg = mk()
    lg.on_drop(G, 300.0)
    run(lg, 3.0)
    run(lg, 1.0, geom=None)
    run(lg, 0.5)
    run(lg, 1.5, geom=None)
    assert lg.state == "lounge_loop"


def test_drag_start_interrupts_immediately_without_line():
    lg = mk()
    lg.on_drop(G, 300.0)
    fr = run(lg, 3.0)
    lg.on_drag_start()
    assert lg.state == "idle"
    assert "lounge_end" not in says(run(lg, 1.0, geom=None))


def test_yawn_then_sleep_after_threshold_and_poke_wakes():
    lg = mk()
    lg.on_drop(G, 300.0)
    fr = run(lg, L.SLEEP_AFTER_S - 5, dt=0.5)
    assert "yawn" in says(fr)
    fr2 = run(lg, 20.0, dt=0.5)
    assert lg.state == "sleep"
    assert fr2[-1].pose_droop > 0.9
    lg.poke()
    assert lg.state == "lounge_loop"
    f = lg.tick(0.1, G)
    assert f.pose_droop < 1.0


def test_sleep_lines_come_from_sleep_category():
    lg = mk()
    lg.on_drop(G, 300.0)
    run(lg, L.SLEEP_AFTER_S + 5, dt=0.5)
    s = says(run(lg, 200.0, dt=0.5))
    assert s and set(s) <= {"lounge_sleep"}


def test_lounge_chatter_is_sparse():
    lg = mk()
    lg.on_drop(G, 300.0)
    fr = run(lg, 120.0, dt=0.5)
    n = says(fr).count("lounge")
    assert 1 <= n <= 4


def test_self_walk_only_when_enabled_idle_long_and_target_present():
    lg = mk(selfwalk=False)
    assert all(f.state == "idle" for f in run(lg, 700.0, dt=1.0, idle_s=900.0))
    lg = mk(selfwalk=True)
    assert all(f.state == "idle" for f in run(lg, 120.0, dt=1.0, idle_s=30.0))
    assert all(f.state == "idle" for f in run(lg, 120.0, geom=None, dt=1.0, idle_s=900.0))
    fr = run(lg, 300.0, dt=1.0, idle_s=900.0)
    assert any(f.state == "walk_to_field" for f in fr)
    assert "self_walk" in says(fr)
    lg.tick(0.1, G, arrived=True, idle_s=900.0)
    assert lg.state == "lie_down"


def test_walk_to_field_cancelled_by_drag_or_loss():
    lg = mk(selfwalk=True)
    for _ in range(3000):
        lg.tick(1.0, G, idle_s=900.0)
        if lg.state == "walk_to_field":
            break
    assert lg.state == "walk_to_field"
    lg.on_drag_start()
    assert lg.state == "idle" and lg.cooldown_left > 0


def _settled():
    lg = mk()
    lg.on_drop(G, 300.0)
    run(lg, 3.0)
    assert lg.state == "lounge_loop"
    return lg


def test_edge_dropping_fast_makes_her_fall_with_line():
    lg = _settled()
    low = FieldGeom(100, 200 + L.FALL_GAP + 40, 800, 500, "window")
    f = lg.tick(0.1, low)
    assert lg.state == "fall" and f.say == "pet_fall" and f.anchor is None


def test_slow_drift_down_is_followed():
    lg = _settled()
    y = 200.0
    for _ in range(100):  # 40 px/s for 10 s = 400 px: slower than FALL_FOLLOW
        y += 4.0
        lg.tick(0.1, FieldGeom(100, y, 800, 500, "window"))
        assert lg.state != "fall"


def test_edge_rising_never_falls():
    lg = _settled()
    for y in (190, 150, 100, 20):
        lg.tick(0.1, FieldGeom(100, y, 800, 500, "window"))
        assert lg.state != "fall"


def test_fall_lands_on_edge_and_lies_down_again():
    lg = _settled()
    low = FieldGeom(100, 400, 800, 500, "window")
    lg.tick(0.1, low)
    assert lg.state == "fall"
    f = lg.tick(0.1, low)
    assert f.pose_loaf < 1.0 and f.anchor is None  # snaps upright while falling
    lg.on_land("edge", low, 350.0)
    assert lg.state == "lie_down"
    f = lg.tick(0.1, low)
    assert f.anchor == (350.0, 400.0)
    run(lg, 3.0, geom=low)
    assert lg.state == "lounge_loop"


def test_fall_to_ground_recovers_to_idle():
    lg = _settled()
    lg.tick(0.1, FieldGeom(100, 600, 800, 500, "window"))
    assert lg.state == "fall"
    lg.on_land("ground")
    assert lg.state == "ground"
    run(lg, L.GROUND_S + 0.3, geom=None)
    assert lg.state == "idle" and lg.cooldown_left > 0


def test_fall_has_time_cap_and_land_outside_fall_is_ignored():
    lg = _settled()
    lg.on_land("ground")
    assert lg.state == "lounge_loop"  # not falling: ignored
    lg.tick(0.1, FieldGeom(100, 700, 800, 500, "window"))
    run(lg, L.FALL_MAX_S + 0.5, geom=None, dt=0.5)
    assert lg.state in ("ground", "idle")


def test_fall_threshold_configurable():
    lg = _settled()
    lg.fall_gap = 500.0
    lg.tick(0.1, FieldGeom(100, 600, 800, 500, "window"))
    assert lg.state != "fall"
