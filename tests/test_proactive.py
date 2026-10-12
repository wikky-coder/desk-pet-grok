"""F5: proactive speech v2 - limiter, local events, 2 h timeline, and the controller gates."""

from __future__ import annotations

import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from desk_pet_grok import lines
from desk_pet_grok.lines import lines_for
from desk_pet_grok.meow import ends_with_meow
from desk_pet_grok.proactive import EventDetector, Scheduler


def test_scheduler_hourly_cap_and_gap():
    s = Scheduler(enabled=True, max_per_hour=3, min_gap_s=300)
    assert s.acquire(0)
    assert not s.acquire(100)  # < 5 min after the last one
    assert s.acquire(301)
    assert s.acquire(700)
    assert not s.acquire(1100)  # 4th within the hour
    assert s.acquire(3601 + 1)  # the first one has left the window


def test_scheduler_blocked_does_not_consume():
    s = Scheduler(enabled=True)
    assert not s.acquire(0, blocked=True)
    assert s.count_last_hour == 0 and s.acquire(1)


def test_scheduler_disabled_is_legacy_passthrough():
    s = Scheduler(enabled=False)
    assert all(s.acquire(float(i)) for i in range(20))


def test_events_app_switch_needs_stable_front_app():
    d = EventDetector(app_min_s=20)
    assert d.tick(0, (0, 0), "Safari") == []
    assert d.tick(30, (1, 0), "Safari") == []  # baseline
    assert d.tick(40, (2, 0), "Xcode") == []  # just switched, not yet stable
    assert d.tick(65, (3, 0), "Xcode") == ["app_switch"]
    assert d.tick(95, (4, 0), "Xcode") == []  # reported once


def test_events_long_use_and_welcome_back():
    d = EventDetector(long_use_s=600, away_s=300)
    out = []
    for i in range(0, 1300, 30):
        out += d.tick(float(i), (i, 0), None)  # cursor keeps moving
    assert out.count("long_use") == 2
    # away for 10 minutes, then moves again
    assert d.tick(1900.0, (1300, 0), None) in (["welcome_back"], ["welcome_back", "long_use"])
    assert d.tick(1930.0, (1301, 0), None) == []


def test_two_hour_timeline_respects_limits():
    rng = random.Random(7)
    sched = Scheduler(enabled=True, max_per_hour=3, min_gap_s=300)
    ev = EventDetector(long_use_s=45 * 60, away_s=600, app_min_s=20)
    apps = ["Safari", "Xcode", "Slack", "Notes"]
    said: list[float] = []
    app, x = apps[0], 0
    for step in range(0, 2 * 3600, 30):  # slow tick every 30 s
        t = float(step)
        if rng.random() < 0.05:
            app = rng.choice(apps)
        x += 1
        kinds = ev.tick(t, (x, 0), app)
        # the old chatter sources also ask: idle chatter every ~60 s, hourly chime
        asks = list(kinds) + (["idle_chatter"] if step % 60 == 0 else []) + (["hour"] if step % 3600 == 0 else [])
        for _ in asks:
            if sched.acquire(t):
                said.append(t)
    assert 1 <= len(said) <= 6
    assert all(b - a >= 300 for a, b in zip(said, said[1:]))


@pytest.mark.parametrize("cat", ["pat_spoil", "app_switch", "long_use", "welcome_back"])
def test_new_lines_style(cat):
    assert cat in lines.CATEGORIES
    pool = lines_for(cat)
    assert len(pool) >= 10
    for s in pool:
        assert ends_with_meow(s) and len(s) <= 24, s


# ---- controller gates (real window + controller, offscreen) ----
@pytest.fixture
def ctl(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    QApplication.instance() or QApplication([])
    from desk_pet_grok.bubble import BubbleWidget
    from desk_pet_grok.chat import ChatController
    from desk_pet_grok.chat_panel import ChatPanel
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow

    def make(**settings):
        sm = StateMachine()
        w = PetWindow(state_machine=sm, settings={"puppet25d": True, **settings})
        c = ChatController(w, state_machine=sm, bubble=BubbleWidget(), panel=ChatPanel())
        c._idle_chatter_timer.stop()
        c._slow_timer.stop()
        shown = []
        orig = c._bubble.show_text
        c._bubble.show_text = lambda t, *a, **k: (shown.append(t), orig(t, *a, **k))[1]
        return w, c, shown

    return make


def test_talk_off_blocks_every_unprompted_line_but_not_user_lines(ctl):
    w, c, shown = ctl(proactive_talk=False)
    c._on_idle_chatter_tick()
    c._say_boot()
    c.on_lounge_say("yawn")
    c._on_slow_tick()
    assert shown == []
    c.on_lounge_say("pet_head")
    c.on_pet_clicked()
    assert len(shown) == 2


def test_blocked_while_chat_open_quiet_or_streaming(ctl):
    w, c, shown = ctl(proactive_v2=True)
    c._panel.isVisible = lambda: True
    for _ in range(5):
        c._on_idle_chatter_tick()
    assert shown == []
    c._panel.isVisible = lambda: False
    c._sm.enter_quiet()
    c._on_idle_chatter_tick()
    assert shown == []
    c._sm.leave_quiet()
    c._streaming = lambda: True
    c._on_idle_chatter_tick()
    assert shown == []


def test_v2_limits_idle_chatter(ctl):
    w, c, shown = ctl(proactive_v2=True)
    for _ in range(6):
        c._line_cooldown._last.clear()  # isolate the scheduler from the legacy per-line cooldown
        c._on_idle_chatter_tick()
    assert len(shown) == 1  # 5-minute gap stops the rest


def test_legacy_default_unchanged(ctl):
    w, c, shown = ctl()
    assert c.proactive_talk and not c.proactive_v2
    for _ in range(3):
        c._line_cooldown._last.clear()
        c._on_idle_chatter_tick()
    assert len(shown) == 3


def test_events_only_when_v2(ctl):
    w, c, shown = ctl()
    c.cursor_fn = iter([(i, 0) for i in range(100)]).__next__
    c._events = EventDetector(long_use_s=1, away_s=1000)
    c._poll_events(0.0)
    c._poll_events(5.0)
    assert shown == []  # v2 off: no event lines
    c.set_proactive_v2(True, persist=False)
    c._poll_events(10.0)
    c._poll_events(20.0)
    assert any(t in lines_for("long_use") for t in shown)


def test_pats_turn_spoiled_after_three(ctl):
    w, c, shown = ctl()
    for i in range(3):
        c._extra_last.clear()
        c.on_lounge_say("pet_head")
    assert shown[-1] in lines_for("pat_spoil")
    assert shown[0] in lines_for("pet_head")
