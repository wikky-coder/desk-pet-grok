"""Glue between the Qt-free ``Lounge`` state machine, a ``FieldProbe`` and the pet window (feature flag ``lounge``).

Never raises/activates windows: it only moves the pet window and sets the rig pose. Geometry is polled about once per
second while lounging (or when self-walk is on); nothing about the focused app is stored or logged."""

from __future__ import annotations

import math
import random
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from desk_pet_grok import focus_probe, puppet
from desk_pet_grok.focus_probe import (DockProbe, FieldGeom, FieldProbe, anchor_for, clamp_anchor_to_screens,
                                       dock_drop_accepts)
from desk_pet_grok.lounge import GROUND_S, Lounge

POLL_MS = 500  # geometry poll while lounging (fast enough to notice the edge dropping)
DROP_BAND_ABOVE = 80.0  # feet may be this far above the edge (px) and still count as "dropped on it"
DROP_BAND_BELOW = 70.0
TOP_SCREEN_SLACK = 70.0  # maximised window: her window is clamped to the screen top
FOOT_PAD = 12.0  # canvas px between the sprite's feet and the window bottom (see Pet25D)
SINK = 4.0  # canvas px the loaf sinks into the edge
EASE = 8.0
MAX_SPEED = 1600.0
# fall physics, in canvas px (scaled by the window's k = height / CANVAS_H)
FALL_V0 = 620.0  # initial upward "throw" speed (canvas px/s)
FALL_G = 4200.0
FALL_VMAX = 2700.0
LIFT_RAMP_S = 0.18  # ears / tail take this long to stream up
EDGE_SQ_S = 0.30  # small squash when she lands back on an edge
GROUND_SQ_DEPTH = 0.30
DOCK_TOL = 40.0  # drop tolerance for the Dock's top edge (px)


class FallSim:
    """Qt-free fall physics for the window's top-left ``y``: throw up a little, accelerate down, land on an edge or the floor."""

    def __init__(self, y: float, k: float, h: float) -> None:
        self.k, self.h = k, h
        self.y = float(y)
        self.vy = -FALL_V0 * k
        self.t = 0.0

    def foot_y(self) -> float:
        return self.y + self.h - FOOT_PAD * self.k

    def lift(self) -> float:
        return min(1.0, self.t / LIFT_RAMP_S)

    def stretch(self) -> tuple[float, float]:
        """(sx, sy) about the feet: tall and thin while airborne, a hint of crouch right at the throw."""
        if self.vy < 0:
            u = min(1.0, self.t / 0.2)
            return 1.0 - 0.03 * u, 1.0 + 0.05 * u
        u = min(1.0, self.vy / (FALL_VMAX * self.k))
        return 1.0 - 0.05 * u, 1.0 + 0.07 * u

    def step(self, dt: float, geom: Optional[FieldGeom], foot_x: float, floor_foot_y: float) -> Optional[str]:
        """Advance; returns "edge" / "ground" on landing, else None."""
        dt = max(0.0, min(dt, 0.05))
        self.t += dt
        prev_foot = self.foot_y()
        self.vy = min(self.vy + FALL_G * self.k * dt, FALL_VMAX * self.k)
        self.y += self.vy * dt
        foot = self.foot_y()
        if geom is not None and self.vy > 0 and geom.x <= foot_x <= geom.x + geom.w:
            if prev_foot <= geom.y + 6.0 and foot >= geom.y - 2.0:
                return "edge"
        if foot >= floor_foot_y:
            self.y += floor_foot_y - foot
            return "ground"
        return None


def landing_squash(u: float, depth: float) -> tuple[float, float]:
    """Damped squash-and-rebound after touching down, u = 0..1 -> (sx, sy). Volume roughly conserved; ends at (1, 1)."""
    u = max(0.0, min(1.0, u))
    s = math.exp(-4.2 * u) * math.cos(2 * math.pi * 1.5 * u) * (1.0 - u ** 6)
    sy = 1.0 - depth * s
    sx = 1.0 + 0.6 * depth * s
    return sx, sy


def drop_accepts(geom: Optional[FieldGeom], foot: tuple[float, float], win_top: float, screen_top: float) -> bool:
    """Pure: is a pet dropped with feet at ``foot`` (window top at win_top) close enough to the geom's top edge?"""
    if geom is None:
        return False
    fx, fy = foot
    if not (geom.x <= fx <= geom.x + geom.w):
        return False
    if geom.y - DROP_BAND_ABOVE <= fy <= geom.y + DROP_BAND_BELOW:
        return True
    return win_top <= screen_top + 4.0 and geom.y <= screen_top + TOP_SCREEN_SLACK  # shoved to the screen top


def window_target(anchor: tuple[float, float], w: int, h: int, screen_top: float) -> tuple[float, float]:
    """Top-left of the pet window so her feet rest on the anchor (clamped so the head stays reachable)."""
    k = h / puppet.CANVAS_H
    x = anchor[0] - w / 2.0
    y = anchor[1] - (h - (FOOT_PAD - SINK) * k)
    return x, max(y, screen_top - 0.45 * h)


class LoungeDriver(QObject):
    say = Signal(str)

    def __init__(self, window, *, probe: FieldProbe | None = None, rng: random.Random | None = None,
                 idle_fn: Callable[[], float] | None = None) -> None:
        super().__init__(window)
        self._w = window
        self.lounge = Lounge(rng=rng, enabled=False, selfwalk=False)
        self.probe = probe or focus_probe.WindowEdgeProbe()
        self._idle_fn = idle_fn or focus_probe.idle_seconds
        self.dock_probe: FieldProbe = DockProbe()
        self.dock_enabled = True  # menu: 也趴程序坞
        self.dock_tol = DOCK_TOL  # px around the Dock's top edge that counts as "dropped on it"
        self._src = "window"  # what she is lying on: "window" | "dock"
        self._geom: Optional[FieldGeom] = None
        self._idle_s = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._fx = self._fy = 0.0  # float window position while we drive it
        self._was_active = False
        self._fall: Optional[FallSim] = None
        self._land_t = 1e9  # seconds since touching down (edge squash)
        self._ground_t = 0.0

    # ---- configuration ----
    @property
    def enabled(self) -> bool:
        return self.lounge.enabled

    def set_enabled(self, on: bool) -> None:
        self.lounge.set_enabled(on)
        if on:
            self._timer.start()
        else:
            self._timer.stop()
            self._release()

    def set_selfwalk(self, on: bool) -> None:
        self.lounge.selfwalk = bool(on)

    def active(self) -> bool:
        return self.lounge.state != "idle"

    # ---- events from the window ----
    def _poll(self) -> None:
        if not self.lounge.enabled:
            return
        if self.active() and self._src == "dock":
            self._geom = self.dock_probe.sample() if self.dock_enabled else None  # hidden / moved / switched off -> she gets up
            self._idle_s = 0.0
            return
        if self.active() or self.lounge.selfwalk:
            self._geom = self.probe.sample()
            self._idle_s = self._idle_fn() if self.lounge.selfwalk else 0.0

    def on_drag_start(self) -> None:
        if self.active():
            self.lounge.on_drag_start()
            self._release()

    def on_press(self) -> None:
        if self.active():
            self.lounge.poke()

    def on_drop(self) -> bool:
        if not self.lounge.enabled:
            return False
        w = self._w
        k = w.height() / puppet.CANVAS_H
        foot = (w.x() + w.width() / 2.0, w.y() + w.height() - FOOT_PAD * k)
        geom = self.probe.sample()
        top = self._w._screen_rect()[1]
        src = "window"
        if not drop_accepts(geom, foot, float(w.y()), top):
            geom = self.dock_probe.sample() if self.dock_enabled else None  # only after the window edge said no
            if not dock_drop_accepts(geom, foot, self.dock_tol):
                return False
            src = "dock"
        ok = self.lounge.on_drop(geom, foot[0])
        if ok:
            self._src = src
            self._geom = geom
            self._fx, self._fy = float(w.x()), float(w.y())
            self._timer.start()
        return ok

    # ---- per-frame ----
    def tick(self, dt: float) -> bool:
        """Advance; returns True while she is under lounge control (window skips normal wandering)."""
        lg = self.lounge
        if lg.state == "idle" and not (lg.selfwalk and lg.enabled and self._geom is not None):
            return False
        w = self._w
        pet = w._pet
        arrived = False
        fr = lg.tick(dt, self._geom, idle_s=self._idle_s)
        if fr.say:
            self.say.emit(fr.say)
        if fr.state == "idle":
            if self._was_active:
                self._was_active = False
                self._release()
            return False
        if not self._was_active:
            self._was_active = True
            self._fx, self._fy = float(w.x()), float(w.y())
        rect = w._screen_rect()
        if fr.state in ("fall", "ground"):
            self._tick_fall(dt, fr, rect)
            return True
        pet_set_fall = getattr(pet, "set_fall", None)
        if pet_set_fall is not None:
            if self._land_t < EDGE_SQ_S:
                self._land_t += dt
                sx, sy = landing_squash(self._land_t / EDGE_SQ_S, 0.12)
                pet_set_fall(0.0, sx, sy)
            elif self._land_t < 1e8:
                self._land_t = 1e9
                pet_set_fall(0.0, 1.0, 1.0)
        if fr.anchor is not None:
            anchor = clamp_anchor_to_screens(fr.anchor, [rect])
            if anchor is None:  # window is on another monitor / off screen
                anchor = fr.anchor
            tx, ty = window_target(anchor, w.width(), w.height(), rect[1])
            if fr.state == "walk_to_field":
                k = w.height() / puppet.CANVAS_H
                speed = 70.0 * k * 1.6
                dx = tx - self._fx
                step = max(-speed * dt, min(speed * dt, dx))
                self._fx += step
                self._fy += (ty - self._fy) * min(1.0, dt * 3.0)
                arrived = abs(tx - self._fx) < 6.0
                pet.drive(dt, want_walk=abs(step) > 0.05, facing=1 if dx >= 0 else -1, look=False,
                          dragging=False, ground_dx=step)
                if arrived and abs(ty - self._fy) < 6.0:
                    lg.tick(0.0, self._geom, arrived=True, idle_s=self._idle_s)
            else:
                a = min(1.0, dt * EASE)
                lim = MAX_SPEED * dt
                self._fx += max(-lim, min(lim, (tx - self._fx) * a))
                self._fy += max(-lim, min(lim, (ty - self._fy) * a))
                pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False, ground_dx=0.0)
            w.move(int(round(self._fx)), int(round(self._fy)))
        else:
            pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False, ground_dx=0.0)
        if hasattr(pet, "set_lounge"):
            if fr.state in ("walk_to_field",):
                pet.set_lounge(None)
            else:
                pet.set_lounge((fr.pose_loaf, fr.pose_droop, fr.yawn))
        return True

    def _tick_fall(self, dt: float, fr, rect) -> None:
        """Throw up -> accelerate down (ears / tail stream up) -> land on the new edge or squash on the floor."""
        w, lg = self._w, self.lounge
        pet = w._pet
        k = w.height() / puppet.CANVAS_H
        set_fall = getattr(pet, "set_fall", None)
        foot_x = w.x() + w.width() / 2.0
        if fr.state == "fall":
            if self._fall is None:
                self._fall = FallSim(self._fy, k, float(w.height()))
                self._land_t = 1e9
            sim = self._fall
            floor = rect[1] + rect[3]
            kind = sim.step(dt, self._geom, foot_x, floor)
            self._fy = sim.y
            w.move(int(round(self._fx)), int(round(self._fy)))
            pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False, ground_dx=0.0)
            if set_fall is not None:
                sx, sy = sim.stretch()
                set_fall(sim.lift(), sx, sy)
            if hasattr(pet, "set_lounge"):
                pet.set_lounge((fr.pose_loaf, fr.pose_droop, fr.yawn))
            if kind is not None:
                self._fall = None
                if kind == "edge":
                    lg.on_land("edge", self._geom, foot_x)
                    self._land_t = 0.0
                else:
                    lg.on_land("ground")
                    self._ground_t = 0.0
            return
        # floor: squash, rebound, stand up (ears / tail settle as the lift fades)
        self._ground_t += dt
        u = self._ground_t / GROUND_S
        sx, sy = landing_squash(u, GROUND_SQ_DEPTH)
        pet.drive(dt, want_walk=False, facing=1, look=False, dragging=False, ground_dx=0.0)
        if set_fall is not None:
            set_fall(max(0.0, 1.0 - self._ground_t / 0.25), sx, sy)
        if hasattr(pet, "set_lounge"):
            pet.set_lounge((fr.pose_loaf, fr.pose_droop, fr.yawn))

    def _release(self) -> None:
        self._was_active = False
        self._src = "window"
        self._fall = None
        self._land_t = 1e9
        pet = self._w._pet
        if hasattr(pet, "set_fall"):
            pet.set_fall(0.0, 1.0, 1.0)
        if hasattr(pet, "set_lounge"):
            pet.set_lounge(None)
        self._w._motion.release()
