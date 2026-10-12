"""v4-2: shake -> anger ladder (logic, art, window wiring)."""
from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import mkwin, qapp  # noqa: E402,F401

from desk_pet_grok import config, lines, lines_v4, shake  # noqa: E402
from desk_pet_grok.meow import ends_with_meow  # noqa: E402
from desk_pet_grok.shake import AngerMachine, ShakeMeter  # noqa: E402


def whip(m, secs, hz=2.5, amp=120.0, t0=0.0, dt=1 / 60):
    t = t0
    ev = []
    for _ in range(int(secs / dt)):
        t += dt
        m.drag_sample(t, amp * math.sin(2 * math.pi * hz * t))
        m.tick(t, dt)
        ev += m.drain()
    return t, ev


def test_defaults_off():
    assert config._DEFAULTS["shake_anger"] is False
    assert AngerMachine().enabled is False


def test_meter_counts_fast_swings_only():
    for hz, amp, expect in ((2.5, 120, True), (1.0, 120, False), (3.0, 20, False), (0.5, 300, False)):
        m = ShakeMeter(); t = 0.0
        for _ in range(60 * 6):
            t += 1 / 60; m.feed(t, amp * math.sin(2 * math.pi * hz * t))
        assert (m.strength > 4.0) is expect, (hz, amp, m.strength)


def test_ladder_order_and_timing():
    m = AngerMachine(enabled=True)
    t, ev = whip(m, 6.0)
    stages = [e[1] for e in ev if e[0] == "stage"]
    assert stages == [1, 2, 3, 4]  # dizzy -> annoyed -> puffed -> fuming, no skipping
    assert m.stage == 4
    assert [shake.FACE[i] for i in (1, 2, 3, 4)] == ["dizzy", "annoyed", "puffed", "fuming"]


def test_light_shake_only_dizzy_and_it_fades():
    m = AngerMachine(enabled=True)
    t, ev = whip(m, 1.1)
    assert m.stage in (1, 2)
    m.release()
    for _ in range(60 * 20):
        t += 1 / 60; m.tick(t, 1 / 60)
    assert m.stage == 0  # dizzy / annoyed recover by themselves


def test_puffed_and_fuming_latch_until_pat_then_sulk():
    m = AngerMachine(enabled=True)
    t, _ = whip(m, 3.4)
    assert m.stage == 3
    m.release()
    for _ in range(60 * 30):
        t += 1 / 60; m.tick(t, 1 / 60)
    assert m.stage == 3  # does not calm by itself
    m2 = AngerMachine(enabled=True)
    t, _ = whip(m2, 6.0); m2.release()
    for _ in range(60 * 4):
        t += 1 / 60; m2.tick(t, 1 / 60)
    assert m2.stage == 5  # fuming + left alone -> back turned


def test_pat_soothes_step_by_step():
    m = AngerMachine(enabled=True)
    t, _ = whip(m, 6.0); m.release()
    for _ in range(60 * 4):
        m.tick(t, 1 / 60)
    assert m.stage == 5
    m.drain()
    for _ in range(int(0.5 * 60)):
        m.pat(True, 1 / 60)
    assert m.stage == 5  # a step needs ~0.9 s
    for _ in range(int(0.6 * 60)):
        m.pat(True, 1 / 60)
    assert m.stage == 4 and ("soothe", 4, 5) in m.drain()  # turned back round, still fuming
    for _ in range(int(1.0 * 60)):
        m.pat(True, 1 / 60)
    assert m.stage == 3 and ("soothe", 3, 4) in m.drain()
    for _ in range(int(1.0 * 60)):
        m.pat(True, 1 / 60)
    assert m.stage == 0 and ("calm", 3) in m.drain()
    # short pauses keep the progress; a long pause forgets it
    t, _ = whip(m, 6.0); m.release()
    for _ in range(60 * 4):
        m.tick(t, 1 / 60)
    for _ in range(40):
        m.pat(True, 1 / 60)
    for _ in range(90):  # 1.5 s pause
        m.pat(False, 1 / 60)
    for _ in range(25):
        m.pat(True, 1 / 60)
    assert m.stage == 4
    m2 = AngerMachine(enabled=True)
    whip(m2, 4.0); m2.release()
    assert m2.stage >= 3
    for _ in range(50):
        m2.pat(True, 1 / 60)
    for _ in range(60 * 3):  # 3 s pause
        m2.pat(False, 1 / 60)
    for _ in range(20):
        m2.pat(True, 1 / 60)
    assert m2.stage >= 3


def test_light_stage_is_soothed_quickly_by_a_pat():
    m = AngerMachine(enabled=True)
    whip(m, 1.2); assert m.stage >= 1
    m.pat(True, 0.5)
    assert m.stage == 0


def test_disabled_ignores_everything_and_clears():
    m = AngerMachine(enabled=False)
    _, ev = whip(m, 5.0)
    assert m.stage == 0 and ev == []
    m.enabled = True; whip(m, 5.0); assert m.stage > 0
    m.enabled = False; m.tick(100.0, 0.1)
    assert m.stage == 0


def test_auto_calm_after_ten_minutes():
    m = AngerMachine(enabled=True)
    t, _ = whip(m, 4.0); m.release()
    for _ in range(60 * 601):
        t += 1 / 60; m.tick(t, 1 / 60)
    assert m.stage == 0


def test_lines_end_with_meow_and_short():
    for cat in shake.LINE.values():
        pool = lines_v4.POOLS[cat]
        assert len(pool) >= 4 and cat in lines_v4.EVENT_CATEGORIES
        assert all(ends_with_meow(s) for s in pool), pool
        assert all(len(s) <= 24 for s in pool)
        assert lines.lines_for(cat) == pool


def test_assets_exist():
    root = os.path.join(os.path.dirname(__file__), "..", "assets")
    for n in ("dizzy", "puffed", "fuming"):
        assert os.path.isfile(os.path.join(root, "rig25d", f"face_{n}.png"))
    assert os.path.isfile(os.path.join(root, "shake25d", "sulk_back.png"))


def test_pet_faces_and_sulk_fade(qapp, tmp_path):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "shake_anger": True, "window_height": 300})
    win.show()
    pet = win._pet
    assert win._mood.enabled is False  # works without the F6 mood switch
    for st, face in ((1, "dizzy"), (2, "annoyed"), (3, "puffed"), (4, "fuming")):
        pet.set_anger(st)
        for _ in range(40):
            pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
        assert pet.mood() == face and pet.mood_visible() and pet._rig.mood_mix[1] == face
    pet.set_anger(5)
    for _ in range(60):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._sulk_t > 0.99 and pet._sulk_sprite() is not None
    pet.set_anger(0)
    for _ in range(90):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet._sulk_t < 0.01 and pet.mood() == "calm" and not pet.mood_visible()
    win.close()


def test_window_wiring_end_to_end(qapp, tmp_path):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    win = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "shake_anger": True, "window_height": 300})
    win.show()
    said = []
    win.lounge_say.connect(said.append)
    t = 100.0
    for i in range(60 * 6):
        t += 1 / 60
        win._anger.drag_sample(t, 120 * math.sin(2 * math.pi * 2.5 * i / 60))
        win._anger_tick(1 / 60)
    assert win._pet.anger() == 4
    assert said[:4] == ["shake_dizzy", "shake_annoyed", "shake_puffed", "shake_fuming"]
    win._anger.release()
    for _ in range(60 * 4):
        win._anger_tick(1 / 60)
    assert win._pet.anger() == 5 and said[-1] == "shake_sulk"
    win._pat_now = True  # head pat
    for _ in range(60 * 5):
        win._anger_tick(1 / 60)
    win._pat_now = False
    assert win._pet.anger() == 0 and said[-1] == "shake_calm" and "anger_soothe" in said
    win.set_shake_anger(False, persist=False)
    assert win.shake_anger is False
    win.close()
