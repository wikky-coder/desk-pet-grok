"""Head-pat (摸头) detection from the global mouse position. Qt-free, no new permissions.

A pat = the cursor zig-zags horizontally over her head zone: at least ``reversals`` direction changes (each leg at
least ``min_swing`` px long and moving at least ``min_speed`` px/s) within ``window_s`` seconds. Once detected it stays
active while folds keep coming, and drops ``hold_s`` after the last fold; leaving the zone drops it immediately.
Straight sweeps, parked cursors and tiny jitter never trigger it. Tune via ``PARAMS`` / the menu sensitivity."""

from __future__ import annotations

from dataclasses import dataclass

LEVELS = ("low", "mid", "high")


@dataclass(frozen=True)
class PettingParams:
    reversals: int  # direction changes needed inside window_s
    min_swing: float  # px: a leg shorter than this is jitter (also the direction hysteresis)
    min_speed: float  # px/s: a leg slower than this is not a stroke
    window_s: float = 1.5
    hold_s: float = 1.0  # stay active this long after the last fold
    lenient: bool = False  # a short / slow leg is just ignored instead of breaking the stroke (lying pose)


PARAMS = {
    "low": PettingParams(reversals=4, min_swing=36.0, min_speed=200.0),
    "mid": PettingParams(reversals=3, min_swing=24.0, min_speed=140.0),
    "high": PettingParams(reversals=3, min_swing=12.0, min_speed=70.0),
}

# lying on an edge she is petted with a looser rule (the zone is smaller on screen and she is a bit harder to hit)
LYING_SCALE = 0.6  # min_swing and min_speed of the chosen level x this
LYING_WINDOW_S = 2.2
LYING_REVERSALS_DROP = 1  # one fewer direction change than standing (mid 3 -> 2, low 4 -> 3, high stays 2)
LYING_MIN_REVERSALS = 2

# head zone as fractions of the pet window (x0, y0, x1, y1)
ZONE_FRAC = (0.22, 0.03, 0.78, 0.38)


def params_for(level: str, overrides: dict | None = None) -> PettingParams:
    """Built-in params for ``level``, optionally patched by settings ``petting_params`` = {level: {field: number}}."""
    base = PARAMS.get(level, PARAMS["mid"])
    ov = (overrides or {}).get(level if level in PARAMS else "mid")
    if not isinstance(ov, dict):
        return base
    vals = {}
    for f in ("reversals", "min_swing", "min_speed", "window_s", "hold_s"):
        try:
            if f in ov:
                vals[f] = int(ov[f]) if f == "reversals" else float(ov[f])
        except (TypeError, ValueError):
            continue
    return PettingParams(**{**base.__dict__, **vals}) if vals else base


def lying_params(level: str, overrides: dict | None = None) -> PettingParams:
    """Looser params for the lying pose, derived from the selected sensitivity level (so the menu still applies)."""
    b = params_for(level, overrides)
    return PettingParams(
        reversals=max(LYING_MIN_REVERSALS, b.reversals - LYING_REVERSALS_DROP),
        min_swing=b.min_swing * LYING_SCALE,
        min_speed=b.min_speed * LYING_SCALE,
        window_s=max(b.window_s, LYING_WINDOW_S),
        hold_s=b.hold_s,
        lenient=True,
    )


def head_zone(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
    a, b, c, d = ZONE_FRAC
    return (x + a * w, y + b * h, x + c * w, y + d * h)


def in_zone(zone: tuple[float, float, float, float], px: float, py: float) -> bool:
    return zone[0] <= px <= zone[2] and zone[1] <= py <= zone[3]


class PettingDetector:
    def __init__(self, level: str = "mid", overrides: dict | None = None, on_event=None) -> None:
        self.overrides = overrides
        self.on_event = on_event  # optional calibration hook: on_event(kind, **numbers)
        self.params = params_for(level, overrides)
        self.reset()

    def set_level(self, level: str) -> None:
        self.params = params_for(level, self.overrides)
        self.reset()

    def _emit(self, kind: str, **kw) -> None:
        if self.on_event is not None:
            self.on_event(kind, **kw)

    def reset(self) -> None:
        self.active = False
        self._dir = 0
        self._ext_x: float | None = None  # current extreme of the leg being travelled
        self._ext_t = 0.0
        self._leg_x = 0.0  # where that leg started
        self._leg_t = 0.0
        self._folds: list[float] = []
        self._last_fold = -1e9
        self._lo = self._hi = None

    def feed(self, t: float, x: float, y: float, inside: bool) -> bool:
        """One cursor sample (seconds, screen px, over-the-head-zone flag). Returns whether she is being patted."""
        del y  # only the horizontal zig-zag matters; the zone already bounds y
        p = self.params
        if not inside:
            if self._folds and not self.active:
                self._emit("pat_abort", folds=len(self._folds))
            self.reset()
            return False
        if self._ext_x is None:
            self._ext_x = self._leg_x = x
            self._ext_t = self._leg_t = t
            return self.active
        d = self._dir
        if d == 0 and p.lenient:
            # lying pose: judge the first direction from the span travelled so far, not from the very first sample
            self._lo = x if self._lo is None else min(self._lo, x)
            self._hi = x if self._hi is None else max(self._hi, x)
            if self._hi - self._lo >= p.min_swing:
                self._dir = 1 if x >= (self._lo + self._hi) / 2 else -1
                self._ext_x, self._ext_t = x, t
                self._leg_x, self._leg_t = (self._lo if self._dir == 1 else self._hi), t - 0.15
            return self.active
        if d == 0:
            if abs(x - self._ext_x) >= p.min_swing:
                self._dir = 1 if x > self._ext_x else -1
                self._ext_x, self._ext_t = x, t
            return self.active
        if (x - self._ext_x) * d > 0:
            self._ext_x, self._ext_t = x, t  # same direction: extend the leg
        elif (self._ext_x - x) * d >= p.min_swing:
            leg = abs(self._ext_x - self._leg_x)
            dur = max(1e-3, self._ext_t - self._leg_t)
            ok = leg >= p.min_swing and leg / dur >= p.min_speed
            self._emit("pat_fold", leg=float(leg), speed=float(leg / dur), ok=ok, folds=len(self._folds) + (1 if ok else 0))
            if ok:
                self._folds.append(t)
                self._last_fold = t
            elif not p.lenient:
                self._folds.clear()  # a short or slow leg breaks the stroke
            self._dir = -d
            self._leg_x, self._leg_t = self._ext_x, self._ext_t
            self._ext_x, self._ext_t = x, t
        self._folds = [f for f in self._folds if t - f <= p.window_s]
        if len(self._folds) >= p.reversals:
            if not self.active:
                self._emit("pat_trigger", folds=len(self._folds))
            self.active = True
        elif self.active and t - self._last_fold > p.hold_s:
            self.active = False
        return self.active


class LyingPettingDetector:
    """Head-pat detector for the lying pose: looser params, and a stroke may run along either axis (horizontal, vertical
    or diagonal wiggles all count), so slow, small, slanted back-and-forth motion still triggers. Straight sweeps and a
    parked cursor still do not."""

    def __init__(self, level: str = "mid", overrides: dict | None = None, on_event=None) -> None:
        self.overrides, self.level, self.on_event = overrides, level, on_event
        self._axes = [PettingDetector(level, overrides, on_event=self._ev) for _ in range(2)]
        for d in self._axes:
            d.params = lying_params(level, overrides)

    def _ev(self, kind: str, **kw) -> None:
        if self.on_event is not None:
            self.on_event(kind, **kw)

    @property
    def params(self) -> PettingParams:
        return self._axes[0].params

    @property
    def active(self) -> bool:
        return any(d.active for d in self._axes)

    def set_level(self, level: str) -> None:
        self.level = level
        for d in self._axes:
            d.params = lying_params(level, self.overrides)
            d.reset()

    def reset(self) -> None:
        for d in self._axes:
            d.reset()

    def feed(self, t: float, x: float, y: float, inside: bool) -> bool:
        a = self._axes[0].feed(t, x, y, inside)
        b = self._axes[1].feed(t, y, x, inside)  # second tracker follows the vertical coordinate
        return a or b
