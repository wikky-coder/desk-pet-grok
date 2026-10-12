"""v4-5: power saving."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from desk_pet_grok import config, powersave  # noqa: E402
from desk_pet_grok.powersave import PowerSaver  # noqa: E402


def test_default_off():
    assert config._DEFAULTS["power_save"] is False
    p = PowerSaver()
    for _ in range(5000):
        assert p.feed(0.1, False) is None
    assert p.interval == powersave.NORMAL_MS


def test_slows_after_idle_and_restores():
    p = PowerSaver(enabled=True)
    seen = []
    for _ in range(700):  # 70 s idle at 0.1 s steps
        r = p.feed(0.1, False)
        if r is not None:
            seen.append((round(p.idle), r))
    assert seen == [(30, powersave.LOW_MS), (60, powersave.DEEP_MS)]
    assert p.feed(0.1, True) == powersave.NORMAL_MS and p.idle == 0.0


def test_activity_resets_before_threshold():
    p = PowerSaver(enabled=True)
    for _ in range(290):
        p.feed(0.1, False)
    p.feed(0.1, True)
    for _ in range(290):
        assert p.feed(0.1, False) is None


def test_switch_off_restores_rate():
    p = PowerSaver(enabled=True)
    for _ in range(400):
        p.feed(0.1, False)
    assert p.interval == powersave.LOW_MS
    p.enabled = False
    assert p.feed(0.1, False) == powersave.NORMAL_MS


def _win(qapp, tmp_path, **s):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    base = {"puppet25d": True, "part_rig": True, "window_height": 300}
    base.update(s)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.show()
    return w


def test_window_timer_slows_and_wakes(qapp, tmp_path):
    w = _win(qapp, tmp_path, power_save=True)
    assert w.power_save and w._motion_timer.interval() == 33
    for _ in range(70):
        w._power_tick(1.0, False, cursor=(5, 5), buttons=False)
    assert w._motion_timer.interval() == powersave.DEEP_MS
    w._power_tick(0.1, False, cursor=(300, 5), buttons=False)  # cursor moved
    assert w._motion_timer.interval() == 33
    for _ in range(35):
        w._power_tick(1.0, False, cursor=(300, 5), buttons=False)
    assert w._motion_timer.interval() == powersave.LOW_MS
    w._power_tick(0.1, True, cursor=(300, 5), buttons=False)  # dragging
    assert w._motion_timer.interval() == 33
    for _ in range(35):
        w._power_tick(1.0, False, cursor=(300, 5), buttons=False)
    w.set_power_save(False, persist=False)
    assert w._motion_timer.interval() == 33
    w.close()


def test_walking_window_counts_as_active(qapp, tmp_path):
    w = _win(qapp, tmp_path, power_save=True)
    for i in range(40):
        w.move(w.x() + 3, w.y())
        w._power_tick(1.0, False, cursor=(5, 5), buttons=False)
    assert w._motion_timer.interval() == 33
    w.close()
