"""Procedural motion: soft idle breath; layered walk (not whole-sprite rock)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class AnimTransform:
    """Paint transform. When ``use_layers`` is True, PetWidget draws upper/lower
    clips separately (two-layer fake walk) instead of rocking the whole sprite.
    """

    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation_deg: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    # Two-layer walk (fallback when no walk frame sequence is present)
    use_layers: bool = False
    split_frac: float = 0.58  # waist as fraction of sprite height
    upper_ox: float = 0.0
    upper_oy: float = 0.0
    upper_rot: float = 0.0
    lower_ox: float = 0.0
    lower_oy: float = 0.0


@dataclass
class ProceduralAnim:
    """Time-based transform for PetWidget.paintEvent.

    Idle: soft breath only (no rock / sway that reads as cardboard shake).
    Walk: either the caller plays ``assets/sprites/walk/*.png`` (preferred),
    or we emit ``use_layers`` offsets so upper leans/bobs while the lower half
    strides with a stronger, phase-offset vertical + horizontal slide.
    """

    t: float = 0.0
    moving: bool = False
    speed: float = 0.0  # px/s
    facing: int = 1  # 1 right, -1 left
    jump_t: float = -1.0
    jump_duration: float = 0.32
    jump_px: float = 18.0
    # When True, prefer layered offsets over whole-sprite walk rock.
    prefer_layers: bool = True
    # True when pet is already playing baked walk frames — keep breath only.
    walk_frames_active: bool = False

    # Idle breath
    breath_amp: float = 0.018
    breath_hz: float = 0.68
    # Soft idle sway (very small — not a rock)
    sway_amp_deg: float = 1.2
    sway_hz: float = 0.35
    # Layered walk tunables
    step_hz: float = 2.4
    stride_px: float = 7.0
    leg_lift_px: float = 6.5
    torso_bob_px: float = 2.2
    torso_lean_deg: float = 4.0
    split_frac: float = 0.58

    def tick(self, dt: float) -> None:
        dt = max(0.0, min(float(dt), 0.1))
        self.t += dt
        if self.jump_t >= 0.0:
            self.jump_t += dt
            if self.jump_t >= self.jump_duration:
                self.jump_t = -1.0

    def set_moving(self, moving: bool, speed: float = 0.0, facing: int = 1) -> None:
        self.moving = bool(moving)
        self.speed = max(0.0, float(speed))
        self.facing = 1 if int(facing) >= 0 else -1

    def set_walk_frames_active(self, active: bool) -> None:
        self.walk_frames_active = bool(active)

    def trigger_jump(self) -> None:
        self.jump_t = 0.0

    def jumping(self) -> bool:
        return self.jump_t >= 0.0

    def transform(self) -> AnimTransform:
        phase_b = 2.0 * math.pi * self.breath_hz * self.t
        phase_s = 2.0 * math.pi * self.sway_hz * self.t
        breath = 1.0 + self.breath_amp * math.sin(phase_b)
        breath += 0.004 * math.sin(2.0 * phase_b)
        sway = self.sway_amp_deg * math.sin(phase_s)

        scale_x = 1.0
        offset_x = 0.0
        offset_y = 0.0
        rotation = sway

        walking = self.moving and self.speed > 2.0

        # Baked walk frames already show stepping — only keep a touch of breath.
        if walking and self.walk_frames_active:
            return AnimTransform(
                scale_x=1.0,
                scale_y=1.0 + self.breath_amp * 0.35 * math.sin(phase_b),
                rotation_deg=0.0,
                offset_x=0.0,
                offset_y=self._jump_y(),
            )

        if walking and self.prefer_layers:
            intensity = min(1.0, 0.5 + self.speed / 100.0)
            step = 2.0 * math.pi * self.step_hz * self.t
            s = math.sin(step)
            c = math.cos(step)
            # Upper: lean into facing + soft bob (not whole-body rock)
            upper_rot = self.torso_lean_deg * intensity * self.facing * (0.65 + 0.35 * c)
            upper_oy = -self.torso_bob_px * intensity * abs(s)
            upper_ox = 1.2 * intensity * self.facing
            # Lower: stronger opposite-phase lift + horizontal stride slide
            # abs(sin) lift ≈ plant/push; horizontal = alternating stride
            lower_ox = self.stride_px * intensity * s * self.facing
            lower_oy = -self.leg_lift_px * intensity * max(0.0, s) + (
                1.5 * intensity * max(0.0, -s)
            )  # slight plant squash on opposite phase
            return AnimTransform(
                scale_x=1.0,
                scale_y=1.0 + self.breath_amp * 0.4 * math.sin(phase_b),
                rotation_deg=0.0,
                offset_x=0.0,
                offset_y=self._jump_y(),
                use_layers=True,
                split_frac=self.split_frac,
                upper_ox=upper_ox,
                upper_oy=upper_oy,
                upper_rot=upper_rot,
                lower_ox=lower_ox,
                lower_oy=lower_oy,
            )

        # Idle (or still): soft breath + tiny sway only — no walk bob.
        jump_y = self._jump_y()
        if self.jump_t >= 0.0:
            u = self.jump_t / self.jump_duration
            if u < 0.45:
                breath = 1.0 + 0.06 * (u / 0.45)
                scale_x = 1.0 - 0.04 * (u / 0.45)
            else:
                land = (u - 0.45) / 0.55
                breath = 1.0 - 0.05 * land
                scale_x = 1.0 + 0.08 * land
            rotation *= 0.25

        return AnimTransform(
            scale_x=scale_x,
            scale_y=breath,
            rotation_deg=rotation,
            offset_x=offset_x,
            offset_y=offset_y + jump_y,
        )

    def _jump_y(self) -> float:
        if self.jump_t < 0.0:
            return 0.0
        u = self.jump_t / self.jump_duration
        return -self.jump_px * 4.0 * u * (1.0 - u)
