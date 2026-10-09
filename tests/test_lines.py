"""Tests for random lines."""

from __future__ import annotations

import random

import pytest

from desk_pet_grok.lines import (
    CATEGORIES,
    LineCooldown,
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
    assert len(pool) >= 3
    assert all(isinstance(s, str) and s.strip() for s in pool)


def test_pick_line_unknown_category() -> None:
    with pytest.raises(KeyError):
        pick_line("nope")


def test_cooldown_gate() -> None:
    cd = LineCooldown(seconds=10.0)
    assert cd.try_acquire("x", now=100.0)
    assert not cd.try_acquire("x", now=105.0)
    assert cd.try_acquire("x", now=111.0)
