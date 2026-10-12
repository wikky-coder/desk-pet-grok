"""Pure motion modes for 桌宠grok: wander, look-at (follow), still + facing."""

from __future__ import annotations

import math
import random
from enum import Enum
from typing import Sequence


class MotionMode(str, Enum):
    wander = "wander"
    follow = "follow"
    still = "still"


MODE_VALUES = frozenset(m.value for m in MotionMode)

# Screen inset so the pet doesn't hug the edge.
_MARGIN = 24.0
# Wander — soft desk-pet cruise (not a seeking drone)
_WANDER_SPEED = 65.0  # px/s cruise
_WANDER_ARRIVE = 14.0  # settle into rest inside this radius
_WANDER_SLOW_RADIUS = 70.0  # ease-out starts here
_WANDER_REST_MIN = 25.0
_WANDER_REST_MAX = 60.0
_WANDER_ACCEL = 2.4  # ease-in toward desired velocity
_WANDER_MAX_TURN_DEG = 120.0  # deg/s heading change cap
_WANDER_HOP_MIN = 60.0
_WANDER_HOP_MAX = 150.0
_WANDER_MAX_DY = 40.0  # prefer mostly-horizontal hops
_WANDER_REST_DAMP = 5.5  # 1/s velocity decay while resting
# Facing hysteresis (avoid flicker on tiny vx wobble)
_FACING_VX_MIN = 14.0  # need meaningful |vx|
_FACING_HOLD_S = 0.14  # must keep opposite sign this long
# Follow: stay put; face toward cursor (look-at, not chase).
_FOLLOW_FACE_DEADZONE = 8.0  # px; ignore tiny cursor jitter near pet center
# Soft clamp spring back when past margin.
_CLAMP_SOFT = 0.35


def parse_mode(value: object, default: MotionMode = MotionMode.wander) -> MotionMode:
    """Parse a settings string into MotionMode."""
    if isinstance(value, MotionMode):
        return value
    if isinstance(value, str) and value in MODE_VALUES:
        return MotionMode(value)
    return default


def _angle_diff(a: float, b: float) -> float:
    """Shortest signed difference b - a in radians, in (-pi, pi]."""
    d = (b - a + math.pi) % (2.0 * math.pi) - math.pi
    return d


class MotionController:
    """Holds velocity / facing / mode; ``tick`` returns new window top-left + facing."""

    def __init__(self, *, mode: MotionMode | str = MotionMode.wander, rng: random.Random | None = None) -> None:
        self.mode = parse_mode(mode)
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1  # 1 right, -1 left
        self._rng = rng if rng is not None else random.Random()
        self._target: tuple[float, float] | None = None
        self._rest_left = 0.0
        self.flat = False
        self._heading: float | None = None  # radians; None until first steer
        self._face_pending: int | None = None
        self._face_hold = 0.0
        self._last_x: float | None = None
        self._last_y: float | None = None

    def release(self) -> None:
        """After a drag: forget the old target and resume wandering from here."""
        self._target = None
        self._heading = None
        self.vx = 0.0
        self.vy = 0.0
        self._rest_left = 0.8

    def set_mode(self, mode: MotionMode | str) -> None:
        self.mode = parse_mode(mode)
        self.vx = 0.0
        self.vy = 0.0
        self._target = None
        self._rest_left = 0.0
        self._heading = None
        self._face_pending = None
        self._face_hold = 0.0

    def tick(
        self,
        dt: float,
        win_pos: Sequence[float],
        win_size: Sequence[float],
        screen_rect: Sequence[float],
        cursor_pos: Sequence[float],
        dragging: bool,
    ) -> tuple[float, float, int]:
        """Advance motion.

        Args:
            dt: seconds since last tick (clamped internally).
            win_pos: (x, y) window top-left.
            win_size: (w, h).
            screen_rect: (sx, sy, sw, sh) available geometry.
            cursor_pos: (cx, cy) global cursor.
            dragging: when True, do not auto-move; update facing from delta x.

        Returns:
            (new_x, new_y, facing)
        """
        dt = max(0.0, min(float(dt), 0.1))
        x, y = float(win_pos[0]), float(win_pos[1])
        w, h = float(win_size[0]), float(win_size[1])
        sx, sy, sw, sh = (float(v) for v in screen_rect)
        cx, cy = float(cursor_pos[0]), float(cursor_pos[1])

        if dragging:
            if self._last_x is not None:
                dx = x - self._last_x
                if abs(dx) >= 0.5:
                    self.facing = 1 if dx > 0 else -1
            self._last_x = x
            self._last_y = y
            self.vx = 0.0
            self.vy = 0.0
            self._face_pending = None
            self._face_hold = 0.0
            return x, y, self.facing

        if self.mode is MotionMode.still:
            self.vx = 0.0
            self.vy = 0.0
            self._last_x = x
            self._last_y = y
            return x, y, self.facing

        if self.mode is MotionMode.follow:
            x, y = self._tick_follow(dt, x, y, w, h, cx, cy)
            # Facing comes from look-at; do not derive from velocity.
        else:
            x, y = self._tick_wander(dt, x, y, w, h, sx, sy, sw, sh)
            x, y = soft_clamp(x, y, w, h, sx, sy, sw, sh)
            self._update_facing_hysteresis(dt)
        self._last_x = x
        self._last_y = y
        return x, y, self.facing

    def _update_facing_hysteresis(self, dt: float) -> None:
        """Flip facing only when horizontal velocity is clear and stable."""
        if abs(self.vx) < _FACING_VX_MIN:
            self._face_pending = None
            self._face_hold = 0.0
            return
        want = 1 if self.vx > 0 else -1
        if want == self.facing:
            self._face_pending = None
            self._face_hold = 0.0
            return
        if self._face_pending != want:
            self._face_pending = want
            self._face_hold = 0.0
        self._face_hold += dt
        if self._face_hold >= _FACING_HOLD_S:
            self.facing = want
            self._face_pending = None
            self._face_hold = 0.0

    def _tick_follow(
        self,
        dt: float,
        x: float,
        y: float,
        w: float,
        h: float,
        cx: float,
        cy: float,
    ) -> tuple[float, float]:
        """Stay in place; face the cursor horizontally."""
        del dt, cy  # look-at uses x only; keep signature stable
        self.vx = 0.0
        self.vy = 0.0
        center_x = x + w * 0.5
        dx = cx - center_x
        if abs(dx) >= _FOLLOW_FACE_DEADZONE:
            self.facing = 1 if dx > 0 else -1
        return x, y

    def _tick_wander(
        self,
        dt: float,
        x: float,
        y: float,
        w: float,
        h: float,
        sx: float,
        sy: float,
        sw: float,
        sh: float,
    ) -> tuple[float, float]:
        if self._rest_left > 0:
            self._rest_left = max(0.0, self._rest_left - dt)
            damp = max(0.0, 1.0 - _WANDER_REST_DAMP * dt)
            self.vx *= damp
            self.vy *= damp
            if abs(self.vx) < 0.5:
                self.vx = 0.0
            if abs(self.vy) < 0.5:
                self.vy = 0.0
            return x + self.vx * dt, y + self.vy * dt

        if self._target is None:
            self._target = self._pick_target(x, y, w, h, sx, sy, sw, sh)
            if self.flat:  # ground-walking puppet: horizontal strolls only
                self._target = (self._target[0], y)

        tx, ty = self._target
        dx = tx - x
        dy = ty - y
        dist = math.hypot(dx, dy)

        # Ease-out: desired speed scales down inside slow radius, then rest.
        if dist <= _WANDER_ARRIVE:
            self._target = None
            self._rest_left = self._rng.uniform(_WANDER_REST_MIN, _WANDER_REST_MAX)
            self._heading = None
            # Do not slam velocity — leave residual for rest damp.
            return x + self.vx * dt, y + self.vy * dt

        if dist < _WANDER_SLOW_RADIUS:
            speed_scale = max(0.12, dist / _WANDER_SLOW_RADIUS)
        else:
            speed_scale = 1.0
        desired_speed = _WANDER_SPEED * speed_scale

        desired_heading = math.atan2(dy, dx)
        if self._heading is None:
            speed_now = math.hypot(self.vx, self.vy)
            if speed_now > 4.0:
                self._heading = math.atan2(self.vy, self.vx)
            else:
                self._heading = desired_heading

        max_turn = math.radians(_WANDER_MAX_TURN_DEG) * dt
        delta = _angle_diff(self._heading, desired_heading)
        if abs(delta) > max_turn:
            delta = math.copysign(max_turn, delta)
        self._heading += delta

        desired_vx = math.cos(self._heading) * desired_speed
        desired_vy = math.sin(self._heading) * desired_speed

        blend = min(1.0, _WANDER_ACCEL * dt)
        self.vx += (desired_vx - self.vx) * blend
        self.vy += (desired_vy - self.vy) * blend

        # Hard cap slightly above cruise (accel overshoot / turn).
        speed = math.hypot(self.vx, self.vy)
        max_speed = _WANDER_SPEED * 1.15
        if speed > max_speed and speed > 0.0:
            scale = max_speed / speed
            self.vx *= scale
            self.vy *= scale

        return x + self.vx * dt, y + self.vy * dt

    def _pick_target(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        sx: float,
        sy: float,
        sw: float,
        sh: float,
    ) -> tuple[float, float]:
        """Short, mostly-horizontal hop within the usable screen rect."""
        min_x = sx + _MARGIN
        min_y = sy + _MARGIN
        max_x = sx + sw - w - _MARGIN
        max_y = sy + sh - h - _MARGIN
        if max_x < min_x:
            max_x = min_x
        if max_y < min_y:
            max_y = min_y

        for _ in range(12):
            dist = self._rng.uniform(_WANDER_HOP_MIN, _WANDER_HOP_MAX)
            # Prefer left/right; small vertical drift only.
            sign = -1.0 if self._rng.random() < 0.5 else 1.0
            # Bias toward continuing current facing when known.
            if abs(self.vx) >= 4.0:
                sign = 1.0 if self.vx > 0 else -1.0
                if self._rng.random() < 0.22:
                    sign = -sign
            elif self._rng.random() < 0.7:
                sign = float(self.facing)

            dx = sign * dist
            dy = self._rng.uniform(-_WANDER_MAX_DY, _WANDER_MAX_DY)
            # Occasional tiny vertical-only drift (rare)
            if self._rng.random() < 0.08:
                dx = self._rng.uniform(-40.0, 40.0)
                dy = self._rng.uniform(-_WANDER_MAX_DY * 0.8, _WANDER_MAX_DY * 0.8)

            tx = min(max_x, max(min_x, x + dx))
            ty = min(max_y, max(min_y, y + dy))
            if math.hypot(tx - x, ty - y) >= _WANDER_HOP_MIN * 0.45:
                return (tx, ty)

        # Fallback: any point in bounds near current y.
        tx = self._rng.uniform(min_x, max_x)
        ty = min(max_y, max(min_y, y + self._rng.uniform(-_WANDER_MAX_DY, _WANDER_MAX_DY)))
        return (tx, ty)


def soft_clamp(
    x: float,
    y: float,
    w: float,
    h: float,
    sx: float,
    sy: float,
    sw: float,
    sh: float,
) -> tuple[float, float]:
    """Keep the window mostly inside the screen with a soft pull-back."""
    min_x = sx + _MARGIN * 0.25
    min_y = sy + _MARGIN * 0.25
    max_x = sx + sw - w - _MARGIN * 0.25
    max_y = sy + sh - h - _MARGIN * 0.25
    if max_x < min_x:
        max_x = min_x
    if max_y < min_y:
        max_y = min_y

    if x < min_x:
        x = x + (min_x - x) * _CLAMP_SOFT
        if x < min_x - _MARGIN:
            x = min_x - _MARGIN
    elif x > max_x:
        x = x + (max_x - x) * _CLAMP_SOFT
        if x > max_x + _MARGIN:
            x = max_x + _MARGIN

    if y < min_y:
        y = y + (min_y - y) * _CLAMP_SOFT
        if y < min_y - _MARGIN:
            y = min_y - _MARGIN
    elif y > max_y:
        y = y + (max_y - y) * _CLAMP_SOFT
        if y > max_y + _MARGIN:
            y = max_y + _MARGIN

    return x, y
