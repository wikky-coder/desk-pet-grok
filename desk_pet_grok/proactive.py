"""F5: unprompted talk, v2. Qt-free.

``Scheduler`` is the one gate every unprompted line goes through: at most ``max_per_hour`` lines in any rolling hour and
at least ``min_gap_s`` seconds between two of them; callers pass ``blocked`` (chat open / streaming / quiet / full
screen) and a blocked request is dropped, not queued. User-triggered lines (click, head-pat, fall) never use it.
``EventDetector`` turns local signals into event kinds (nothing here costs quota): switched front app, long continuous
use, back after being away. Hourly chimes and weather changes are produced by the existing slow tick / weather code."""

from __future__ import annotations

from dataclasses import dataclass, field

# event kind -> line category
EVENT_LINES = {
    "app_switch": "app_switch",
    "long_use": "long_use",
    "welcome_back": "welcome_back",
}


@dataclass
class Scheduler:
    enabled: bool = True  # False = no limiter (legacy behaviour: the old per-line cooldowns only)
    max_per_hour: int = 3
    min_gap_s: float = 300.0
    _stamps: list[float] = field(default_factory=list)

    def _prune(self, now: float) -> None:
        self._stamps = [t for t in self._stamps if now - t < 3600.0]

    def allow(self, now: float, *, blocked: bool = False) -> bool:
        if blocked:
            return False
        if not self.enabled:
            return True
        self._prune(now)
        if len(self._stamps) >= max(0, int(self.max_per_hour)):
            return False
        if self._stamps and now - self._stamps[-1] < self.min_gap_s:
            return False
        return True

    def acquire(self, now: float, *, blocked: bool = False) -> bool:
        """Check and, if allowed, record one unprompted line."""
        if not self.allow(now, blocked=blocked):
            return False
        if self.enabled:
            self._stamps.append(now)
        return True

    @property
    def count_last_hour(self) -> int:
        return len(self._stamps)


class EventDetector:
    """Feed it a sample every few seconds/minutes: cursor position (activity proxy) and the front app name (or None)."""

    def __init__(self, *, long_use_s: float = 45 * 60.0, away_s: float = 10 * 60.0, app_min_s: float = 20.0) -> None:
        self.long_use_s = long_use_s
        self.away_s = away_s
        self.app_min_s = app_min_s
        self._cursor: tuple[float, float] | None = None
        self._last_active: float | None = None
        self._use_start: float | None = None
        self._app: str | None = None
        self._app_since = 0.0
        self._reported_app: str | None = None

    def tick(self, now: float, cursor: tuple[float, float] | None, front_app: str | None) -> list[str]:
        out: list[str] = []
        moved = cursor is not None and self._cursor is not None and cursor != self._cursor
        if cursor is not None:
            self._cursor = cursor
        if self._last_active is None:
            self._last_active = now
            self._use_start = now
        if moved:
            if now - self._last_active >= self.away_s:
                out.append("welcome_back")
                self._use_start = now
            self._last_active = now
        elif now - self._last_active >= self.away_s:
            self._use_start = None  # away: the continuous-use run is over
        if self._use_start is None and moved:
            self._use_start = now
        if self._use_start is not None and now - self._use_start >= self.long_use_s and now - self._last_active < self.away_s:
            out.append("long_use")
            self._use_start = now
        if front_app:
            if front_app != self._app:
                self._app, self._app_since = front_app, now
            elif (
                front_app != self._reported_app
                and now - self._app_since >= self.app_min_s
                and self._reported_app is not None
            ):
                out.append("app_switch")
                self._reported_app = front_app
            elif self._reported_app is None and now - self._app_since >= self.app_min_s:
                self._reported_app = front_app  # first app seen: baseline, no remark
        return out
