"""v4-6: work along — classify the front app name, stable / cooldown logic, props on the pet, window wiring."""
from __future__ import annotations

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from desk_pet_grok import config, workalong  # noqa: E402
from desk_pet_grok.workalong import FrontPoller, WorkAlong, classify  # noqa: E402


@pytest.mark.parametrize("name,mode", [
    ("Safari", "read"), ("Google Chrome", "read"), ("预览", "read"), ("Preview", "read"), ("Books", "read"), ("Microsoft Word", "read"),
    ("Notion", "read"), ("Obsidian", "read"), ("微信读书", "read"), ("Arc", "read"),
    ("Visual Studio Code", "code"), ("Code", "code"), ("Cursor", "code"), ("Xcode", "code"), ("PyCharm CE", "code"), ("Sublime Text", "code"),
    ("Terminal", "terminal"), ("iTerm2", "terminal"), ("Warp", "terminal"), ("Ghostty", "terminal"), ("终端", "terminal"),
    ("Adobe Photoshop 2026", "draw"), ("Figma", "draw"), ("Sketch", "draw"), ("Procreate", "draw"), ("Krita", "draw"), ("Clip Studio Paint", "draw"),
    ("Finder", None), ("访达", None), ("WeChat", None), ("Slack", None), ("Spotify", None), ("Barcode Scanner", None),
    ("桌宠Grok", None), ("python3", None), ("System Settings", None), ("", None), (None, None),
])
def test_classify(name, mode):
    assert classify(name) == mode


def test_default_off():
    assert config._DEFAULTS["work_along"] is False
    assert WorkAlong().enabled is False


def run(m, secs, app, blocked=False, t0=0.0, dt=0.5):
    t, ev = t0, []
    for _ in range(int(secs / dt)):
        t += dt
        e = m.feed(t, dt, app, blocked)
        if e:
            ev.append((round(t, 1), e))
    return t, ev


def test_enter_needs_stable_time_and_switch_obeys_cooldown():
    m = WorkAlong(enabled=True)
    t, ev = run(m, 2.0, "Safari")
    assert m.mode is None  # < 3 s: a glance
    t, ev = run(m, 2.0, "Safari", t0=t)
    assert m.mode == "read" and ev[0][1] == ("enter", "read")
    t, ev = run(m, 10.0, "Terminal", t0=t)  # in front for 10 s but the cooldown (25 s) has not passed
    assert m.mode == "read" and ev == []
    t, ev = run(m, 20.0, "Terminal", t0=t)
    assert m.mode == "terminal" and ev[0][1] == ("switch", "terminal")


def test_flicking_between_apps_never_shows_a_prop():
    m = WorkAlong(enabled=True)
    t = 0.0
    for i in range(80):
        t, ev = run(m, 1.0, "Safari" if i % 2 else "Terminal", t0=t)
        assert ev == []
    assert m.mode is None


def test_exit_after_leaving_and_instant_when_blocked():
    m = WorkAlong(enabled=True)
    t, _ = run(m, 5.0, "Xcode")
    assert m.mode == "code"
    t, ev = run(m, 3.0, "Finder", t0=t)
    assert m.mode == "code"  # short Finder visit keeps the prop
    t, ev = run(m, 4.0, "Finder", t0=t)
    assert m.mode is None and ev[-1][1] == ("exit", "code")
    t, _ = run(m, 5.0, "Xcode", t0=t + 30)
    assert m.mode == "code"
    e = m.feed(t + 1, 0.5, "Xcode", blocked=True)  # lying down / clinging / angry / hidden
    assert e == ("exit", "code") and m.mode is None
    t2, _ = run(m, 4.0, "Xcode", blocked=True, t0=t + 1)
    assert m.mode is None


def test_disabled_never_shows_and_clears():
    m = WorkAlong(enabled=False)
    run(m, 10.0, "Xcode"); assert m.mode is None
    m.enabled = True; run(m, 5.0, "Xcode"); assert m.mode == "code"
    m.enabled = False
    assert m.feed(100.0, 0.5, "Xcode") == ("exit", "code")


def test_poller_reads_off_thread_and_stops():
    seq = iter(["Safari", "Xcode", "Xcode", "Xcode", "Xcode", "Xcode"])
    p = FrontPoller(lambda: next(seq, "Xcode"), interval=0.01)
    p.start()
    time.sleep(0.15)
    assert p.name == "Xcode"
    p.stop(); assert p.name is None


def test_poller_survives_errors():
    def boom():
        raise RuntimeError("x")
    p = FrontPoller(boom, interval=0.01); p.start(); time.sleep(0.05); assert p.name is None; p.stop()


def test_assets_exist():
    root = os.path.join(os.path.dirname(__file__), "..", "assets", "work25d")
    for n in ("book", "laptop", "palette"):
        assert os.path.isfile(os.path.join(root, n + ".png"))
    assert os.path.isfile(os.path.join(root, "work.json"))


def _win(qapp, tmp_path, **s):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    base = {"puppet25d": True, "part_rig": True, "window_height": 300}
    base.update(s)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.show()
    return w


def test_window_follows_front_app_and_hides_props_when_blocked(qapp, tmp_path):
    w = _win(qapp, tmp_path, work_along=True)
    said = []
    w.lounge_say.connect(said.append)
    w._work_poller = type("P", (), {"name": "Visual Studio Code", "start": lambda s: None, "stop": lambda s: None})()
    for _ in range(60 * 5):
        w._work_tick(1 / 60, False)
    assert w._work.mode == "code" and w._pet.work_mode() == "code" and said == ["work_code"]
    for _ in range(90):
        w._pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert w._pet._work_t > 0.99
    w._work_tick(1 / 60, True)  # being dragged
    assert w._pet.work_mode() is None
    for _ in range(120):
        w._pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert w._pet._work_t < 0.01 and w._pet._work_shown is None
    # lying down: never triggers
    w._pet.lounging = lambda: True
    for _ in range(60 * 6):
        w._work_tick(1 / 60, False)
    assert w._work.mode is None
    w.close()


def test_switch_off_removes_prop(qapp, tmp_path):
    w = _win(qapp, tmp_path, work_along=True)
    w._work_poller = type("P", (), {"name": "Terminal", "start": lambda s: None, "stop": lambda s: None})()
    for _ in range(60 * 5):
        w._work_tick(1 / 60, False)
    assert w._pet.work_mode() == "terminal"
    w.set_work_along(False, persist=False)
    assert w._pet.work_mode() is None and not w.work_along
    w.close()


def test_lines():
    from desk_pet_grok import lines_v4
    from desk_pet_grok.meow import ends_with_meow
    for c in ("work_read", "work_code", "work_terminal", "work_draw"):
        assert len(lines_v4.POOLS[c]) >= 3 and all(ends_with_meow(s) and len(s) <= 24 for s in lines_v4.POOLS[c])
