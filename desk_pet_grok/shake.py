"""v4-2: 「甩她会红温」 (Qt-free). Dragging her and whipping left-right fast builds up shake strength; when it passes thresholds
she escalates   晕 (dizzy) → 不耐烦 (annoyed) → 鼓脸 (puffed) → 红温冒蒸汽 (fuming) → 背过身赌气 (sulk).
Dizzy / annoyed fade on their own; from puffed on she stays angry until a head pat soothes her (long enough pat: 1.2 s, sulking 2.5 s;
a safety timer calms her after 10 minutes if petting is off)."""
from __future__ import annotations

from dataclasses import dataclass, field

BACK_PX = 12.0  # moving back this far from the extreme confirms a reversal
MIN_AMP_PX = 60.0  # a reversal counts when the cursor swung at least this far (peak to peak) ...
MAX_SWING_S = 0.4  # ... within this time (a quick whip, not a slow drag)
AMP_PER_POINT = 240.0  # px of swing for 1.0 strength (a reversal adds at most REV_MAX)
REV_MAX = 1.0
GAP_RESET_S = 0.6  # no motion for this long forgets the half-swing
DECAY_PER_S = 0.6  # strength lost per second once she is not being shaken (idle > 0.7 s)
THRESHOLDS = (4.0, 9.0, 15.0, 22.0)  # stage 1..4 (dizzy, annoyed, puffed, fuming); stage 5 = sulk
LATCH_STAGE = 3  # puffed and above stay until she is patted
SULK_AFTER_S = 3.0  # fuming and left alone -> turns her back
SULK_AT_STRENGTH = 30.0  # shaken this much while fuming: sulks one second after release
AUTO_CALM_S = 600.0
PAT_STEP_S = {1: 0.4, 2: 0.4, 3: 0.9, 4: 0.9, 5: 0.9}  # patting this long (s) moves her one step calmer: 5 sulk -> 4 fuming -> 3 puffed -> calm (1 / 2 -> calm)
PAT_GAP_RESET_S = 2.0  # progress survives pauses up to this long (the head zone is small; the cursor leaves it now and then)
FACE = {0: None, 1: "dizzy", 2: "annoyed", 3: "puffed", 4: "fuming", 5: "puffed"}
LINE = {1: "shake_dizzy", 2: "shake_annoyed", 3: "shake_puffed", 4: "shake_fuming", 5: "shake_sulk"}
CALM_LINE = "shake_calm"


@dataclass
class ShakeMeter:
    strength: float = 0.0
    reversals: int = 0
    _dir: int = 0
    _ref_x: float = 0.0
    _start_x: float = 0.0
    _start_t: float = 0.0
    _ext_x: float = 0.0
    _ext_t: float = 0.0
    _last_t: float = -1e9
    _last_rev: float = -1e9

    def feed(self, now: float, x: float) -> float:
        """Feed one drag sample (screen x); returns the strength added by it."""
        if now - self._last_t > GAP_RESET_S or self._dir == 0 and self._last_t < 0:
            self._dir = 0
            self._ref_x = x
        self._last_t = now
        if self._dir == 0:
            if abs(x - self._ref_x) >= 3.0:
                self._dir = 1 if x > self._ref_x else -1
                self._start_x, self._start_t = self._ref_x, now
                self._ext_x, self._ext_t = x, now
            return 0.0
        if (x - self._ext_x) * self._dir >= 0:
            self._ext_x, self._ext_t = x, now
            return 0.0
        if abs(self._ext_x - x) < BACK_PX:
            return 0.0
        amp, dur = abs(self._ext_x - self._start_x), self._ext_t - self._start_t
        gained = 0.0
        if amp >= MIN_AMP_PX and dur <= MAX_SWING_S:
            gained = min(REV_MAX, amp / AMP_PER_POINT)
            self.strength += gained
            self._last_rev = now
            self.reversals += 1
        self._start_x, self._start_t = self._ext_x, self._ext_t
        self._dir = -self._dir
        self._ext_x, self._ext_t = x, now
        return gained

    def decay(self, now: float, dt: float) -> None:
        if now - self._last_rev > 0.7:
            self.strength = max(0.0, self.strength - DECAY_PER_S * dt)

    def reset(self) -> None:
        self.strength = 0.0
        self._dir = 0
        self.reversals = 0
        self._last_t = -1e9


@dataclass
class AngerMachine:
    enabled: bool = False
    stage: int = 0
    meter: ShakeMeter = field(default_factory=ShakeMeter)
    dragging: bool = False
    events: list = field(default_factory=list)  # ("stage", new, old) / ("calm", old); drained by the window

    def __post_init__(self) -> None:
        self._idle = 0.0  # seconds since release (fuming -> sulk)
        self._angry_for = 0.0
        self._pat_acc = 0.0
        self._pat_gap = 0.0
        self._now = 0.0

    # ---- inputs ----
    def drag_sample(self, now: float, x: float) -> None:
        if not self.enabled:
            return
        self._now = now
        self.dragging = True
        self._idle = 0.0
        self._pat_acc = 0.0
        if self.stage == 5:
            return  # sulking: only a pat helps
        gained = self.meter.feed(now, x)
        if gained > 0:
            self._escalate()

    def release(self) -> None:
        self.dragging = False
        self._idle = 0.0

    def _escalate(self) -> None:
        s = self.meter.strength
        new = sum(1 for t in THRESHOLDS if s >= t)
        if new > self.stage:
            self._set(new)

    def _set(self, new: int) -> None:
        old = self.stage
        if new == old:
            return
        self.stage = new
        self.events.append(("stage", new, old))

    def pat(self, on: bool, dt: float) -> None:
        if not self.enabled or self.stage == 0:
            return
        if not on:
            self._pat_gap += dt
            if self._pat_gap > PAT_GAP_RESET_S:
                self._pat_acc = 0.0
            return
        self._pat_gap = 0.0
        self._pat_acc += dt
        if self._pat_acc < PAT_STEP_S.get(self.stage, 0.0):
            return
        self._pat_acc = 0.0
        if self.stage >= 4:  # one step calmer; the next step needs a fresh stretch of patting
            old, new = self.stage, self.stage - 1
            self.meter.strength = THRESHOLDS[new - 1] + 0.2
            self._idle = 0.0
            self.stage = new
            self.events.append(("soothe", new, old))
        else:
            self.calm()

    def calm(self) -> None:
        old = self.stage
        self.meter.reset()
        self.stage = 0
        self._angry_for = 0.0
        self._pat_acc = 0.0
        if old:
            self.events.append(("calm", old))

    def tick(self, now: float, dt: float) -> None:
        if not self.enabled:
            if self.stage:
                self.calm()
                self.events.clear()
            return
        self._now = now
        if self.stage == 0:
            self.meter.decay(now, dt)
            return
        if self.stage < LATCH_STAGE:
            self.meter.decay(now, dt)
            s = self.meter.strength
            lower = sum(1 for t in THRESHOLDS if s >= t - 0.8)
            if lower < self.stage and not self.dragging:
                self._set(lower if lower >= 0 else 0)
            if self.stage == 0:
                self.events.append(("calm", 1))
            return
        self._angry_for += dt
        if not self.dragging:
            self._idle += dt
            if self.stage == 4 and (self._idle >= SULK_AFTER_S or (self.meter.strength >= SULK_AT_STRENGTH and self._idle >= 1.0)):
                self._set(5)
        if self._angry_for >= AUTO_CALM_S:
            self.calm()

    def face(self):
        return FACE[self.stage]

    def drain(self) -> list:
        ev, self.events = self.events, []
        return ev
