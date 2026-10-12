"""Fall physics (Qt-free pieces) + window/rig integration."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from desk_pet_grok.focus_probe import FakeProbe, FieldGeom
from desk_pet_grok.lounge_driver import FALL_G, FallSim, landing_squash

K = 0.47
H = 220.0


def test_throws_up_then_falls_and_accelerates():
    sim = FallSim(300.0, K, H)
    ys, vs = [], []
    for _ in range(20):
        assert sim.step(1 / 60.0, None, 500.0, 5000.0) is None
        ys.append(sim.y)
        vs.append(sim.vy)
    assert min(ys) < 300.0  # went up first
    assert vs[0] < 0 < vs[-1]
    assert all(b >= a for a, b in zip(vs, vs[1:]))  # monotonic acceleration
    assert vs[-1] - vs[-2] == pytest.approx(FALL_G * K / 60.0, rel=0.02)


def test_lands_on_edge_below_inside_span():
    sim = FallSim(300.0, K, H)
    g = FieldGeom(100, 700, 800, 400, "window")
    kind, n = None, 0
    while kind is None and n < 600:
        kind = sim.step(1 / 60.0, g, 400.0, 5000.0)
        n += 1
    assert kind == "edge"
    assert sim.foot_y() == pytest.approx(g.y, abs=40)


def test_misses_edge_outside_span_and_hits_floor():
    sim = FallSim(300.0, K, H)
    g = FieldGeom(1200, 700, 300, 400, "window")  # she is at x=400: not above it
    kind, n = None, 0
    while kind is None and n < 900:
        kind = sim.step(1 / 60.0, g, 400.0, 900.0)
        n += 1
    assert kind == "ground"
    assert sim.foot_y() == pytest.approx(900.0, abs=0.01)


def test_edge_already_above_feet_is_ignored():
    sim = FallSim(800.0, K, H)
    g = FieldGeom(100, 300, 800, 400, "window")  # window top far above her feet
    kind, n = None, 0
    while kind is None and n < 900:
        kind = sim.step(1 / 60.0, g, 400.0, 1500.0)
        n += 1
    assert kind == "ground"


def test_landing_squash_curve():
    sx0, sy0 = landing_squash(0.0, 0.3)
    assert sy0 == pytest.approx(0.7) and sx0 > 1.0
    assert landing_squash(1.0, 0.3) == pytest.approx((1.0, 1.0))
    sy = [landing_squash(u / 20.0, 0.3)[1] for u in range(21)]
    assert min(sy) < 0.75 and max(sy[3:]) > 1.0  # squashes then rebounds past 1


# ---- window integration -------------------------------------------------------------------------------------------
from PySide6.QtWidgets import QApplication  # noqa: E402

from desk_pet_grok.state import StateMachine  # noqa: E402
from desk_pet_grok.window import PetWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _win(qapp):
    w = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "lounge": True})
    w.resize(220, 287)
    return w


def test_window_fall_sequence_to_edge_and_floor(qapp):
    w = _win(qapp)
    if not w.puppet_mode or not w.part_rig_available():
        pytest.skip("rig assets missing")
    said = []
    w.lounge_say.connect(said.append)
    probe = FakeProbe([FieldGeom(0, 300, 1400, 600, "window")])
    drv = w._lounge
    drv.probe = probe
    w.move(500, 300 - 287 + 14)
    assert drv.on_drop()
    for _ in range(100):
        drv.tick(0.05)
        drv._geom = probe.sample()
    assert drv.lounge.state == "lounge_loop"
    # window dragged far down: she falls onto the new edge, and shouts
    probe.set(FieldGeom(0, 600, 1400, 600, "window"))
    drv._geom = probe.sample()
    states = set()
    for _ in range(300):
        drv.tick(1 / 30.0)
        drv._geom = probe.sample()
        states.add(drv.lounge.state)
        if drv.lounge.state == "lie_down":
            break
    assert "fall" in states and drv.lounge.state == "lie_down"
    assert "pet_fall" in said
    # now remove the edge below her: she falls to the floor, squashes, stands
    probe.set(FieldGeom(0, 5000, 100, 100, "window"))  # elsewhere, far away
    drv._geom = probe.sample()
    seen = []
    for _ in range(600):
        drv.tick(1 / 30.0)
        drv._geom = probe.sample()
        seen.append(drv.lounge.state)
        if drv.lounge.state == "idle":
            break
    assert "fall" in seen and "ground" in seen and seen[-1] == "idle"
    assert w._pet.falling() is False  # released
