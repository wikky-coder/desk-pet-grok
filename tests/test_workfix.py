"""work-along fixes: shake stage-0 KeyError, classic (non-rig) rendering, front-app reading chain, status line."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from desk_pet_grok import shake, workalong  # noqa: E402


def test_shake_stage0_event_has_no_line_and_is_handled(qapp, tmp_path):
    m = shake.AngerMachine(enabled=True)
    t = 0.0
    for i in range(12):
        t += 0.05
        m.drag_sample(t, 200 if i % 2 else 0)
    m.release()
    for _ in range(300):
        t += 0.1
        m.tick(t, 0.1)
    ev = m.drain()
    assert ("stage", 0, 1) in ev and 0 not in shake.LINE  # the event that used to raise KeyError: 0
    # window level: feed the same events through _anger_tick
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    w = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, "window_height": 300, "shake_anger": True})
    w.show()
    said = []
    w.lounge_say.connect(said.append)
    w._anger.events.extend([("stage", 1, 0), ("stage", 0, 1), ("calm", 1)])
    w._anger_tick(0.016)  # must not raise
    assert said[0] == "shake_dizzy" and said[-1] == "shake_calm" and len(said) == 2
    w.close()


def _win(qapp, tmp_path, **s):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    base = {"puppet25d": True, "window_height": 300}  # NOTE: no part_rig -> classic rendering
    base.update(s)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.show()
    return w


FRONT = [("Safari", "read", "read"), ("Code", "code", "code"), ("Terminal", "terminal", "terminal"), ("Procreate", "draw", "draw"),
         ("Visual Studio Code", "code", "code"), ("iTerm2", "terminal", "terminal"), ("Preview", "read", "read"), ("Microsoft Word", "read", "read"),
         ("Notes", "read", "read"), ("备忘录", "read", "read"), ("Pages", "read", "read"), ("Typora", "read", "read"), ("Obsidian", "read", "read"),
         ("Google Chrome", "read", "read"), ("Cursor", "code", "code"), ("Xcode", "code", "code"), ("PyCharm", "code", "code"),
         ("Sublime Text", "code", "code"), ("Warp", "terminal", "terminal"), ("Adobe Photoshop 2026", "draw", "draw"), ("Figma", "draw", "draw"),
         ("Sketch", "draw", "draw"), ("微信读书", "read", "read"), ("Finder", None, None), ("Grok Bot", None, None)]


@pytest.mark.parametrize("name,mode,_", FRONT)
def test_classic_rendering_enters_each_pose(qapp, tmp_path, name, mode, _):
    w = _win(qapp, tmp_path, work_along=True)
    assert not w.part_rig  # classic
    w._work_poller = type("P", (), {"name": name, "start": lambda s: None, "stop": lambda s: None, "_thread": None})()
    for _i in range(60 * 5):
        w._work_tick(1 / 60, False)
        w._pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
    assert w._work.mode == mode
    if mode:
        pet = w._pet
        pet.grab()
        for _i in range(60):
            pet.drive(1 / 60, want_walk=False, facing=1, look=False, dragging=False)
        assert pet._rig is not None and pet._rig.work_body is not None and pet._rig.work_body[0] == mode
        assert pet._rig_drawing()  # the rig's idle pose (with the two-handed body) is what is shown, not the classic frame
    w.close()


def test_status_line(qapp, tmp_path):
    w = _win(qapp, tmp_path, work_along=True)
    assert "还没开始" in w.work_status()
    alive = type("T", (), {"is_alive": lambda s: True})()
    w._work_poller = type("P", (), {"name": "Safari", "start": lambda s: None, "stop": lambda s: None, "_thread": alive})()
    assert "Safari" in w.work_status() and "翻书" in w.work_status() and "稳定" in w.work_status()
    for _i in range(60 * 5):
        w._work_tick(1 / 60, False)
    assert "已出现" in w.work_status()
    w._pet.lounging = lambda: True
    assert "趴着" in w.work_status()
    w._work_poller.name = None
    assert "没读到" in w.work_status()
    w.set_work_along(False, persist=False)
    assert w.work_status() == ""
    w.close()


def test_front_name_chain(monkeypatch):
    from desk_pet_grok import screen_mac
    monkeypatch.setattr(screen_mac, "IS_MAC", True)
    monkeypatch.setattr(screen_mac, "_nsworkspace_name", lambda: "Safari")
    assert screen_mac.front_app_name() == "Safari"
    monkeypatch.setattr(screen_mac, "_nsworkspace_name", lambda: None)
    monkeypatch.setattr(screen_mac.subprocess, "run", lambda *a, **k: type("R", (), {"stdout": ""})())
    assert screen_mac.front_app_name() is None
    def boom():
        raise OSError("x")
    monkeypatch.setattr(screen_mac, "_nsworkspace_name", boom)
    assert screen_mac.front_app_name() is None  # never raises


def test_switching_apps_with_cooldown():
    m = workalong.WorkAlong(enabled=True)
    t, got = 0.0, []
    for app, secs in (("Safari", 6), ("Terminal", 10), ("Terminal", 30), ("Procreate", 40)):
        for _ in range(int(secs / 0.5)):
            t += 0.5
            e = m.feed(t, 0.5, app)
            if e:
                got.append((round(t), e))
    assert [e[1] for _, e in got] == [("read" if False else "read"), "terminal", "draw"] or [x[1][1] for x in got] == ["read", "terminal", "draw"]
