"""v4-4: festival dates, time-of-day greetings, decorations, window wiring."""
from __future__ import annotations

import datetime as dt
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from desk_pet_grok import config, greeting, holidays  # noqa: E402

D = dt.date


@pytest.mark.parametrize("d,key", [
    ("2026-10-31", "halloween"), ("2026-12-24", "christmas"), ("2026-12-25", "christmas"), ("2027-01-01", "newyear"),
    ("2027-02-05", "cny"), ("2027-02-06", "cny"), ("2027-02-20", "lantern"), ("2026-06-19", "dragon"), ("2026-09-25", "midautumn"),
    ("2026-10-01", "national"), ("2028-01-26", "cny"), ("2028-02-09", "lantern"), ("2026-10-11", None), ("2026-03-04", None),
])
def test_festival_dates(d, key):
    assert holidays.festival_on(D.fromisoformat(d)) == key


def test_lunar_table_sane():
    for y, r in holidays.LUNAR.items():
        cny = D.fromisoformat(r["cny"])
        assert cny.year == y and (D.fromisoformat(r["lantern"]) - cny).days == 14
        assert 110 < (D.fromisoformat(r["dragon"]) - cny).days < 170 and 215 < (D.fromisoformat(r["midautumn"]) - cny).days < 260


def test_all_festival_items_have_art_and_specs():
    from desk_pet_grok import fx
    root = os.path.join(os.path.dirname(__file__), "..", "assets", "festival25d")
    for key, (_l, head, (a, b)) in holidays.FESTIVALS.items():
        if head:
            assert head in fx.HEAD_SPEC and os.path.isfile(os.path.join(root, head + ".png")), key
        for it in (a, b):
            if it:
                assert it in fx.SIDE_W and os.path.isfile(os.path.join(root, it + ".png")), key


@pytest.mark.parametrize("h,p", [(0, "dawn"), (4, "dawn"), (5, "morning"), (10, "morning"), (11, "noon"), (13, "noon"), (14, "afternoon"),
                                 (17, "afternoon"), (18, "evening"), (21, "evening"), (22, "night"), (23, "night")])
def test_period(h, p):
    assert greeting.period_of(h) == p


def test_greeter_once_per_period_per_day():
    g = greeting.Greeter()
    t = dt.datetime(2026, 10, 11, 9, 0)
    assert g.due(t) == "morning"
    g.mark("morning", t)
    assert g.due(t.replace(hour=10)) is None
    assert g.due(t.replace(hour=12)) == "noon"
    assert g.due(t + dt.timedelta(days=1)) == "morning"  # next day greets again
    g2 = greeting.Greeter(g.seen)
    assert g2.due(t) is None  # persisted


def test_defaults_and_lines():
    assert config._DEFAULTS["time_greeting"] is True and config._DEFAULTS["holiday_outfit"] is True
    from desk_pet_grok import lines_v4
    from desk_pet_grok.meow import ends_with_meow
    for p in greeting.LABEL:
        assert "greet_" + p in lines_v4.POOLS
    for k in holidays.FESTIVALS:
        assert "festival_" + k in lines_v4.POOLS
    for cat, pool in lines_v4.POOLS.items():
        if cat.startswith(("greet_", "festival_")):
            assert all(ends_with_meow(s) and len(s) <= 24 for s in pool), cat


def _win(qapp, tmp_path, **s):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    base = {"puppet25d": True, "part_rig": True, "window_height": 300}
    base.update(s)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.show()
    return w


def test_window_greets_once_and_decorates(qapp, tmp_path):
    w = _win(qapp, tmp_path)
    said = []
    w.lounge_say.connect(said.append)
    now = dt.datetime(2026, 10, 31, 9, 0)
    cur = [(10, 10)]
    for i in range(40):  # 40 * 5 s, cursor keeps moving
        cur[0] = (10 + i * 40, 10)
        w._greet_tick(5.0, now, cur[0])
    assert said == ["festival_halloween"]  # festival line replaces the period line the first time that day
    assert w._pet.holiday() == "halloween"
    w._pet.grab()
    for _ in range(90):
        w._pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert w._pet._hol_a > 0.99
    # a later period the same day: plain period line
    said.clear()
    later = now.replace(hour=15)
    for i in range(3):
        cur[0] = (10 + i * 40, 50)
        w._greet_tick(5.0, later, cur[0])
    assert said == ["greet_afternoon"]
    w.close()


def test_greeting_needs_user_present_and_switch(qapp, tmp_path):
    w = _win(qapp, tmp_path)
    said = []
    w.lounge_say.connect(said.append)
    now = dt.datetime(2026, 10, 11, 9, 0)
    w._greet_tick(5.0, now, (100, 100))
    w._greet_state["idle"], w._greet_state["age"] = 500.0, 100.0  # user has been away
    for _ in range(60):  # cursor never moves
        w._greet_tick(5.0, now, (100, 100))
    assert said == []
    w._greet_tick(5.0, now, (400, 300))
    assert said == ["greet_morning"]
    w.set_time_greeting(False)
    said.clear()
    for i in range(10):
        w._greet_tick(5.0, now.replace(hour=12), (i * 50, 5))
    assert said == []
    w.set_holiday_outfit(False)
    w._greet_tick(5.0, dt.datetime(2026, 10, 31, 12), (1, 1))
    assert w._pet.holiday() is None
    w.close()


def test_greet_effect_face_returns(qapp, tmp_path):
    w = _win(qapp, tmp_path)
    pet = w._pet
    pet.greet("sun", "happy", hold=0.5)
    assert pet._greet_fx.active() and pet._expr is not None
    for _ in range(120):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._expr is None and pet._mood_to == "calm"
    w.close()
