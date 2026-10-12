"""F6: mood state machine + face layers."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import mkwin, qapp  # noqa: E402,F401

from desk_pet_grok import config, mood, partrig  # noqa: E402
from desk_pet_grok.mood import MoodMachine  # noqa: E402


def run(m, secs, hour=12, dt=0.5):
    for _ in range(int(secs / dt)):
        m.tick(dt, hour)


def test_default_is_calm_and_switch_defaults_off():
    assert MoodMachine().current() == "calm"
    assert config._DEFAULTS["mood"] is False


def test_pat_makes_her_happy_then_it_decays_to_calm():
    m = MoodMachine(); m.event("pat")
    assert m.current() == "happy"
    run(m, 20); assert m.current() == "happy"
    run(m, 300); assert m.current() == "calm"


def test_fall_surprise_is_short():
    m = MoodMachine(); m.event("fall")
    assert m.current() == "surprised"
    run(m, 6); assert m.current() == "calm"


def test_rapid_poking_annoys_and_petting_soothes():
    m = MoodMachine(); m.event("poke"); m.event("poke")
    assert m.current() == "annoyed"
    run(m, 5)
    m.event("pat"); m.event("pat")
    assert m.current() == "happy"


def test_priority_and_neglect():
    m = MoodMachine(); m.event("neglect")
    assert m.current() == "pouty"
    m.event("fall")
    assert m.current() == "surprised"
    run(m, 10); assert m.current() == "pouty"
    run(m, 600); assert m.current() == "calm"


def test_night_sleepy_needs_idle_time_and_night_hour():
    m = MoodMachine(); run(m, 60, hour=2); assert m.current() == "calm"  # not idle long enough
    run(m, 90, hour=2); assert m.current() == "sleepy"
    m.event("pat"); assert m.current() == "happy"  # interaction wins
    d = MoodMachine(); run(d, 400, hour=14); assert d.current() == "calm"  # daytime: never
    assert mood.is_night(23) and mood.is_night(4) and not mood.is_night(5) and not mood.is_night(12)


def test_disabled_machine_ignores_everything():
    m = MoodMachine(enabled=False)
    for k in ("pat", "fall", "poke", "neglect"):
        m.event(k)
    run(m, 400, hour=2)
    assert m.current() == "calm"


def test_fade_is_0p3_to_0p6_seconds():
    assert 0.3 <= mood.FADE_S <= 0.6
    a, n = 0.0, 0
    while a < 1.0:
        a = mood.fade_step(a, 1 / 60); n += 1
    assert 0.3 <= n / 60 <= 0.6 + 1 / 60


def _drive(pet, secs, dt=1 / 60):
    out = []
    for _ in range(int(secs / dt)):
        pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False)
        out.append(pet._rig.mood_mix if pet._rig is not None else None)
    return out


def test_all_mood_faces_exist_and_match_head_box():
    from PIL import Image
    hb = Image.open(partrig.RIG_DIR / "head_base.png").size
    for n in ("cheerful", "surprised", "annoyed", "sleepy", "pouty"):
        im = Image.open(partrig.RIG_DIR / f"face_{n}.png")
        assert im.size == hb and im.mode == "RGBA"
    r = partrig.PartRig()
    assert all(r.has_mood_face(m) for m in mood.FACE_MOODS)


def test_pet_flag_off_means_no_change(qapp):
    w = mkwin(qapp, part_rig=True); w._motion_timer.stop()
    w.mood_event("fall")
    assert w._pet.mood() == "calm" and not w._pet.mood_visible()
    assert w.mood_enabled is False


def test_pet_crossfades_without_jumps_and_back_to_calm(qapp):
    w = mkwin(qapp, part_rig=True); w._motion_timer.stop()
    w.set_mood_enabled(True, persist=False)
    pet = w._pet
    w.mood_event("fall")
    assert pet.mood() == "surprised" and pet.mood_visible()
    mix = _drive(pet, 0.7)
    ts = [m[2] for m in mix]
    assert ts[-1] == 1.0 and all(b - a <= 0.16 for a, b in zip(ts, ts[1:]))  # no jump between frames
    first_full = next(i for i, t in enumerate(ts) if t >= 1.0) / 60
    assert 0.3 <= first_full <= 0.6
    faces = pet._rig.mood_faces()
    assert faces == [("surprised", 1.0)]
    w.mood_event("activity"); w._mood.reset(); w._mood_apply()
    assert pet.mood() == "calm"
    _drive(pet, 0.7)
    assert not pet.mood_visible()


def test_missing_face_art_falls_back_to_calm(qapp, monkeypatch):
    monkeypatch.setattr(partrig.PartRig, "has_mood_face", lambda self, m: False)
    w = mkwin(qapp, part_rig=True); w._motion_timer.stop()
    w.set_mood_enabled(True, persist=False)
    w.mood_event("fall")
    assert w._pet.mood() == "calm"


def test_petting_drives_window_mood_and_chat_hooks(qapp):
    w = mkwin(qapp, part_rig=True); w._motion_timer.stop()
    w.set_mood_enabled(True, persist=False)
    w._set_pat(True)
    assert w._pet.mood() == "happy"
    w._set_pat(False)
    w._mood_on_say("pet_fall")
    assert w._pet.mood() == "surprised"


def test_menu_and_settings_rows(qapp):
    from test_settings_panel import Model, _menu_checked, _panel
    from desk_pet_grok.menu import build_pet_menu
    m = Model(); st = {"v": False}
    cb = m.cb(); cb.is_mood = lambda: st["v"]; cb.set_mood = lambda v: st.update(v=v)
    menu = build_pet_menu(None, cb)
    acts = [a for a in menu.actions() if "表情情绪" in a.text()]
    assert len(acts) == 1 and not acts[0].isChecked()
    acts[0].trigger()
    assert st["v"] is True
    from desk_pet_grok.settings_panel import SettingsPanel, build_sections
    p = SettingsPanel(build_sections(cb, ax_trusted=lambda: False, open_ax=lambda: None))
    p.checkbox_for("表情情绪").setChecked(False)
    assert st["v"] is False
