"""Tests for random lines."""

from __future__ import annotations

import random

import pytest

from desk_pet_grok.meow import ends_with_meow
from desk_pet_grok.lines import (
    CATEGORIES,
    BUBBLE_MAX_CHARS,
    LONG_IDLE_LEVELS,
    LineCooldown,
    is_rapid_click,
    long_idle_level,
    lines_for,
    pick_line,
)


@pytest.mark.parametrize("category", CATEGORIES)
def test_pick_line_non_empty(category: str) -> None:
    line = pick_line(category, rng=random.Random(0))
    assert isinstance(line, str)
    assert line.strip()


@pytest.mark.parametrize("category", CATEGORIES)
def test_lines_for_has_entries(category: str) -> None:
    pool = lines_for(category)
    assert len(pool) >= 10
    assert all(isinstance(s, str) and s.strip() for s in pool)


def test_pick_line_unknown_category() -> None:
    with pytest.raises(KeyError):
        pick_line("nope")


def test_cooldown_gate() -> None:
    cd = LineCooldown(seconds=10.0)
    assert cd.try_acquire("x", now=100.0)
    assert not cd.try_acquire("x", now=105.0)
    assert cd.try_acquire("x", now=111.0)


def test_all_new_categories_present():
    for c in ("boot", "long_idle_1", "long_idle_2", "long_idle_3", "top_of_hour", "weather_change",
              "rapid_clicks", "screen_edge", "task_done", "error", "idle_chatter", "click_reply", "after_drag"):
        assert c in CATEGORIES


@pytest.mark.parametrize("category", CATEGORIES)
def test_length_limit_voice_and_no_dupes(category: str) -> None:
    pool = lines_for(category)
    assert len(set(pool)) == len(pool)
    for s in pool:
        shown = s.replace("{hour}", "12").replace("{cond}", "多云")
        assert 0 < len(shown) <= 24, shown
        assert len(shown) <= BUBBLE_MAX_CHARS
        assert "小Grok" not in shown and "桌宠" not in shown


def test_voice_self_reference_and_address() -> None:
    allv = [s for c in CATEGORIES for s in lines_for(c)]
    assert sum("本喵" in s for s in allv) >= 40
    wiki = sum("Wiki" in s for s in allv)
    assert 3 <= wiki and wiki * 4 <= sum("本喵" in s for s in allv)  # self = 本喵 mostly, Wiki only now and then
    assert sum("主人" in s for s in allv) >= 15  # user = 主人
    assert not any(("Wiki，" in s) or "Wiki 早" in s or "欢迎回来，Wiki" in s for s in allv)  # Wiki never addresses the user
    assert all("我是桌宠" not in s for s in allv)
    kao = [s for s in allv if any(k in s for k in "(（٩ᵕ>ω<")]
    assert len(kao) <= len(allv) // 10  # kaomoji sparingly


def test_templates_only_when_filled() -> None:
    rng = random.Random(1)
    for _ in range(50):
        assert "{" not in pick_line("top_of_hour", rng=rng)  # no values -> plain lines only
        assert "{" not in pick_line("top_of_hour", rng=rng, hour=9)
        assert "{" not in pick_line("weather_change", rng=rng, cond="下雨")
    seen = {pick_line("top_of_hour", rng=random.Random(i), hour=9) for i in range(60)}
    assert any("9" in s for s in seen)


def test_long_idle_levels_escalate() -> None:
    assert long_idle_level(10) == 0
    assert [long_idle_level(x) for x in (301, 901, 2401)] == [1, 2, 3]
    assert len(LONG_IDLE_LEVELS) == 3 and all(lines_for(c) for c in LONG_IDLE_LEVELS)


def test_rapid_click_detection() -> None:
    assert not is_rapid_click([0.0, 1.0, 2.0], 2.0)
    assert is_rapid_click([0.0, 0.5, 1.0, 1.5], 1.5)
    assert not is_rapid_click([0.0, 0.5, 1.0, 5.0], 5.0)


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_line_ends_with_meow(category: str) -> None:
    for s in lines_for(category):
        assert ends_with_meow(s), s


def test_lounge_categories_exist() -> None:
    for c in ("lounge_start", "lounge", "yawn", "lounge_sleep", "lounge_end", "self_walk"):
        assert c in CATEGORIES and len(lines_for(c)) >= 10


def test_pet_categories_style() -> None:
    for c in ("pet_head", "pet_fall"):
        pool = lines_for(c)
        assert 10 <= len(pool) <= 12
        for s in pool:
            assert ends_with_meow(s) and len(s) <= 24, s
    assert all("主人" in s or "本喵" in s or "Wiki" in s or s for s in lines_for("pet_head"))
    assert any("主人" in s for s in lines_for("pet_head"))
    assert any("本喵" in s for s in lines_for("pet_head"))
