"""Qt-free state machine for lounging on a window top edge / input field (see docs/superpowers/specs/...lounge...).

States: idle -> (walk_to_field ->) lie_down -> lounge_loop <-> yawn -> sleep -> get_up -> idle;
edge dropping away: any lounge state -> fall -> (edge: lie_down again | floor: ground -> idle).
Inputs per tick: dt, the current probed geometry (or None), optional ``arrived``/``idle_s``. Output: ``Frame`` with the
anchor (screen point on the top edge), pose amounts and an optional speech category (all lines end with 喵)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from desk_pet_grok.focus_probe import FieldGeom, anchor_for

LIE_DOWN_S = 1.0
GET_UP_S = 0.8
LOST_S = 2.0  # geometry must be missing this long before she gets up
COOLDOWN_S = 60.0  # after getting up: no self-walk back
SLEEP_AFTER_S = 180.0
YAWN_S = 2.5
YAWN_GAP_S = (40.0, 90.0)
SAY_GAP_S = (35.0, 80.0)
SLEEP_SAY_GAP_S = (30.0, 60.0)
SELFWALK_IDLE_S = 600.0
SELFWALK_TRY_GAP_S = (60.0, 150.0)
POSE_RATE = 1.0  # pose units per second
MARGIN = 40.0
FALL_GAP = 48.0  # px: the edge dropping this far below where she sits (faster than FALL_FOLLOW) makes her fall
FALL_FOLLOW = 70.0  # px/s: slower downward drift of the edge is followed, not fallen from
PAT_EYES_DELAY_S = 0.35  # ears twitch first, then the eyes close
FALL_MAX_S = 6.0  # safety: a fall never lasts longer than this
GROUND_S = 0.85  # squash / recover on the screen floor
GROUND_COOLDOWN_S = 20.0


@dataclass(frozen=True)
class Frame:
    state: str
    anchor: Optional[tuple[float, float]]
    pose_loaf: float  # 0 standing .. 1 loaf
    pose_droop: float  # 0 head up .. 1 asleep
    yawn: float  # 0..1 yawn amount
    say: Optional[str] = None


class Lounge:
    def __init__(self, *, rng: random.Random | None = None, enabled: bool = True, selfwalk: bool = False,
                 on_event=None) -> None:
        self.on_event = on_event  # optional calibration hook: on_event(kind, **numbers)
        self.rng = rng or random.Random()
        self.enabled = enabled
        self.selfwalk = selfwalk
        self.state = "idle"
        self.t = 0.0  # time in current state
        self.t_lounge = 0.0  # time since lounging began / was last poked
        self.cooldown_left = 0.0
        self.lost = 0.0
        self.prefer_x = 0.0
        self.geom: Optional[FieldGeom] = None
        self.loaf = 0.0
        self.droop = 0.0
        self.yawn_amt = 0.0
        self._next_yawn = 0.0
        self._next_say = 0.0
        self._next_try = self.rng.uniform(*SELFWALK_TRY_GAP_S)
        self._clock = 0.0
        self.fall_gap = FALL_GAP
        self.fall_follow = FALL_FOLLOW
        self.petting = False
        self._pet_t = 0.0  # how long the current pat has lasted
        self._ref_y = 0.0  # edge height she is currently sitting on (follows slow drops, instantly follows rises)

    # ---- events ----
    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not enabled and self.state != "idle":
            self._to("idle")

    def on_drop(self, geom: Optional[FieldGeom], foot_x: float) -> bool:
        if not self.enabled or geom is None:
            return False
        self.geom, self.prefer_x, self.lost = geom, float(foot_x), 0.0
        self._ref_y = geom.y
        self._to("lie_down")
        self.t_lounge = 0.0
        self._say_pending = "lounge_start"
        return True

    def on_drag_start(self) -> None:
        if self.state != "idle":
            self._to("idle")
            self.cooldown_left = max(self.cooldown_left, COOLDOWN_S)
        self.loaf = self.droop = self.yawn_amt = 0.0

    def on_land(self, kind: str, geom: Optional[FieldGeom] = None, foot_x: float = 0.0) -> None:
        """Driver event: the fall ended on a window edge ("edge") or on the screen floor ("ground")."""
        if self.state != "fall":
            return
        if kind == "edge" and geom is not None:
            self.geom, self.prefer_x, self.lost = geom, float(foot_x), 0.0
            self._ref_y = geom.y
            self._to("lie_down")
            self.t_lounge = 0.0
            self._say_pending = None
        else:
            self._to("ground")

    def set_petting(self, on: bool) -> None:
        """Head-pat while lounging: wakes her (back to the awake lie), holds off sleep / yawns, eyes close happily."""
        on = bool(on)
        if on and not self.petting:
            self._pet_t = 0.0
            self.poke()
        self.petting = on

    def poke(self) -> None:
        """Click on her: wake up from sleep, restart the sleep timer."""
        if self.state in ("sleep", "yawn", "lounge_loop"):
            self.t_lounge = 0.0
            if self.state != "lounge_loop":
                self._to("lounge_loop")

    # ---- internals ----
    _say_pending: Optional[str] = None

    def _to(self, s: str) -> None:
        self.state, self.t = s, 0.0
        if s == "lounge_loop":
            self._next_yawn = self.rng.uniform(*YAWN_GAP_S)
            self._next_say = self.rng.uniform(*SAY_GAP_S) * 0.5

    @staticmethod
    def _approach(v: float, target: float, step: float) -> float:
        return min(target, v + step) if v < target else max(target, v - step)

    def tick(self, dt: float, geom: Optional[FieldGeom], *, arrived: bool = False, idle_s: float = 0.0) -> Frame:
        dt = max(0.0, min(dt, 0.5))
        self.t += dt
        self._clock += dt
        self.cooldown_left = max(0.0, self.cooldown_left - dt)
        say: Optional[str] = None
        st = self.state
        if st != "idle":
            self.lost = self.lost + dt if geom is None else 0.0
            if geom is not None:
                self.geom = geom
        if st == "idle":
            self._tick_idle(dt, geom, idle_s)
            if self.state == "walk_to_field":
                say = "self_walk"
        elif st == "walk_to_field":
            if self.lost >= LOST_S:
                self._to("idle")
                self.cooldown_left = COOLDOWN_S
            elif arrived and self.geom is not None:
                self.prefer_x = self.prefer_x
                self._to("lie_down")
                self.t_lounge = 0.0
                self._say_pending = "lounge_start"
        elif st == "fall":
            if self.t >= FALL_MAX_S:
                self._to("ground")
        elif st == "ground":
            if self.t >= GROUND_S:
                self._to("idle")
                self.cooldown_left = GROUND_COOLDOWN_S
        elif st in ("lie_down", "lounge_loop", "yawn", "sleep"):
            self.t_lounge += 0.0 if self.petting else dt  # being petted counts as interaction: no dozing off meanwhile
            if geom is not None:
                if geom.y <= self._ref_y:
                    self._ref_y = geom.y
                else:
                    self._ref_y = min(geom.y, self._ref_y + self.fall_follow * dt)
                if self.on_event is not None and geom.y - self._ref_y > 4.0:
                    self.on_event("edge_drop", gap=float(geom.y - self._ref_y), limit=float(self.fall_gap), dt=float(dt))
                if geom.y - self._ref_y > self.fall_gap:
                    if self.on_event is not None:
                        self.on_event("fall", gap=float(geom.y - self._ref_y), limit=float(self.fall_gap))
                    self._to("fall")
                    self.t_lounge = 0.0
                    return self._frame(dt, "pet_fall")
            if self.lost >= LOST_S:
                self._to("get_up")
                say = "lounge_end"
            elif st == "lie_down":
                if self.t >= LIE_DOWN_S:
                    self._to("lounge_loop")
                    say = self._say_pending
                    self._say_pending = None
            elif st == "lounge_loop":
                if self.t_lounge >= SLEEP_AFTER_S:
                    self._to("sleep")
                    self._next_say = self.rng.uniform(5.0, 12.0)
                elif self.t >= self._next_yawn and not self.petting:
                    self._to("yawn")
                elif self.t >= self._next_say:
                    say = "lounge"
                    self._next_say = self.t + self.rng.uniform(*SAY_GAP_S)
            elif st == "yawn":
                if self.t >= YAWN_S:
                    self._to("lounge_loop")
                    self._next_yawn = self.t + self.rng.uniform(*YAWN_GAP_S)
                    say = "yawn" if self.rng.random() < 0.5 else None
                    self._say_pending = None
            elif st == "sleep":
                if self.t >= self._next_say:
                    say = "lounge_sleep"
                    self._next_say = self.t + self.rng.uniform(*SLEEP_SAY_GAP_S)
        elif st == "get_up":
            if self.t >= GET_UP_S:
                self._to("idle")
                self.cooldown_left = COOLDOWN_S
        return self._frame(dt, say)

    def _frame(self, dt: float, say: Optional[str]) -> Frame:
        self._pose(dt)
        anchor = None
        if self.state in ("lie_down", "lounge_loop", "yawn", "sleep", "walk_to_field", "get_up") and self.geom is not None:
            anchor = anchor_for(self.geom, self.prefer_x, MARGIN)
        return Frame(self.state, anchor, self.loaf, self.droop, self.yawn_amt, say)

    def _tick_idle(self, dt: float, geom: Optional[FieldGeom], idle_s: float) -> None:
        if not (self.enabled and self.selfwalk) or geom is None:
            return
        if self.cooldown_left > 0 or idle_s < SELFWALK_IDLE_S:
            return
        if self._clock < self._next_try:
            return
        self._next_try = self._clock + self.rng.uniform(*SELFWALK_TRY_GAP_S)
        if self.rng.random() < 0.5:
            self.geom, self.lost = geom, 0.0
            self.prefer_x = geom.x + geom.w * self.rng.uniform(0.25, 0.75)
            self._to("walk_to_field")

    def _pose(self, dt: float) -> None:
        step = POSE_RATE * dt
        st = self.state
        loaf_t = 1.0 if st in ("lie_down", "lounge_loop", "yawn", "sleep") else 0.0
        droop_t = 1.0 if st == "sleep" else 0.0
        rate = 0.5
        if self.petting and st in ("lie_down", "lounge_loop", "yawn", "sleep"):
            self._pet_t += dt
            if self._pet_t >= PAT_EYES_DELAY_S:
                droop_t, rate = 1.0, 1.8  # squint through the half frame into the closed one
            else:
                droop_t = self.droop  # ears twitch with the eyes as they were
        elif self._pet_t:
            self._pet_t = 0.0
            rate = 1.4 if st in ("lounge_loop",) else rate
        fast = st in ("fall", "ground")  # startled: she snaps upright
        self.loaf = self._approach(self.loaf, loaf_t, step * 5.0 if fast else (step if st != "get_up" else step * 1.2))
        self.droop = self._approach(self.droop, droop_t, step * (5.0 if fast else rate))
        if st == "yawn":
            u = min(1.0, self.t / YAWN_S)
            self.yawn_amt = 1.0 - abs(2.0 * u - 1.0)
        else:
            self.yawn_amt = 0.0
