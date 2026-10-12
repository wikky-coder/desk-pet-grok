"""v4-5: power saving (Qt-free). Normal rate = the 33 ms motion tick (~30 fps). With the switch on, once nothing has happened for
IDLE_S (cursor still, no buttons, no drag / pat, she is not walking, no chat open) the tick slows to LOW_MS (~12 fps); after
DEEP_IDLE_S more it slows to DEEP_MS (~6 fps) while she just breathes. Any activity restores the normal rate on the very next tick."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

NORMAL_MS = 33
LOW_MS = 83
DEEP_MS = 160
IDLE_S = 30.0
DEEP_IDLE_S = 60.0  # idle total (not additional)


@dataclass
class PowerSaver:
    enabled: bool = False
    idle: float = 0.0
    interval: int = NORMAL_MS

    def feed(self, dt: float, active: bool) -> Optional[int]:
        """dt = real seconds since the last tick. Returns the new timer interval (ms) when it changes, else None."""
        if active or not self.enabled:
            self.idle = 0.0
        else:
            self.idle += dt
        want = NORMAL_MS
        if self.enabled:
            if self.idle >= DEEP_IDLE_S:
                want = DEEP_MS
            elif self.idle >= IDLE_S:
                want = LOW_MS
        if want != self.interval:
            self.interval = want
            return want
        return None
