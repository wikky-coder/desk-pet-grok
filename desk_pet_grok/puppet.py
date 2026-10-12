"""Pure logic for the 2.5D puppet (no Qt): state machine, bounds, prefs, hit test.

The puppet is driven by a single turn progress ``tp`` in [0, 1]:
0 = front (idle), 1 = full side (walk), in between = the pre-rendered
front→side turn clip. Walking happens only at ``tp == 1``; the walk frame
advances with *distance travelled* so feet never skate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from desk_pet_grok.springs import LEAN, Spring

MIN_HEIGHT = 160
MAX_HEIGHT = 320
DEFAULT_HEIGHT = 220
CANVAS_W = 360
CANVAS_H = 470
STRIDE_PX_PER_FRAME = 1.5  # stance-foot travel per walk frame, in canvas pixels
TURN_SECONDS = 0.6  # full front→side turn (bible §3.7: 18 frames @30 fps)
NATIVE_FACING = -1  # the shipped side sprites are drawn facing LEFT (-1)
LOOK_TP = 0.33  # partial turn toward the cursor in look-at mode
STOP_HOLD_S = 0.25  # debounce before turning back to the front
IDLE_FREEZE_S = 45.0  # no interaction → stop repainting
HOP_S = 0.43  # bible §3.11: 13 frames @30 fps
HOP_CANVAS_PX = 16.0
LEAN_MAX_DEG = 15.0
LEAN_PER_VX = 0.025  # deg per px/s of drag speed
# per-frame tables (frame 0..12): lift px, scaleY, scaleX  (volume ~conserved)
HOP_LIFT = (0, 0, 0, 6, 12, 15, 16, 14, 9, 2, 0, 0, 0)
HOP_SY = (1.00, 0.96, 0.93, 1.06, 1.04, 1.01, 1.00, 1.00, 1.01, 1.02, 0.92, 1.03, 1.00)
HOP_SX = (1.00, 1.02, 1.05, 0.96, 0.98, 1.00, 1.00, 1.00, 1.00, 0.99, 1.07, 0.99, 1.00)


def clamp_height(h: float) -> int:
    return max(MIN_HEIGHT, min(MAX_HEIGHT, int(round(h))))


def size_for_height(h: float) -> tuple[int, int]:
    hh = clamp_height(h)
    return int(round(hh * CANVAS_W / CANVAS_H)), hh


def clamp_to_screen(x: float, y: float, w: float, h: float, rect, margin: float = 0.0):
    """Keep a w×h window fully inside rect=(sx, sy, sw, sh) (available geometry)."""
    sx, sy, sw, sh = rect
    lo_x, hi_x = sx + margin, sx + sw - w - margin
    lo_y, hi_y = sy + margin, sy + sh - h - margin
    if hi_x < lo_x:
        hi_x = lo_x
    if hi_y < lo_y:
        hi_y = lo_y
    return min(max(x, lo_x), hi_x), min(max(y, lo_y), hi_y)


def walk_gain(ground_speed: float, height: float) -> float:
    """Walk-frames per second matching a ground speed (px/s) at window height."""
    k = height / CANVAS_H
    return ground_speed / (STRIDE_PX_PER_FRAME * k)


def hit_alpha(alpha_rows, x: int, y: int, pad: int = 2, cut: int = 12) -> bool:
    """True if any pixel within ``pad`` of (x, y) has alpha > cut.

    ``alpha_rows`` is a 2D sequence indexed [y][x]. Blank pixels → False so
    the click can fall through to the window below.
    """
    h = len(alpha_rows)
    if h == 0:
        return False
    w = len(alpha_rows[0])
    for yy in range(max(0, y - pad), min(h, y + pad + 1)):
        row = alpha_rows[yy]
        for xx in range(max(0, x - pad), min(w, x + pad + 1)):
            if row[xx] > cut:
                return True
    return False


def next_rest_frame(frame: float, rest_frames: list[int], n: int) -> tuple[int, int]:
    """Return (rest_frame, frames_to_go) — first rest frame at/after ``frame``."""
    best = None
    for r in rest_frames:
        d = (r - int(frame)) % n
        if best is None or d < best[1]:
            best = (r, d)
    return best if best else (0, 0)


@dataclass
class PuppetState:
    tp: float = 0.0
    side_facing: int = 1  # latched while tp > 0; +1 right
    walk_pos: float = 0.0  # walk-cycle frame position (float)
    settle_to: int | None = None  # rest frame we are walking out to before turning back
    settled: bool = False
    stop_timer: float = 0.0
    since_interact: float = 0.0
    hop_t: float = -1.0  # <0 = no hop
    lean: float = 0.0  # degrees (spring)
    lean_v: float = 0.0  # deg/s
    gain: float = 0.0  # 0..1 ramp that scales ground movement
    frozen: bool = False

    def clip(self) -> str:
        if self.tp <= 0.0:
            return "idle"
        if self.tp >= 1.0:
            return "walk"
        return "turn"


class PuppetLogic:
    """Deterministic idle → turn_out → walk → turn_in → idle machine."""

    def __init__(self, n_walk: int = 60, rest_frames: list[int] | None = None) -> None:
        self.s = PuppetState()
        self.n_walk = n_walk
        self.rest_frames = rest_frames or [0]
        self.want_walk = False
        self.want_facing = 1
        self.look = False
        self.dragging = False
        self.drag_vx = 0.0
        self._lean = Spring(*LEAN)
        self.phase_ok = True  # idle breath phase allows a turn to start (seam match)

    # ---- inputs ----
    def set_walk(self, want: bool, facing: int) -> None:
        self.want_walk = bool(want) and not self.dragging
        self.want_facing = 1 if facing >= 0 else -1
        if want:
            self.wake()

    def set_look(self, look: bool) -> None:
        self.look = bool(look)
        self.wake()

    def set_dragging(self, dragging: bool, vx: float = 0.0) -> None:
        self.dragging = bool(dragging)
        self.drag_vx = vx if dragging else 0.0
        if dragging:
            self.want_walk = False
            self.s.gain = 0.0
            self.s.settle_to = None
            self.wake()

    def hop(self) -> None:
        self.s.hop_t = 0.0
        self.wake()

    def wake(self) -> None:
        self.s.since_interact = 0.0
        self.s.frozen = False

    # ---- derived ----
    @property
    def walking(self) -> bool:
        return (self.s.tp >= 1.0 and self.want_walk and self.s.settle_to is None
                and self.s.side_facing == self.want_facing and not self.s.settled)

    def animating(self) -> bool:
        s = self.s
        return not s.frozen

    def mirror(self) -> bool:
        """Flip horizontally when the wanted side differs from the drawn side."""
        return self.s.side_facing != NATIVE_FACING

    def hop_pose(self) -> tuple[float, float, float]:
        """(y_offset_canvas_px (negative = up), scale_x, scale_y) from the 13-frame table."""
        t = self.s.hop_t
        if t < 0:
            return 0.0, 1.0, 1.0
        f = min(len(HOP_LIFT) - 1.0, t / HOP_S * (len(HOP_LIFT) - 1))
        i = int(f)
        j = min(i + 1, len(HOP_LIFT) - 1)
        u = f - i

        def lerp(tab):
            return tab[i] + (tab[j] - tab[i]) * u

        return -lerp(HOP_LIFT), lerp(HOP_SX), lerp(HOP_SY)

    def hop_offset(self) -> tuple[float, float]:
        y, _sx, sy = self.hop_pose()
        return y, sy

    def target_tp(self) -> float:
        s = self.s
        if self.dragging:
            return 0.0
        match = s.side_facing == self.want_facing
        if s.tp >= 1.0:
            if self.want_walk and match:
                return 1.0
            return 1.0 if not s.settled else 0.0
        if self.want_walk:
            if s.tp > 0.0 and not match:
                return 0.0
            return 1.0
        if self.look:
            if s.tp > 0.0 and not match:
                return 0.0
            return LOOK_TP
        return 0.0

    # ---- step ----
    def tick(self, dt: float, ground_dx: float = 0.0, height: float = DEFAULT_HEIGHT) -> None:
        """Advance. ``ground_dx`` = actual window displacement (px) this tick."""
        s = self.s
        dt = max(0.0, min(dt, 0.1))
        s.since_interact += dt
        if s.hop_t >= 0:
            s.hop_t += dt
            if s.hop_t >= HOP_S:
                s.hop_t = -1.0
        # drag tilt: damped spring (f 1.6 Hz, zeta 0.35) toward -k*vx, capped at +-15 deg.
        # Positive = clockwise about the grab point, so the feet trail the motion.
        want_lean = 0.0
        if self.dragging:
            want_lean = max(-LEAN_MAX_DEG, min(LEAN_MAX_DEG, self.drag_vx * LEAN_PER_VX))
        sp = self._lean
        sp.x, sp.v = s.lean - want_lean, s.lean_v  # spring displacement is relative to the target
        sp.step(dt)
        s.lean, s.lean_v = sp.x + want_lean, sp.v
        s.lean = max(-LEAN_MAX_DEG, min(LEAN_MAX_DEG, s.lean))
        if want_lean == 0.0 and abs(s.lean) < 0.3 and abs(s.lean_v) < 3.0:
            s.lean = s.lean_v = 0.0

        # latch facing when leaving the front
        if s.tp <= 0.0:
            if self.want_walk:
                s.side_facing = self.want_facing
            elif self.look:
                s.side_facing = self.want_facing

        # walking → settle logic
        if s.tp >= 1.0:
            if self.want_walk and s.side_facing == self.want_facing:
                s.stop_timer = 0.0
                s.settle_to = None
                s.settled = False
            else:
                s.stop_timer += dt
                if s.settle_to is None and not s.settled and s.stop_timer >= STOP_HOLD_S:
                    r, _ = next_rest_frame(s.walk_pos, self.rest_frames, self.n_walk)
                    s.settle_to = r
        # walk frame advance by distance
        if s.tp >= 1.0:
            if self.walking:
                s.walk_pos = (s.walk_pos + abs(ground_dx) / (STRIDE_PX_PER_FRAME * height / CANVAS_H)) % self.n_walk
            elif s.settle_to is not None:
                # glide to the rest frame at a gentle fixed pace
                cur = int(s.walk_pos) % self.n_walk
                if cur == s.settle_to:
                    s.settle_to = None
                    s.settled = True
                else:
                    s.walk_pos = (s.walk_pos + 45.0 * dt) % self.n_walk
                    if (s.settle_to - int(s.walk_pos)) % self.n_walk > self.n_walk // 2:
                        s.walk_pos = float(s.settle_to)
                        s.settle_to = None
                        s.settled = True
        # gain ramps for ground movement
        if self.walking:
            s.gain = min(1.0, s.gain + dt / 0.35)
        else:
            s.gain = max(0.0, s.gain - dt / 0.2)

        # turn progress
        tgt = self.target_tp()
        if s.tp <= 0.0 and tgt > 0.0 and not self.phase_ok:
            tgt = 0.0  # wait (briefly) for the idle breath to match turn frame 0
        rate = dt / TURN_SECONDS
        if s.tp < tgt:
            s.tp = min(tgt, s.tp + rate)
        elif s.tp > tgt:
            s.tp = max(tgt, s.tp - rate)
        if s.tp < 1.0:
            s.settled = False
            s.settle_to = None
        if s.tp <= 0.0:
            s.walk_pos = float(self.rest_frames[0])
            s.settle_to = None
            s.stop_timer = 0.0

        # freeze when nothing happens for a long time
        idle = (
            s.tp <= 0.0 and not self.want_walk and not self.look and not self.dragging
            and s.hop_t < 0 and s.lean == 0.0
        )
        if idle and s.since_interact >= IDLE_FREEZE_S:
            s.frozen = True
        elif not idle:
            s.frozen = False
            if not self.want_walk:
                pass

    def turn_frame(self, n_turn: int = 24) -> int:
        u = max(0.0, min(1.0, self.s.tp))
        u = u * u * (3.0 - 2.0 * u)  # ease in/out like a person turning
        return max(0, min(n_turn - 1, int(round(u * (n_turn - 1)))))
