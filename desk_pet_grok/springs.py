"""Damped springs for secondary motion (design bible §3.14). Pure Python, no Qt.

Semi-implicit Euler at a fixed 240 Hz sub-step:
    a = -w^2 x - 2 z w v - gain * a_body ;  v += a dt ; x += v dt ; |x| <= limit
"""

from __future__ import annotations

import math
from dataclasses import dataclass

SUBSTEP = 1.0 / 240.0
ACCEL_LIMIT = 3000.0  # body acceleration clamp (canvas px/s^2)


@dataclass
class Spring:
    f: float  # Hz
    zeta: float
    limit: float  # max |x|
    gain: float = 1.0
    x: float = 0.0
    v: float = 0.0

    def step(self, dt: float, a_body: float = 0.0) -> float:
        a_body = max(-ACCEL_LIMIT, min(ACCEL_LIMIT, a_body))
        w = 2.0 * math.pi * self.f
        n = max(1, int(math.ceil(dt / SUBSTEP)))
        h = dt / n
        for _ in range(n):
            a = -w * w * self.x - 2.0 * self.zeta * w * self.v - self.gain * a_body
            self.v += a * h
            self.x += self.v * h
            if self.x > self.limit:
                self.x, self.v = self.limit, min(self.v, 0.0)
            elif self.x < -self.limit:
                self.x, self.v = -self.limit, max(self.v, 0.0)
        return self.x

    def at_rest(self, eps: float = 0.01) -> bool:
        return abs(self.x) < eps and abs(self.v) < eps * 10


class Chain:
    """Springs hanging off each other: each link's target is its parent link's deflection
    so motion travels (and lags) toward the tip. Parameters interpolate root -> tip."""

    def __init__(self, n: int, root: tuple[float, float, float, float],
                 tip: tuple[float, float, float, float]) -> None:
        # tuples are (f, zeta, limit, gain)
        self.links = []
        for i in range(n):
            u = i / max(1, n - 1)
            p = [root[k] + (tip[k] - root[k]) * u for k in range(4)]
            self.links.append(Spring(*p))

    def step(self, dt: float, a_body: float, drive: float = 0.0) -> list[float]:
        out = []
        prev = drive
        for s in self.links:
            s.step(dt, a_body + (s.f * 2 * math.pi) ** 2 * (-prev) * 0.0)
            # parent coupling: add the parent's deflection as an extra restoring target
            s.v += (prev - s.x) * (2 * math.pi * s.f) ** 2 * 0.25 * dt
            prev = s.x
            out.append(s.x)
        return out


# bible §3.14 table: (f Hz, zeta, max amplitude, gain)
SKIRT = (2.6, 0.50, 4.5, 0.9)  # canvas px
HAIR = (2.4, 0.40, 7.0, 1.0)  # degrees
AHOGE = (4.5, 0.18, 20.0, 1.4)  # degrees
TAIL_ROOT = (1.6, 0.45, 15.0, 0.8)
TAIL_TIP = (1.1, 0.30, 22.0, 1.2)
LEAN = (1.6, 0.35, 30.0, 1.0)  # drag tilt, degrees (limit = displacement from target)
