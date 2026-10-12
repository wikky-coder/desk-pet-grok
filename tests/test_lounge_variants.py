"""F7: lying-pose variants (side / chin / stretch / curl): assets, switching, sleep->curl, fallbacks, head zone."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_lounge_pet import _lie, _WINS, _restore_cfg_env, needs_art, qapp  # noqa: E402,F401

from desk_pet_grok import config, loungeart  # noqa: E402

NAMES = ("side", "chin", "stretch", "curl")


def test_assets_and_json_are_complete():
    assert loungeart.variant_names() == list(NAMES)
    for n in NAMES:
        d = loungeart.VARIANT_DIR / n
        j = json.loads((d / "lounge.json").read_text())
        assert j["fw"] == 720 and j["cols"] == 4 and j["breath_frames"] == 1 and j["breath"] == "runtime"
        assert (d / j["poses"]["base"]["file"]).is_file()
        x0, y0, x1, y1 = j["head_zone"]
        assert 0 <= x0 < x1 <= j["fw"] and 0 <= y0 < y1 <= j["fh"]
        assert abs(j["scale"] - 0.34675615212527966) < 1e-9  # same scale as the base art: head size stays consistent
    for n in ("side", "chin"):  # eyes poses so dozing / sleeping work in these
        j = json.loads((loungeart.VARIANT_DIR / n / "lounge.json").read_text())
        assert {"half", "sleep"} <= set(j["poses"]) and j["poses"]["base"]["frames"] == 5
    for n in ("stretch", "curl"):
        assert json.loads((loungeart.VARIANT_DIR / n / "lounge.json").read_text())["poses"]["base"]["frames"] == 1


def test_variant_art_loads_and_flick_only_where_frames_exist(qapp):
    for n in NAMES:
        a = loungeart.LoungeArt(loungeart.VARIANT_DIR / n)
        assert a.variant == n and a.has_flick == (n in ("side", "chin"))
        a.set_pose(1.0, 0.0, 0.0)
        a.start_flick()
        assert (a.flick_t >= 0) == a.has_flick
        for _ in range(200):
            a.step(1 / 30)
            assert a.frame_index() < (11 if a.has_flick else 7)
    base = loungeart.LoungeArt()
    assert base.variant == "base" and base.has_flick and base.head_zone_frame == loungeart.HEAD_ZONE_FRAME


def test_default_off():
    assert config._DEFAULTS["lounge_variants"] is False


@needs_art
def test_flag_off_keeps_the_single_loaf_pose(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    assert win.lounge_variants is False
    for _ in range(2000):
        pet.drive(1 / 30, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.lounge_variant() == "base"
    assert [a for a, *_ in pet._active_arts()] == [pet._lounge_art]


@needs_art
def test_flag_on_switches_by_ducking_never_blending_two_poses(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    pet._var_start("base", instant=True)
    pet._var_start("side")
    seen = []
    for _ in range(60):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
        arts = pet._active_arts()
        assert len(arts) == 1  # one pose at a time (duck out, then pop in)
        seen.append((arts[0][0].variant, arts[0][1]))
    assert seen[0][0] == "base" and seen[-1] == ("side", 1.0)
    mults = [m for _, m in seen]
    assert min(mults) < 0.1  # fully hidden at the swap
    assert all(abs(b - a) < 0.35 for a, b in zip(mults, mults[1:]))  # no pop


@needs_art
def test_random_rotation_waits_and_respects_petting(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    pet._var_start("base", instant=True)
    pet._var_next = pet._var_clock + 5.0
    pet.set_lounge((1.0, 0.0, 0.0))
    for _ in range(60 * 4):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.lounge_variant() == "base"  # not due yet
    pet._pat = 1.0  # being patted: do not rearrange her
    pet._pat_on = True
    for _ in range(60 * 3):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
        pet._pat = 1.0
    assert pet.lounge_variant() == "base"
    pet._pat_on = False
    for _ in range(60 * 3):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.lounge_variant() != "base" and pet.lounge_variant() != "curl"


@needs_art
def test_falls_asleep_into_curl_and_wakes_back_to_her_pose(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    pet._var_start("chin", instant=True)
    pet.set_lounge((1.0, 1.0, 0.0))  # asleep
    for _ in range(90):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.lounge_variant() == "curl" and pet._var_t == 1.0
    pet.set_lounge((1.0, 0.0, 0.0))  # woken
    for _ in range(90):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.lounge_variant() == "chin"


@needs_art
def test_missing_variant_assets_fall_back_to_base(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(loungeart, "VARIANT_DIR", tmp_path / "nothing")
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    assert pet._var_options() == ["base"]
    pet._var_start("side")
    assert pet.lounge_variant() == "base"
    pet.set_lounge((1.0, 1.0, 0.0))
    for _ in range(60):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.lounge_variant() == "base"
    assert [a for a, *_ in pet._active_arts()] == [pet._lounge_art]


@needs_art
def test_head_zone_follows_the_variant_and_stays_in_window(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    zones = {}
    for v in ("base",) + NAMES:
        pet._var_start(v, instant=True)
        pet._var_from = pet._var_to = v
        z = pet.lounge_head_zone(float(win.width()), float(win.height()))
        assert z is not None and 0 <= z[0] < z[2] <= win.width() and 0 <= z[1] < z[3] <= win.height()
        zones[v] = z
    assert zones["curl"] != zones["base"] and zones["chin"] != zones["side"]


@needs_art
def test_pat_still_works_with_a_variant(qapp, tmp_path):
    import math
    from test_lounge_pet import Clock, _zone_center
    win, drv = _lie(tmp_path)
    win.set_lounge_variants(True, persist=False)
    pet = win._pet
    pet._var_start("side", instant=True); pet._var_from = pet._var_to = "side"
    pet._var_next = 1e9
    c = Clock(win, drv)
    cx, cy, _ = _zone_center(win)
    for i in range(90):
        c.step(cx + 20 * math.sin(2 * math.pi * 2.0 * i / 30), cy)
    assert win._pat_now and pet.lounge_variant() == "side"


def test_menu_and_settings_row(qapp):
    from test_settings_panel import Model
    from desk_pet_grok.menu import build_pet_menu
    from desk_pet_grok.settings_panel import SettingsPanel, build_sections
    st = {"v": False}
    cb = Model().cb(); cb.is_lounge_variants = lambda: st["v"]; cb.set_lounge_variants = lambda v: st.update(v=v)
    menu = build_pet_menu(None, cb)
    acts = [a for a in menu.actions() if "多种趴姿" in a.text()]
    assert len(acts) == 1 and not acts[0].isChecked()
    acts[0].trigger()
    assert st["v"] is True
    p = SettingsPanel(build_sections(cb, ax_trusted=lambda: False, open_ax=lambda: None))
    p.checkbox_for("多种趴姿").setChecked(False)
    assert st["v"] is False


# ---- stretch is a transition pose ----
def _run(pet, secs, fps=60, **kw):
    for _ in range(int(secs * fps)):
        pet.drive(1 / fps, want_walk=False, facing=1, look=False, dragging=False)


def _enter_stretch(pet, frm="chin"):
    pet._var_start(frm, instant=True); pet._var_from = pet._var_to = frm
    pet._stretch_end = -1e9
    pet._var_start("stretch")
    _run(pet, 0.7)
    assert pet.lounge_variant() == "stretch"


@needs_art
def test_stretch_is_never_the_initial_pose(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    assert "stretch" not in pet._var_options(initial=True)
    for seed in range(40):
        pet._var_rng.seed(seed)
        pet.set_lounge(None)
        pet.set_lounge((0.0, 0.0, 0.0))  # lying down again
        assert pet.lounge_variant() != "stretch"


@needs_art
def test_stretch_lasts_whole_cycles_of_4_to_8_seconds_then_a_stable_pose(qapp, tmp_path):
    for seed in range(6):
        win, drv = _lie(tmp_path)
        pet = win._pet
        win.set_lounge_variants(True, persist=False)
        pet._var_rng.seed(seed)
        pet.set_lounge((1.0, 0.0, 0.0))
        _enter_stretch(pet, "chin")
        t0 = pet._var_clock
        n = pet._stretch_cycles
        art = pet._art_for("stretch")
        while pet.lounge_variant() == "stretch":
            _run(pet, 1 / 30)
            assert pet._var_clock - t0 < 9.0
        stay = pet._var_clock - t0
        total = stay + 0.7  # 0.7 s were run before t0 (incl. the 0.6 s fade-in)
        assert 4.0 <= total <= 8.5, total
        assert art.phase >= 12.0 * n - 1e-6  # left on a full-cycle boundary, never mid-stretch
        assert n in (3, 4) and total >= 2.0 * n - 0.1
        _run(pet, 0.8)
        assert pet.lounge_variant() in ("base", "side", "chin") and pet.lounge_variant() != "stretch"
        assert pet.lounge_variant() != "chin"  # a different stable pose than before


@needs_art
def test_no_back_to_back_stretch_and_60s_gap(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    pet.set_lounge((1.0, 0.0, 0.0))
    _enter_stretch(pet)
    while pet.lounge_variant() == "stretch":
        _run(pet, 0.1)
    end = pet._stretch_end
    assert "stretch" not in pet._var_options()  # right after: not allowed
    pet._var_clock = end + 59.0
    assert "stretch" not in pet._var_options()
    pet._var_clock = end + 61.0
    assert "stretch" in pet._var_options()
    # rotation never picks stretch inside the gap, across many draws
    pet._var_clock = end + 5.0
    for seed in range(60):
        pet._var_rng.seed(seed)
        assert "stretch" not in pet._var_options()


@needs_art
def test_petting_interrupts_stretch_smoothly(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    pet.set_lounge((1.0, 0.0, 0.0))
    _enter_stretch(pet, "side")
    pet._pat_on = True; pet._pat = 1.0
    _run(pet, 0.05)
    seen = []
    for _ in range(60):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
        pet._pat = 1.0
        arts = pet._active_arts()
        assert len(arts) == 1
        seen.append((arts[0][0].variant, arts[0][1]))
    assert seen[-1][0] in ("base", "chin") and seen[-1][1] == 1.0  # soft duck out / in, not a cut
    assert min(m for _, m in seen) < 0.1


@needs_art
def test_sleep_and_yawn_still_win_over_stretch(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    pet.set_lounge((1.0, 0.0, 0.0))
    _enter_stretch(pet)
    pet.set_lounge((1.0, 1.0, 0.0))
    _run(pet, 1.5)
    assert pet.lounge_variant() == "curl"
    pet.set_lounge((1.0, 0.0, 0.0))
    _run(pet, 1.5)
    _enter_stretch(pet)
    pet.set_lounge((1.0, 0.0, 1.0))  # yawning
    _run(pet, 1.5)
    assert pet.lounge_variant() != "stretch"


@needs_art
def test_variant_interval_is_random_40_120_and_redrawn_each_time(qapp, tmp_path):
    from desk_pet_grok import config
    assert config._DEFAULTS["lounge_variant_interval"] == [40, 120]
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    assert pet.variant_interval() == (40.0, 120.0)
    gaps = []
    for _ in range(300):
        before = pet._var_clock
        pet._var_start("base", instant=True)  # same pose: no draw
        pet._var_to = "side"
        pet._var_start("chin", instant=True)
        gaps.append(pet._var_next - pet._var_clock)
    assert all(40.0 <= g <= 120.0 for g in gaps)
    assert len({round(g, 3) for g in gaps}) > 250  # a fresh draw every time, not a fixed number
    assert 70 < sum(gaps) / len(gaps) < 90 and min(gaps) < 50 and max(gaps) > 110  # roughly uniform over the whole range


@needs_art
def test_variant_interval_setting_clamps_and_applies(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    assert pet.variant_interval() == (40.0, 120.0)  # default
    from desk_pet_grok.window import PetWindow
    from desk_pet_grok.state import StateMachine
    w2 = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "part_rig": True, "lounge_variant_interval": [30, 50]})
    assert w2._pet.variant_interval() == (30.0, 50.0)
    w2.close()
    assert pet.set_variant_interval(5, 2) == (10.0, 10.0)
    assert pet.set_variant_interval(1e9, 1e9) == (900.0, 900.0)
    assert pet.set_variant_interval(60, 20) == (60.0, 60.0)  # max below min -> equals min
    assert pet.set_variant_interval("x", None) == (40.0, 120.0)
    assert pet.set_variant_interval(float("nan"), 3) == (40.0, 120.0)


@needs_art
def test_rotation_holds_while_busy_then_switches_when_free(qapp, tmp_path):
    win, drv = _lie(tmp_path)
    pet = win._pet
    win.set_lounge_variants(True, persist=False)
    pet._var_start("base", instant=True)
    pet.set_lounge((1.0, 0.0, 0.0))
    for _ in range(30):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    v0 = pet.lounge_variant()
    pet._var_next = pet._var_clock + 0.2
    for busy in ("pat", "yawn", "droop"):
        pet.set_lounge((1.0, 0.6, 0.0) if busy == "droop" else (1.0, 0.0, 1.0 if busy == "yawn" else 0.0))
        if busy == "pat":
            pet._pat_on = True
            pet._pat = 1.0
        for _ in range(60 * 2):
            pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
            if busy == "pat":
                pet._pat, pet._pat_on = 1.0, True
        assert pet.lounge_variant() == v0, busy  # due, but she is being petted / yawning / drowsy: no switch
        pet._pat, pet._pat_on = 0.0, False
    pet.set_lounge((1.0, 0.0, 0.0))
    for _ in range(60 * 3):
        pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert pet.lounge_variant() != v0
    assert pet._var_next - pet._var_clock > 30.0  # re-drawn afresh after the switch
