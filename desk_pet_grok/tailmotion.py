"""Natural tail motion (Qt-free): slow incommensurate sines + irregular quick wags + a spring that lags the target.

angle() is the tail's deflection in degrees (+ = one way, - = the other) at the root pivot.
Modes (all eased, never switched hard): calm / happy (more and bigger quick wags) / pat (continuous fast wag) / asleep (very slow, very small)."""

from __future__ import annotations

import math
import random

SLOW = ((0.31, 6.0), (0.13, 4.5))  # (Hz, deg) summed slow sways: never an exact loop
WAG_HZ = (2.0, 2.8)
WAG_DEG = (9.0, 14.0)
WAG_LEN_S = (1.0, 1.9)
WAG_GAP_S = (5.0, 13.0)
HAPPY_GAP_S = (1.6, 4.5)
PAT_HZ, PAT_DEG = 3.2, 17.0
ASLEEP_HZ, ASLEEP_DEG = 0.11, 2.5
SPRING_F, SPRING_ZETA = 3.2, 0.55  # the tail follows its target with a little lag and overshoot
LIMIT = 19.0


class TailDriver:
    def __init__(self, rng: random.Random | None = None, gain: float = 1.0) -> None:
        self.rng = rng or random.Random()
        self.gain = gain
        self.t = 0.0
        self.x = 0.0
        self.v = 0.0
        self.phase = [self.rng.uniform(0, 2 * math.pi) for _ in SLOW]
        self.wag_t = -1.0  # >= 0 while a quick wag is running
        self.wag_len = 1.0
        self.wag_hz = 2.4
        self.wag_deg = 10.0
        self.next_wag = self.rng.uniform(*WAG_GAP_S) * 0.4
        self._pat = 0.0
        self._asleep = 0.0

    def target(self, dt: float, pat: float = 0.0, happy: float = 0.0, asleep: float = 0.0) -> float:
        k = min(1.0, dt / 0.25)
        self._pat += (max(0.0, min(1.0, pat)) - self._pat) * k
        self._asleep += (max(0.0, min(1.0, asleep)) - self._asleep) * min(1.0, dt / 0.8)
        calm = (1.0 - self._asleep) * (1.0 - self._pat)
        out = sum(a * math.sin(2 * math.pi * f * self.t + p) for (f, a), p in zip(SLOW, self.phase)) * calm
        # irregular quick wags
        if self.wag_t >= 0.0:
            self.wag_t += dt
            u = self.wag_t / self.wag_len
            if u >= 1.0:
                self.wag_t = -1.0
                gap = HAPPY_GAP_S if happy > 0.5 else WAG_GAP_S
                self.next_wag = self.t + self.rng.uniform(*gap)
            else:
                env = math.sin(math.pi * u) ** 2
                out += calm * env * self.wag_deg * math.sin(2 * math.pi * self.wag_hz * self.wag_t)
        elif self.t >= self.next_wag and self._asleep < 0.3 and self._pat < 0.2:
            self.wag_t = 0.0
            self.wag_len = self.rng.uniform(*WAG_LEN_S)
            self.wag_hz = self.rng.uniform(*WAG_HZ) * (1.2 if happy > 0.5 else 1.0)
            self.wag_deg = self.rng.uniform(*WAG_DEG) * (1.25 if happy > 0.5 else 1.0)
        out += self._pat * PAT_DEG * math.sin(2 * math.pi * PAT_HZ * self.t)
        out += self._asleep * ASLEEP_DEG * math.sin(2 * math.pi * ASLEEP_HZ * self.t)
        return out * self.gain

    def step(self, dt: float, pat: float = 0.0, happy: float = 0.0, asleep: float = 0.0) -> float:
        dt = max(1e-3, min(dt, 0.1))
        self.t += dt
        tgt = self.target(dt, pat, happy, asleep)
        w = 2 * math.pi * SPRING_F
        a = w * w * (tgt - self.x) - 2 * SPRING_ZETA * w * self.v
        self.v += a * dt
        self.x += self.v * dt
        self.x = max(-LIMIT, min(LIMIT, self.x))
        return self.x

    def angle(self) -> float:
        return self.x
