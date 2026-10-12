"""v4-4: time-of-day greetings (Qt-free). Six periods; the first time she sees the user in a period on a given day she greets once
(a small action + effect + line). "Seen" = app start or the user moving the mouse / clicking after being away. Remembered per day."""
from __future__ import annotations

import datetime as _dt
from typing import Optional

PERIODS = (("dawn", 0, 5), ("morning", 5, 11), ("noon", 11, 14), ("afternoon", 14, 18), ("evening", 18, 22), ("night", 22, 24))
LABEL = {"dawn": "凌晨", "morning": "早上", "noon": "中午", "afternoon": "下午", "evening": "晚上", "night": "深夜"}
# what she does: face (None = keep), hop, effect icon
ACTION = {
    "dawn": ("sleepy", False, "zzz"),
    "morning": ("happy", True, "sun"),
    "noon": ("happy", False, "bowl"),
    "afternoon": (None, True, "cup"),
    "evening": ("happy", False, "moon"),
    "night": ("sleepy", False, "moon_zzz"),
}


def period_of(hour: int) -> str:
    for name, a, b in PERIODS:
        if a <= hour < b:
            return name
    return "night"


class Greeter:
    def __init__(self, seen: Optional[dict] = None) -> None:
        self.seen: dict[str, str] = dict(seen or {})

    def due(self, now: _dt.datetime) -> Optional[str]:
        p = period_of(now.hour)
        return None if self.seen.get(p) == now.date().isoformat() else p

    def mark(self, period: str, now: _dt.datetime) -> None:
        self.seen[period] = now.date().isoformat()
        for k in [k for k, v in self.seen.items() if v != now.date().isoformat()]:
            del self.seen[k]  # only today's periods are kept
