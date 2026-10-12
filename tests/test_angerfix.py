"""angerfix: petting soothes her at every anger stage (real detector path), angry-voice lines only while angry, back to normal after."""
from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from test_petting_window import qapp  # noqa: E402,F401

from desk_pet_grok import lines, lines_v4, petting  # noqa: E402
from desk_pet_grok.meow import ends_with_meow  # noqa: E402


def _win(tmp_path, **s):
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    base = {"puppet25d": True, "part_rig": True, "shake_anger": True, "window_height": 160}  # small window like the user's
    base.update(s)
    w = PetWindow(state_machine=StateMachine(), settings=base)
    w.show()
    return w


@pytest.mark.parametrize("stage", [1, 2, 3, 4, 5])
def test_real_petting_soothes_every_stage(qapp, tmp_path, stage):
    w = _win(tmp_path)
    said = []
    w.lounge_say.connect(said.append)
    w._anger._set(stage)
    w._anger.events.clear()
    w._pet.set_anger(stage)
    zone = petting.head_zone(w.x(), w.y(), w.width(), w.height())
    cx0, cy = (zone[0] + zone[2]) / 2, (zone[1] + zone[3]) / 2
    t = 50.0
    seen = set()
    for i in range(60 * 8):
        t += 1 / 60
        w.feed_cursor(t, cx0 + 35 * math.sin(2 * math.pi * 2.5 * i / 60), cy)
        w._anger_tick(1 / 60)
        seen.add(w._anger.stage)
    assert w._anger.stage == 0 and w._pet.anger() == 0, (stage, seen)
    assert said[-1] == "shake_calm"
    if stage >= 4:
        assert "anger_soothe" in said  # sulk / fuming come down in steps with a line each
    w.close()


def test_pat_zone_is_forgiving_when_angry(qapp, tmp_path):
    """Stroking just outside the normal head zone still counts while she is angry."""
    w = _win(tmp_path)
    w._anger._set(4)
    zone = petting.head_zone(w.x(), w.y(), w.width(), w.height())
    cx0, cy = (zone[0] + zone[2]) / 2, zone[3] + 0.12 * (zone[3] - zone[1])  # a bit below the zone
    t, on_frames = 50.0, 0
    for i in range(120):
        t += 1 / 60
        on_frames += w.feed_cursor(t, cx0 + 30 * math.sin(2 * math.pi * 2.5 * i / 60), cy)
    assert on_frames > 40
    w.close()


def test_all_anger_pools_are_angry_voice():
    for c in ("anger_soothe", "anger_pat", "anger_poke", "anger_greet", "anger_work", "anger_idle", "shake_calm"):
        pool = lines_v4.POOLS[c]
        assert 10 <= len(pool) <= 12, c
    for c in lines_v4.ANGER_CATEGORIES:
        for s in lines_v4.POOLS[c]:
            assert ends_with_meow(s) and len(s) <= 24, (c, s)
    for c in ("shake_dizzy", "shake_annoyed", "shake_puffed", "shake_fuming", "shake_sulk"):
        assert len(lines_v4.POOLS[c]) >= 10


@pytest.mark.parametrize("cat,want", [("idle_chatter", "anger_idle"), ("click_reply", "anger_poke"), ("rapid_clicks", "anger_poke"),
                                      ("greet_morning", "anger_greet"), ("festival_cny", "anger_greet"), ("work_code", "anger_work"),
                                      ("pet_head", "anger_pat"), ("pat_spoil", "anger_pat"), ("top_of_hour", "anger_idle"),
                                      ("shake_fuming", "shake_fuming"), ("anger_soothe", "anger_soothe")])
def test_angry_equivalent(cat, want):
    assert lines_v4.angry_equivalent(cat) == want


def _chat(qapp, tmp_path):
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    from desk_pet_grok.app import build  # noqa: F401
    return None


def test_chat_lines_only_angry_while_angry_and_prompt(qapp, tmp_path, monkeypatch):
    from desk_pet_grok import chat as chatmod
    w = _win(tmp_path)
    bubble = chatmod.BubbleWidget() if hasattr(chatmod, "BubbleWidget") else None
    ctl = chatmod.ChatController.__new__(chatmod.ChatController)  # only the pieces under test
    shown = []
    ctl.anger_fn = lambda: w._anger.stage
    assert ctl._angry() is False
    assert chatmod.ANGER_PROMPT not in ctl._system_prompt_base() if hasattr(ctl, "_system_prompt_base") else True
    w._anger._set(3)
    assert ctl._angry() is True
    ctl._memory_on = False
    p = ctl._system_prompt()
    assert "在生气" in p and "赌气" in p and p.startswith(chatmod.SYSTEM_PROMPT[:20])
    w._anger.calm()
    assert ctl._angry() is False and ctl._system_prompt() == chatmod.SYSTEM_PROMPT
    w.close()


def test_show_line_replaces_categories_then_recovers(qapp, tmp_path):
    from PySide6.QtCore import QTimer
    from desk_pet_grok import chat as chatmod
    w = _win(tmp_path)
    ctl = chatmod.ChatController.__new__(chatmod.ChatController)
    class B:
        def show_text(self, t): shown.append(t)
        def reposition_above(self, w): pass
    class CD:
        def try_acquire(self, k): return True
        def mark(self, k): pass
    import random
    shown = []
    ctl.anger_fn = lambda: w._anger.stage
    ctl.hidden_fn = None
    ctl._window = type("W", (), {"bubble_visible": True, "play_jump": lambda s: None})()
    ctl._worker = None
    ctl._bubble, ctl._line_cooldown, ctl._line_rng = B(), CD(), random.Random(1)
    ctl._line_clear_timer = QTimer()
    w._anger._set(3)
    for cat in ("idle_chatter", "click_reply", "greet_morning", "work_code", "boot", "lounge_start"):
        shown.clear()
        assert ctl.show_line(cat, force=True)
        pool = set(lines_v4.POOLS[lines_v4.angry_equivalent(cat)])
        assert shown[0] in pool, (cat, shown)
    w._anger.calm()
    shown.clear()
    assert ctl.show_line("idle_chatter", force=True)
    assert shown[0] in set(lines.lines_for("idle_chatter"))  # ordinary talk is back
    w.close()
