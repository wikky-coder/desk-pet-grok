"""F6: mood layer on top of the pose state machine (Qt-free).

Moods: calm (default), happy, sleepy, annoyed, surprised, pouty (wronged / clingy).  Events push a mood's level up;
every level decays over time (exponential half-life).  The shown mood is the one with the largest weighted level above
a threshold, else calm.  Time of day only adds a slow "sleepy" drift at night when nothing else is going on.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

MOODS = ("calm", "happy", "sleepy", "annoyed", "surprised", "pouty")
FACE_MOODS = ("happy", "sleepy", "annoyed", "surprised", "pouty")  # moods that have a face layer (calm = the base head)

# half-life seconds, priority weight when two moods are alive at once
HALF_LIFE = {"happy": 40.0, "sleepy": 120.0, "annoyed": 12.0, "surprised": 1.6, "pouty": 90.0}
WEIGHT = {"surprised": 1.6, "annoyed": 1.25, "happy": 1.0, "pouty": 0.9, "sleepy": 0.6}
SHOW_MIN = 0.28  # a level below this shows calm
PAT_GAIN = 0.55  # one pat session
PAT_HAPPY_CAP = 1.0
POKE_GAIN = 0.5  # one rapid-click burst
FALL_GAIN = 1.0
NEGLECT_GAIN = 0.8
NIGHT_HOURS = (23, 5)  # [23:00, 05:00)
NIGHT_LEVEL = 0.45
NIGHT_IDLE_S = 120.0  # needs this long without interaction before the night drift shows
FADE_S = 0.45  # face cross-fade (acceptance: 0.3 - 0.6 s)


def is_night(hour: int) -> bool:
    a, b = NIGHT_HOURS
    return hour >= a or hour < b


@dataclass
class MoodMachine:
    enabled: bool = True

    def __post_init__(self) -> None:
        self.level: dict[str, float] = {m: 0.0 for m in FACE_MOODS}
        self.idle_s = 0.0
        self.hour = 12
        self.pats = 0

    # ---- events ----
    def event(self, kind: str) -> None:
        if not self.enabled:
            return
        if kind == "pat":
            self.idle_s = 0.0
            self.pats += 1
            self._bump("happy", PAT_GAIN, PAT_HAPPY_CAP)
            self.level["annoyed"] *= 0.4  # being petted soothes
            self.level["pouty"] *= 0.3
        elif kind == "fall":
            self.idle_s = 0.0
            self._bump("surprised", FALL_GAIN)
        elif kind == "poke":  # rapid clicking
            self.idle_s = 0.0
            self._bump("annoyed", POKE_GAIN)
            self.level["happy"] *= 0.6
        elif kind == "neglect":  # left alone for long
            self._bump("pouty", NEGLECT_GAIN)
        elif kind == "activity":
            self.idle_s = 0.0
            self.level["pouty"] *= 0.5

    def _bump(self, mood: str, amount: float, cap: float = 1.0) -> None:
        self.level[mood] = min(cap, self.level[mood] + amount)

    # ---- time ----
    def tick(self, dt: float, hour: int | None = None) -> None:
        if hour is not None:
            self.hour = hour
        self.idle_s += dt
        for m, hl in HALF_LIFE.items():
            self.level[m] *= 0.5 ** (dt / hl)
        if self.enabled and is_night(self.hour) and self.idle_s >= NIGHT_IDLE_S:
            self.level["sleepy"] = max(self.level["sleepy"], NIGHT_LEVEL)

    def current(self) -> str:
        if not self.enabled:
            return "calm"
        best, bv = "calm", 0.0
        for m, v in self.level.items():
            s = v * WEIGHT[m]
            if v >= SHOW_MIN and s > bv:  # SHOW_MIN gates on the raw level, the weight only orders
                best, bv = m, s
        return best

    def reset(self) -> None:
        for m in self.level:
            self.level[m] = 0.0
        self.idle_s = 0.0


def fade_step(a: float, dt: float, fade_s: float = FADE_S) -> float:
    """Progress 0..1 of a cross-fade after dt seconds."""
    return min(1.0, a + dt / fade_s)


def smooth(a: float) -> float:
    a = min(1.0, max(0.0, a))
    return a * a * (3 - 2 * a)
