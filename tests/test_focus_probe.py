from desk_pet_grok.focus_probe import (
    FakeProbe,
    FieldGeom,
    anchor_for,
    clamp_anchor_to_screens,
    pick_front_window,
)


def W(layer=0, pid=100, x=100, y=80, w=800, h=600, alpha=1.0):
    return {"layer": layer, "pid": pid, "x": x, "y": y, "w": w, "h": h, "alpha": alpha}


def test_pick_front_window_skips_own_menubar_tiny_and_transparent():
    entries = [
        W(layer=25, pid=1, y=0, w=1440, h=24),  # menu bar
        W(pid=999, x=10, y=10),  # own process
        W(w=50, h=40),  # tiny
        W(alpha=0.0),  # invisible
        W(pid=200, x=300, y=120, w=900, h=700),  # the one
        W(pid=300),
    ]
    g = pick_front_window(entries, own_pid=999)
    assert g == FieldGeom(300.0, 120.0, 900.0, 700.0, "window", "")


def test_pick_front_window_none_when_nothing_usable():
    assert pick_front_window([], own_pid=1) is None
    assert pick_front_window([W(layer=3)], own_pid=1) is None


def test_anchor_clamps_x_inside_geometry_and_uses_top_edge():
    g = FieldGeom(100, 200, 500, 300, "window")
    assert anchor_for(g, prefer_x=50, margin=40) == (140.0, 200.0)
    assert anchor_for(g, prefer_x=900, margin=40) == (560.0, 200.0)
    assert anchor_for(g, prefer_x=300, margin=40) == (300.0, 200.0)
    narrow = FieldGeom(100, 200, 60, 30, "field")
    assert anchor_for(narrow, prefer_x=0, margin=40) == (130.0, 200.0)  # too narrow -> centre


def test_clamp_anchor_to_screens_multi_monitor_and_negative_origin():
    screens = [(0, 0, 1440, 900), (-1920, 0, 1920, 1080)]
    assert clamp_anchor_to_screens((-500.0, 300.0), screens) == (-500.0, 300.0)
    assert clamp_anchor_to_screens((2000.0, 300.0), screens) is None
    assert clamp_anchor_to_screens((100.0, -5.0), screens) == (100.0, 0.0)  # top edge above screen -> clamp down


def test_fake_probe_scripted_sequence():
    a = FieldGeom(0, 0, 100, 100, "window")
    p = FakeProbe([a, None, a])
    assert p.sample() == a and p.sample() is None and p.sample() == a
    assert p.sample() == a  # last value repeats
    p.set(None)
    assert p.sample() is None
