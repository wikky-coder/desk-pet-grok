"""2.5D puppet widget: pre-rendered layered-rig clips (idle / turn / walk).

Same outward interface as :class:`PetWidget` so ``PetWindow`` can swap them.
Painting keeps the Source-blit + window-mask technique so transparent pixels
neither ghost nor steal clicks.
"""

from __future__ import annotations

import math

import json
import random
import time
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QBitmap, QImage, QPainter, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from desk_pet_grok import fx as fxmod, shake, eyefx, mood, loungeart, partrig, partturn, partwalk, puppet
from desk_pet_grok import pet25d_paint
from desk_pet_grok.puppet import PuppetLogic
from desk_pet_grok.springs import SKIRT, Spring
from desk_pet_grok.state import PetState

SPRITES25D = Path(__file__).resolve().parents[1] / "assets" / "sprites25d"
_MASK_PAD = 2
_MASK_CACHE_MAX = 600
_XFADE_S = 0.16  # rig<->sheet cross-fade duration
_FRAME_CACHE_BYTES = 48 * 1024 * 1024  # LRU cap for scaled frames (bible §6)
_BOW = (188.0, 288.0)  # canvas px: the point the pet "hangs" from while dragged
_FLICK_GAP_S = (6.0, 14.0)  # random gap between ear flicks (bible §3.4)
_HEM_Y0, _HEM_Y1, _HEM_Y2 = 330.0, 400.0, 412.0  # skirt sway band (canvas rows); weight 0 at the legs below the hem
_HEM_BAND = 3  # physical px per shear band


def load_manifest(root: Path | None = None) -> dict | None:
    root = Path(root) if root else SPRITES25D
    try:
        man = json.loads((root / "manifest.json").read_text())
        for name in ("idle_front", "turn_out", "walk_side"):
            if not (root / man["clips"][name]["sheet"]).is_file():
                return None
        return man
    except Exception:
        return None


def available(root: Path | None = None) -> bool:
    return load_manifest(root) is not None


VARIANT_SWITCH_S = 0.6  # duck out + pop in (no blending of two poses)
VARIANT_SINK = 0.05
VARIANT_GAP_S = (40.0, 120.0)  # a fresh uniform draw from this range after every pose change (setting ``lounge_variant_interval``)
VARIANT_GAP_LIMITS = (10.0, 900.0)
STRETCH_CYCLES = (3, 4)  # stretch is a transition pose: 3-4 full ping-pong cycles (12 frames each at 6 fps = 2 s) = 6-8 s incl. the 0.6 s fade-in
STRETCH_MIN_GAP_S = 60.0  # at least this long between the end of one stretch and the start of the next
HAPPY_IN_S = 0.2
HAPPY_OUT_S = 0.25


class Pet25D(QWidget):
    def __init__(self, parent: QWidget | None = None, *, root: Path | None = None) -> None:
        super().__init__(parent)
        self._root = Path(root) if root else SPRITES25D
        self._man = load_manifest(self._root) or {}
        clips = self._man.get("clips", {})
        self._clips = clips
        if self._man.get("stride_px_per_frame"):
            # foot-planted gait: stance-foot travel per frame comes from the sprite pack
            puppet.STRIDE_PX_PER_FRAME = float(self._man["stride_px_per_frame"])
        self.logic = PuppetLogic(
            n_walk=clips.get("walk_side", {}).get("frames", 60),
            rest_frames=self._man.get("walk_rest_frames", [0]),
        )
        self._state = PetState.idle
        self._sheets: dict[str, QImage] = {}
        self._frames: OrderedDict[tuple[str, int, int], QPixmap] = OrderedDict()
        self._frames_bytes = 0
        self._frames_h = 0
        fl = self._man.get("idle_flick")
        if fl and (self._root / fl["sheet"]).is_file():
            self._clips = dict(self._clips)
            self._clips["idle_flick"] = dict(
                fl, frames=fl["frames_per_variant"] * len(fl["variants"]), loop=False)
        self._flick_at = time.monotonic() + random.uniform(*_FLICK_GAP_S)
        self._flick_var: int | None = None
        self._last_idle_idx = -1
        self._rig: partrig.PartRig | None = None
        self._lounge: tuple[float, float, float] | None = None
        self._lounge_art: loungeart.LoungeArt | None = None
        self._wrig: partwalk.WalkRig | None = None
        self._trig: partturn.TurnRig | None = None
        self._turn_on = False
        self._fam: str | None = None
        self._xf_t0: float | None = None
        self._xf_snap: QImage | None = None
        self._rig_on = False
        self._skirt = Spring(*SKIRT)
        self._pat_on = False  # head-pat reaction target / eased amount
        self._pat = 0.0
        self._tail_boost = True  # F8: natural, more visible tail swing (all poses)
        self._var_on = False  # F7 feature flag: lying-pose variants (side / chin / stretch / curl)
        self._var_arts: dict[str, loungeart.LoungeArt | None] = {}
        self._var_from = self._var_to = "base"
        self._var_t = 1.0
        self._var_prev = "base"  # the pose to return to when she wakes from curl-sleep
        self._var_clock = 0.0
        self._var_next = 0.0
        self._stretch_end = -1e9
        self._stretch_cycles = 3
        self._var_rng = random.Random()
        self._var_gap = VARIANT_GAP_S
        self._anger = 0  # v4-2: shake-anger stage (0..5); drives the face, the effects and the back-turned sulk sprite
        self._anger_fx = fxmod.AngerFx()
        self._sulk_t = 0.0  # 0..1 crossfade to the back-turned sprite
        self._sulk_img = None
        self._holiday = None  # v4-4: festival key (decorations) / None
        self._hol_a = 0.0
        self._hol_ok = False
        self._hol_art = None
        self._greet_fx = fxmod.GreetFx()
        self._expr = None  # (face, seconds left, face to go back to)
        self._work_mode = None  # v4-6: prop next to her (read / code / terminal / draw)
        self._work_shown = None
        self._work_t = 0.0
        self._work_clock = 0.0
        self._work_art = None
        self._cling_side = 0  # v4-3: -1 / +1 = clinging to that screen border (sprites, not the rig)
        self._cling_peek = False
        self._cling_t = 0.0
        self._peek_t = 0.0
        self._cling_art = None
        self._mood_on = False  # F6 feature flag (window: setting 'mood')
        self._mood_from, self._mood_to, self._mood_t = "calm", "calm", 1.0
        self._happy = 0.0  # 'enjoying it' face layer opacity (fade in 0.2 s, out 0.25 s)
        self._gaze_on = True  # eyes follow the mouse (passive)
        self._gaze_t = (0.0, 0.0)
        self._gaze = (0.0, 0.0)
        self._gaze_painted = (0.0, 0.0)
        self._lift = 0.0  # fall: airborne amount 0..1 (eased toward _lift_t)
        self._lift_t = 0.0
        self._fall_sq = (1.0, 1.0)  # fall squash/stretch (sx, sy) about the feet
        self._prev_vx = 0.0
        self._hem_dx = 0.0
        self._t0 = time.monotonic()
        self._buf: QImage | None = None
        self._mask_cache: dict[tuple, QRegion] = {}
        self._mask_key: tuple | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setMinimumSize(80, 100)

    # ---- compat surface ----
    @property
    def state(self) -> PetState:
        return self._state

    def set_state(self, state: PetState) -> None:
        self._state = state
        self.logic.wake()
        self.update()

    def set_facing(self, facing: int) -> None:
        self.logic.want_facing = 1 if facing >= 0 else -1

    def set_motion(self, moving: bool, speed: float = 0.0) -> None:  # compat no-op
        pass

    def play_jump(self) -> None:
        self.logic.hop()
        self.update()

    def wake(self) -> None:
        self.logic.wake()

    def hit(self, p: QPoint) -> bool:
        """True when ``p`` (widget coords) lands on (or next to) the character."""
        buf = self._buf
        if buf is None:
            return False
        d = buf.devicePixelRatio()
        px, py, pad = int(p.x() * d), int(p.y() * d), int(_MASK_PAD * d)
        for yy in range(max(0, py - pad), min(buf.height(), py + pad + 1)):
            for xx in range(max(0, px - pad), min(buf.width(), px + pad + 1)):
                if (buf.pixel(xx, yy) >> 24) & 0xFF > 12:
                    return True
        return False

    # ---- driving ----
    def drive(
        self,
        dt: float,
        *,
        want_walk: bool,
        facing: int,
        look: bool,
        dragging: bool,
        drag_vx: float = 0.0,
        ground_dx: float = 0.0,
    ) -> None:
        lg = self.logic
        was_frozen = lg.s.frozen
        if dragging != lg.dragging:
            lg.set_dragging(dragging, drag_vx)
        elif dragging:
            lg.drag_vx = drag_vx
        lg.want_facing = 1 if facing >= 0 else -1
        lg.set_look(look) if look != lg.look else None
        lg.set_walk(want_walk, facing)
        if self._state is PetState.sleep and not want_walk and not dragging:
            # sleeping: hold the first idle frame, do not repaint
            lg.s.frozen = True
        lg.phase_ok = self._idle_phase_ok()
        lg.tick(dt, ground_dx, self.height())
        self._step_secondary(dt, ground_dx, dragging, drag_vx)
        if not lg.s.frozen or was_frozen != lg.s.frozen or self.secondary_active():
            self.update()

    def _step_secondary(self, dt: float, ground_dx: float, dragging: bool, drag_vx: float) -> None:
        """Skirt-hem spring driven by window acceleration (screen px/s^2 -> canvas px/s^2)."""
        dt = max(1e-3, min(dt, 0.1))
        vx = drag_vx if dragging else ground_dx / dt
        k = max(1e-3, self.height() / puppet.CANVAS_H)
        a = (vx - self._prev_vx) / dt / k
        self._prev_vx = vx
        self._hem_dx = self._skirt.step(dt, a)
        self._ease_fx(dt)
        if self._lounge_art is not None and self._lounge is not None:
            self._var_tick(dt)
            for art, _m, _s in (self._active_arts() or [(self._lounge_art, 1.0, 0.0)]):
                art.pat = self._pat
                art.step(dt)
        if self._rig is not None and (self._rig_on or self._lounge is not None or self._pat > 0.01 or self._lift > 0.01
                                      or self._work_t > 0.001 or self._work_mode is not None):
            self._rig.pat, self._rig.lift = self._pat, self._lift
            self._rig.happy = self._happy
            m = -1.0 if self.logic.mirror() else 1.0  # painter mirrors the sprite: keep lag on the correct side
            self._rig.tail_boost = self._tail_boost
            self._rig.step(dt, a * m, allow_flick=self._state is PetState.idle and self.logic.s.clip() == 'idle')
            if self._wrig is not None:
                walking = self.logic.s.clip() == "walk"
                self._wrig.tail_boost = self._tail_boost
                self._wrig.step(dt, a * m, int(self.logic.s.walk_pos) if walking else None, walking, abs(vx) / k)

    # ---- head pat / gaze / fall (eye + rig effects) ----
    def _ease_fx(self, dt: float) -> None:
        tgt = 1.0 if self._pat_on else 0.0
        rate = 5.0 if tgt > self._pat else 2.5
        self._pat += max(-rate * dt, min(rate * dt, tgt - self._pat))
        if self._mood_t < 1.0:
            self._mood_t = mood.fade_step(self._mood_t, dt)
        self._anger_fx.step(dt)
        self._greet_fx.step(dt)
        if self._expr is not None:
            face, left, back = self._expr
            left -= dt
            if left <= 0:
                self._expr = None
                if not self._anger:
                    self._apply_face(back)
            else:
                self._expr = (face, left, back)
        ht = 1.0 if (self._holiday and self._hol_ok) else 0.0
        self._hol_a += max(-3.0 * dt, min(3.0 * dt, ht - self._hol_a))
        wt = 1.0 if self._work_mode else 0.0
        self._work_t += max(-2.8 * dt, min(2.8 * dt, wt - self._work_t))
        self._work_clock += dt
        if self._rig is not None:
            ws = self._work_mode or self._work_shown
            self._rig.set_work_body(ws, self._work_t * self._work_t * (3 - 2 * self._work_t) if self._rig.has_work_body(ws) else 0.0)
        if self._work_mode:
            self._work_shown = self._work_mode
        elif self._work_t <= 0.001:
            self._work_shown = None
        ct = 1.0 if self._cling_side else 0.0
        self._cling_t += max(-4.0 * dt, min(4.0 * dt, ct - self._cling_t))
        pt = 1.0 if (self._cling_side and self._cling_peek) else 0.0
        self._peek_t += max(-6.0 * dt, min(6.0 * dt, pt - self._peek_t))
        st = 1.0 if self._anger == 5 else 0.0
        self._sulk_t += max(-2.5 * dt, min(2.5 * dt, st - self._sulk_t))
        if self._rig is not None:
            self._rig.mood_mix = (self._mood_from, self._mood_to, self._mood_t)
        h_tgt = 1.0 if (self._pat_on and self._lounge is None and self._rig is not None and self._rig.has_happy_face()) else 0.0
        h_rate = (1.0 / HAPPY_IN_S if h_tgt > self._happy else 1.0 / HAPPY_OUT_S) * dt
        self._happy += max(-h_rate, min(h_rate, h_tgt - self._happy))
        lr = (10.0 if self._lift_t > self._lift else 4.5) * dt
        self._lift += max(-lr, min(lr, self._lift_t - self._lift))
        a = min(1.0, dt * 14.0)
        gx, gy = self._gaze
        self._gaze = (gx + (self._gaze_t[0] - gx) * a, gy + (self._gaze_t[1] - gy) * a)

    # ---- F8 tail swing boost ----
    def set_tail_boost(self, on: bool) -> None:
        self._tail_boost = bool(on)
        for r in (self._rig, self._wrig):
            if r is not None:
                r.tail_boost = bool(on)
        for a in [self._lounge_art, *self._var_arts.values()]:
            if a is not None:
                a.tail_on = bool(on)
        self.update()

    def tail_boost(self) -> bool:
        return self._tail_boost

    # ---- F7 lying-pose variants ----
    def set_lounge_variants(self, on: bool) -> None:
        self._var_on = bool(on)
        if not on:
            self._var_from = self._var_to = "base"
            self._var_t = 1.0
        self.update()

    def lounge_variant(self) -> str:
        return self._var_to

    def _art_for(self, name: str):
        if name == "base":
            return self._lounge_art
        if name not in self._var_arts:
            try:
                self._var_arts[name] = loungeart.LoungeArt(loungeart.VARIANT_DIR / name)
                self._var_arts[name].tail_on = self._tail_boost
            except Exception:  # missing / broken assets: that variant is simply not used
                self._var_arts[name] = None
        return self._var_arts[name]

    def set_variant_interval(self, lo=None, hi=None) -> tuple[float, float]:
        """Seconds range for the next pose change (each change re-draws uniformly inside it); bad / missing values -> the default."""
        a, b = VARIANT_GAP_LIMITS
        try:
            lo_f, hi_f = float(lo), float(hi)
            if not (math.isfinite(lo_f) and math.isfinite(hi_f)):
                raise ValueError
        except (TypeError, ValueError):
            lo_f, hi_f = VARIANT_GAP_S
        lo_f = min(b, max(a, lo_f))
        hi_f = min(b, max(lo_f, hi_f))
        self._var_gap = (lo_f, hi_f)
        return self._var_gap

    def variant_interval(self) -> tuple[float, float]:
        return self._var_gap

    def _var_gap_draw(self) -> float:
        return self._var_rng.uniform(*self._var_gap)

    def _var_options(self, initial: bool = False) -> list[str]:
        """Poses she may pick; stretch is a transition pose: never the first pose, and not within STRETCH_MIN_GAP_S of the last one."""
        out = ["base"] + [n for n in loungeart.variant_names() if n not in ("curl", "stretch") and self._art_for(n) is not None]
        if not initial and "stretch" in loungeart.variant_names() and self._art_for("stretch") is not None \
                and self._var_clock - self._stretch_end >= STRETCH_MIN_GAP_S:
            out.append("stretch")
        return out

    def _stable_options(self, avoid: str) -> list[str]:
        opts = [n for n in self._var_options(initial=True) if n != avoid]
        return opts or ["base"]

    def _var_start(self, to: str, instant: bool = False) -> None:
        if to != "base" and self._art_for(to) is None:
            to = "base"
        if to == self._var_to:
            return
        if self._var_to not in ("curl", "stretch"):
            self._var_prev = self._var_to
        if self._var_to == "stretch":
            self._stretch_end = self._var_clock
        if to == "stretch":
            self._stretch_cycles = self._var_rng.choice(STRETCH_CYCLES)
            art = self._art_for("stretch")
            if art is not None:
                art.phase = 0.0  # start at the beginning of a full stretch cycle
        self._var_from, self._var_to = self._var_to, to
        self._var_t = 1.0 if instant else 0.0
        self._var_next = self._var_clock + self._var_gap_draw()

    def _var_tick(self, dt: float) -> None:
        if not self._var_on or self._lounge is None or self._lounge_art is None:
            return
        self._var_clock += dt
        if self._var_t < 1.0:
            self._var_t = min(1.0, self._var_t + dt / VARIANT_SWITCH_S)
            return
        loaf, droop, yawn = self._lounge
        if droop > 0.85 and self._pat < 0.05 and not self._pat_on and self._art_for("curl") is not None:  # fell asleep (a pat closes her eyes too: not that): curl up
            self._var_start("curl")
        elif self._var_to == "stretch":
            art = self._art_for("stretch")
            petted = self._pat >= 0.05 or self._pat_on
            done = art is None or art.phase >= 12.0 * self._stretch_cycles  # end on a cycle boundary, never mid-stretch
            if petted or done or yawn >= 0.05:
                self._var_start(self._var_rng.choice(self._stable_options(self._var_prev)))
        elif self._var_to == "curl" and droop < 0.4:  # woken: back to the pose she had
            self._var_start(self._var_prev if self._var_prev != "curl" else "base")
        elif (self._var_clock >= self._var_next and self._var_to != "curl" and self._pat < 0.05 and droop < 0.05
              and yawn < 0.05 and loaf > 0.95):
            opts = [n for n in self._var_options() if n != self._var_to]  # (stretch only when its gap is over)
            if opts:
                self._var_start(self._var_rng.choice(opts))
            else:
                self._var_next = self._var_clock + self._var_gap_draw()

    def _active_arts(self) -> list:
        """[(art, opacity multiplier, sink)] of the lying art(s) to draw: the base art, or a variant (ducking out / popping in)."""
        base = self._lounge_art
        if not self._var_on or base is None:
            return [(base, 1.0, 0.0)] if base is not None else []
        to_art = self._art_for(self._var_to) or base
        if self._var_t >= 1.0:
            return [(to_art, 1.0, 0.0)]
        from_art = self._art_for(self._var_from) or base
        if self._var_t < 0.5:
            u = loungeart._smooth(self._var_t * 2.0)
            return [(from_art, 1.0 - u, VARIANT_SINK * u)]
        u = loungeart._smooth((self._var_t - 0.5) * 2.0)
        return [(to_art, u, VARIANT_SINK * (1.0 - u))]

    def _main_art(self):
        arts = self._active_arts()
        return arts[0][0] if arts else None

    # ---- F6 mood faces ----
    def set_mood_enabled(self, on: bool) -> None:
        self._mood_on = bool(on)
        if not on and not self._anger:
            self._mood_from = self._mood_to = "calm"
            self._mood_t = 1.0
            if self._rig is not None:
                self._rig.mood_mix = ("calm", "calm", 1.0)
        self.update()

    def set_anger(self, stage: int) -> None:
        """v4-2: 0 calm .. 4 fuming, 5 sulking (back turned). Works without the F6 mood switch."""
        stage = max(0, min(5, int(stage)))
        if stage == self._anger:
            return
        self._anger = stage
        self._anger_fx.set_stage(stage)
        self._apply_face(shake.FACE[stage] or "calm")
        self.update()

    def anger(self) -> int:
        return self._anger

    def set_mood(self, mood: str) -> None:
        """Cross-fade (mood.FADE_S) to the face of `mood`; moods without art, or the flag off, show the calm base head."""
        if not self._mood_on or self._anger or self._expr is not None:
            return
        self._apply_face(mood)

    def _apply_face(self, mood: str) -> None:
        if mood != "calm":
            self._ensure_rig()
            if self._rig is None or not self._rig.has_mood_face(mood):
                mood = "calm"
        if mood == self._mood_to:
            return
        shown = self._mood_to if self._mood_t >= 0.5 else self._mood_from  # mid-fade: start from the dominant face
        self._mood_from, self._mood_to, self._mood_t = shown, mood, 0.0
        self.update()

    def mood(self) -> str:
        return self._mood_to

    def mood_visible(self) -> bool:
        return (self._mood_on or self._anger > 0 or self._expr is not None or self._mood_t < 1.0) and (self._mood_to != "calm" or (self._mood_t < 1.0 and self._mood_from != "calm"))

    def _ensure_rig(self) -> bool:
        if self._rig is None and partrig.available():
            try:
                self._rig = partrig.PartRig()
            except Exception:
                self._rig = None
        return self._rig is not None

    def set_petting(self, on: bool) -> None:
        """Head-pat reaction: eyes squint, ears down, tail wags, head sinks (needs the part rig; falls back to eyes + press)."""
        on = bool(on)
        if on and not self._pat_on:
            self._ensure_rig()
            self.logic.wake()
            if self._lounge_art is not None and self._lounge is not None:
                (self._main_art() or self._lounge_art).start_flick()
        self._pat_on = on
        self.update()

    def petting(self) -> bool:
        return self._pat_on or self._pat > 0.01

    def pat_amount(self) -> float:
        return self._pat

    def set_gaze_enabled(self, on: bool) -> None:
        self._gaze_on = bool(on)
        if not on:
            self._gaze_t = (0.0, 0.0)

    def set_gaze(self, gx: float, gy: float) -> None:
        """Target iris offset -1..1 (screen space, toward the cursor). Eyes only; head and body never turn."""
        if not self._gaze_on:
            gx = gy = 0.0
        self._gaze_t = (max(-1.0, min(1.0, gx)), max(-1.0, min(1.0, gy)))

    def gaze(self) -> tuple[float, float]:
        return self._gaze

    def set_fall(self, lift: float, sx: float = 1.0, sy: float = 1.0) -> None:
        """Fall pose: ``lift`` 0..1 streams ears/ahoge/tail up and widens the eyes; (sx, sy) squash/stretch about the feet."""
        lift = max(0.0, min(1.0, lift))
        if lift > 0.01 and self._lift <= 0.01:
            self._ensure_rig()
        self._lift_t = lift
        self._fall_sq = (sx, sy)
        self.update()

    def falling(self) -> bool:
        return self._lift > 0.01 or self._fall_sq != (1.0, 1.0)

    def _fx_active(self) -> bool:
        gx, gy = self._gaze
        px, py = self._gaze_painted
        return (self._anger > 0 or self._greet_fx.active() or self._expr is not None or self._hol_a > 0.001 or self._holiday is not None
                or self._sulk_t > 0.001 or self._work_t > 0.001 or self._work_mode is not None or self._cling_side != 0 or self._cling_t > 0.001
                or self._anger_fx.active()
                or self._pat_on or self._pat > 0.001 or self._happy > 0.001 or self._mood_t < 1.0 or self.falling()
                or abs(gx - px) > 0.015 or abs(gy - py) > 0.015)

    def _extra_rig(self) -> bool:
        return (self._pat > 0.01 or self._lift > 0.01 or self.mood_visible() or self._work_t > 0.001 or self._work_mode is not None) \
            and self._rig is not None and self._state is not PetState.sleep

    # ---- part rig (feature flag, default off) ----
    def set_part_rig(self, enabled: bool) -> bool:
        """Toggle the live part rig for the idle pose. Returns the effective state."""
        if enabled and self._rig is None and partrig.available():
            try:
                self._rig = partrig.PartRig()
            except Exception:  # broken assets: stay on the sheets
                self._rig = None
        if enabled and self._wrig is None and partwalk.available():
            try:
                self._wrig = partwalk.WalkRig()
            except Exception:
                self._wrig = None
        self._rig_on = bool(enabled and self._rig is not None)
        self.logic.wake()
        self.update()
        return self._rig_on

    def set_lounge(self, pose: tuple[float, float, float] | None) -> None:
        """Lounge pose (loaf, droop, yawn) drawn by the part rig; None = normal behaviour. Loads the rig on demand."""
        if pose is not None and self._rig is None and partrig.available():
            try:
                self._rig = partrig.PartRig()
            except Exception:
                self._rig = None
        if pose is not None and self._rig is None:
            pose = None
        if pose is not None and self._lounge_art is None and loungeart.available():
            try:
                self._lounge_art = loungeart.LoungeArt()
                self._lounge_art.tail_on = self._tail_boost
            except Exception:  # broken assets: keep the squashed-loaf fallback
                self._lounge_art = None
        entering = pose is not None and self._lounge is None
        self._lounge = pose
        if entering and self._var_on and self._lounge_art is not None:
            opts = self._var_options(initial=True)  # a fresh pose each time she lies down (the art is still invisible at loaf ~0)
            if len(opts) > 1:
                self._var_start(self._var_rng.choice(opts), instant=True)
            self._var_t = 1.0
        if pose is not None and self._lounge_art is not None:
            for art, _m, _s in self._active_arts():
                art.set_pose(*pose)
            self._lounge_art.set_pose(*pose)
        if self._rig is not None:
            self._rig.set_pose(*(pose or (0.0, 0.0, 0.0)))
        self.update()

    def lounge_head_zone(self, w: float, h: float):
        """Head-pat zone (window-local) of the lying pose, or None unless she is fully lying with the art loaded."""
        if self._lounge is None or self._lounge_art is None or self._lounge[0] < 0.85:
            return None
        art = self._main_art() or self._lounge_art
        return loungeart.head_zone(w, h, art.fw, art.fh, art.canvas[1], zone=art.head_zone_frame, off=art.base_off)

    def lounging(self) -> bool:
        return self._lounge is not None

    def set_part_turn(self, enabled: bool) -> bool:
        if enabled and self._trig is None and partturn.available():
            try:
                self._trig = partturn.TurnRig()
            except Exception:
                self._trig = None
        self._turn_on = bool(enabled and self._trig is not None)
        return self._turn_on

    def part_turn_on(self) -> bool:
        return self._turn_on

    def part_rig_on(self) -> bool:
        return self._rig_on

    def _rig_drawing(self) -> bool:
        lg = self.logic
        if self._lounge is not None and self._rig is not None and lg.s.clip() == "idle":
            return True
        if self._extra_rig() and lg.s.clip() == "idle":
            return True
        return (self._rig_on and self._rig is not None and lg.s.clip() == "idle"
                and self._state is not PetState.sleep)

    def _walk_rig_drawing(self) -> bool:
        return self._rig_on and self._wrig is not None and self.logic.s.clip() == "walk"

    def secondary_active(self) -> bool:
        if self._xf_t0 is not None:
            return True
        return (self._rig_drawing() or self._walk_rig_drawing() or abs(self._hem_dx) > 0.05 or not self._skirt.at_rest(0.05)
                or self._fx_active())

    # ---- frames ----
    def _sheet(self, clip: str) -> QImage:
        img = self._sheets.get(clip)
        if img is None:
            img = QImage(str(self._root / self._clips[clip]["sheet"]))
            img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            self._sheets[clip] = img
        return img

    def _frame(self, clip: str, idx: int) -> QPixmap:
        ph = max(1, int(self.height() * self.devicePixelRatioF()))
        if ph != self._frames_h:
            self._frames.clear()
            self._frames_bytes = 0
            self._frames_h = ph
        key = (clip, idx, ph)
        pm = self._frames.get(key)
        if pm is not None:
            self._frames.move_to_end(key)
            return pm
        c = self._clips[clip]
        fw, fh = c["fw"], c["fh"]
        r, col = divmod(idx, c["cols"])
        crop = self._sheet(clip).copy(col * fw, r * fh, fw, fh)
        sc = crop.scaledToHeight(ph, Qt.TransformationMode.SmoothTransformation)
        pm = QPixmap.fromImage(sc)
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        self._frames[key] = pm
        self._frames_bytes += sc.width() * sc.height() * 4
        while self._frames_bytes > _FRAME_CACHE_BYTES and len(self._frames) > 1:
            _k, old = self._frames.popitem(last=False)
            self._frames_bytes -= int(old.width() * old.height() * 4)  # (device px)
        return pm

    def _idle_idx(self) -> int:
        c = self._clips["idle_front"]
        return int((time.monotonic() - self._t0) * c["fps"]) % c["frames"]

    def _idle_phase_ok(self) -> bool:
        if self._rig_drawing():
            return self._rig.at_rest()
        ok = self._man.get("idle_turn_ok")
        return True if not ok else self._idle_idx() in ok

    def current_frame_key(self) -> tuple[str, int]:
        lg = self.logic
        kind = lg.s.clip()
        if self._rig_drawing() and not lg.s.frozen:
            return "rig", 0
        if kind != "idle":
            self._flick_var = None
        if kind == "turn" and self._rig_on and self._turn_on and self._trig is not None:
            return "rigt", int(round(max(0.0, min(1.0, lg.s.tp)) * 60))
        if kind == "turn":
            return "turn_out", lg.turn_frame(self._clips["turn_out"]["frames"])
        if kind == "walk" and self._rig_on and self._wrig is not None:
            return "rigw", int(lg.s.walk_pos) % self._wrig.n
        if kind == "walk":
            return "walk_side", int(lg.s.walk_pos) % self._clips["walk_side"]["frames"]
        if lg.s.frozen or self._state is PetState.sleep:
            return "idle_front", 0
        idx = self._idle_idx()
        n_fl = self._man.get("idle_flick", {}).get("frames_per_variant", 0)
        if "idle_flick" in self._clips and n_fl:
            now = time.monotonic()
            if self._flick_var is None and idx == 0 and self._last_idle_idx not in (0, -1) \
                    and now >= self._flick_at and self._state is PetState.idle:
                self._flick_var = random.choices((0, 1, 2), weights=(38, 37, 25))[0]  # L / R / both
            if self._flick_var is not None:
                if idx < n_fl:
                    self._last_idle_idx = idx
                    return "idle_flick", self._flick_var * n_fl + idx
                self._flick_var = None
                self._flick_at = now + random.uniform(*_FLICK_GAP_S)
        self._last_idle_idx = idx
        return "idle_front", idx

    def _sway(self, pm: QPixmap, dx_canvas: float) -> QPixmap:
        """Shear the skirt-hem band sideways by dx (bible §3.14: runtime, responds to motion)."""
        img = pm.toImage()
        dpr = pm.devicePixelRatio()
        img.setDevicePixelRatio(1.0)
        H, W = img.height(), img.width()
        kpx = H / puppet.CANVAS_H
        y0, y1, y2 = _HEM_Y0 * kpx, _HEM_Y1 * kpx, _HEM_Y2 * kpx
        out = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(0)
        q = QPainter(out)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        top = int(y0)
        q.drawImage(QPointF(0, 0), img, QRectF(0, 0, W, top))
        y = top
        while y < H:
            bh = min(_HEM_BAND, H - y)
            m = y + bh / 2.0
            if m < y1:
                u = (m - y0) / (y1 - y0)
                w = u * u * (3 - 2 * u)
            else:
                u = min(1.0, max(0.0, (m - y1) / (y2 - y1)))
                w = 1.0 - u * u * (3 - 2 * u)
            q.drawImage(QPointF(dx_canvas * kpx * max(0.0, w), y), img, QRectF(0, y, W, bh))
            y += bh
        q.end()
        res = QPixmap.fromImage(out)
        res.setDevicePixelRatio(dpr)
        return res

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0 or not self._clips:
            return
        dpr = self.devicePixelRatioF()
        buf = QImage(int(w * dpr), int(h * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        buf.setDevicePixelRatio(dpr)
        buf.fill(0)
        art = self._lounge_art if self._lounge is not None else None
        if art is not None:
            self._paint_lounge_art(buf, w, h, dpr, art)
            return
        clip, idx = self.current_frame_key()
        lg = self.logic
        pm = None if clip in ("rig", "rigw", "rigt") else self._frame(clip, idx)
        if pm is not None and abs(self._hem_dx) > 0.08 and clip != "turn_out":
            pm = self._sway(pm, self._hem_dx * (-1.0 if lg.mirror() else 1.0))
        hop_y, hop_sx, squash = lg.hop_pose()
        k = h / puppet.CANVAS_H
        p = QPainter(buf)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # pivot at the feet (bottom centre of the window canvas)
        foot_y = puppet.CANVAS_H * k - 12 * k
        p.translate(w / 2.0, foot_y + hop_y * k)
        loaf = self._lounge[0] if self._lounge is not None else 0.0
        press = 0.0 if self._rig_drawing() else self._pat  # no rig: press the whole body down a little
        p.scale(hop_sx * (1.0 + 0.10 * loaf) * self._fall_sq[0], squash * (1.0 - 0.34 * loaf - 0.035 * press) * self._fall_sq[1])
        # tilt about the grab point (bow) while dragged; identity when lean == 0
        bx, by = w / 2.0 + (_BOW[0] - puppet.CANVAS_W / 2.0) * k, _BOW[1] * k - foot_y
        p.translate(bx - w / 2.0, by)
        p.rotate(lg.s.lean)
        p.translate(-(bx - w / 2.0), -by)
        p.scale(-1.0 if lg.mirror() else 1.0, 1.0)
        p.translate(-w / 2.0, -foot_y)
        world = p.worldTransform()
        if self._sulk_t > 0.001 or self._cling_t > 0.001:
            p.setOpacity(max(0.0, 1.0 - max(self._sulk_t, self._cling_t)))  # crossfade to the back-turned sprite (drawn below, over the figure)
        if clip == "rigt":
            self._trig.paint(p, w, h, dpr, idx / 60.0, self._rig.head.x if self._rig else 0.0)
        elif clip == "rigw":
            self._wrig.paint(p, w, h, dpr, idx)
        elif pm is None:
            self._rig.paint(p, w, h, dpr)
        else:
            p.drawPixmap(QRect(0, 0, w, h), pm)
        p.end()
        self._hol_ok = clip == "rig" and self._cling_t < 0.01 and self._sulk_t < 0.05 and not self._anger
        if (self._sulk_t > 0.001 or self._cling_t > 0.001 or self._work_t > 0.001 or self._anger_fx.active() or self._hol_a > 0.001
                or self._greet_fx.active()):
            q = QPainter(buf)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if self._sulk_t > 0.001:
                self._paint_sulk(q, world, k, w, h)
            if self._cling_t > 0.001:
                self._paint_cling(q, k)
            elif self._work_t > 0.001 and self._work_shown and self._sulk_t < 0.05:
                self._paint_work(q, k)
            if self._hol_a > 0.001 and self._holiday:
                self._paint_holiday(q, world, k)
            self._anger_fx.paint(q, world, k, dpr, self)
            self._greet_fx.paint(q, world, k, dpr, self)
            q.end()
        if clip in ("rig", "idle_front", "idle_flick") and self._state is not PetState.sleep and self._happy < 0.02 and not self.mood_visible() and self._sulk_t < 0.001 and self._cling_t < 0.001:
            eyes = (tuple(self._rig.head_point(*e) for e in eyefx.EYES) if clip == "rig" and self._rig is not None
                    else eyefx.EYES)
            eyefx.apply(buf, world, k, dpr, gaze=self._gaze, squint=self._pat, wide=self._lift, eyes=eyes)
            self._gaze_painted = self._gaze
        self._present(buf, clip, (clip, idx, lg.mirror(), round(lg.s.lean), round(hop_y), round(self._hem_dx * 2), round(hop_sx * 50), round(loaf * 20), round(self._pat * 8), round(self._happy * 20), self._mood_to, round(self._mood_t * 20), round(self._lift * 8), round(self._fall_sq[0] * 40), round(self._fall_sq[1] * 40), (self._wrig.state_key() if clip == 'rigw' else self._rig.state_key()) if pm is None else 0, w, h), dpr)

    # ---- v4-4 festival decorations / greetings ----
    def set_holiday(self, key) -> None:
        from desk_pet_grok import holidays

        key = key if key in holidays.FESTIVALS else None
        if key != self._holiday:
            self._holiday = key
            self.update()

    def holiday(self):
        return self._holiday

    def greet(self, kind: str, face: str | None = None, hold: float = 4.4) -> None:
        """Small greeting effect: an icon beside her head and (optionally) a face for ``hold`` seconds."""
        self._greet_fx.start(kind)
        if face and not self._anger and self._expr is None:
            self._ensure_rig()
            if self._rig is not None and self._rig.has_mood_face(face):
                back = self._mood_to
                self._expr = (face, hold, back)
                self._apply_face(face)
        self.update()

    def _hol_images(self):
        if self._hol_art is None:
            self._hol_art = {}
            root = Path(__file__).resolve().parent.parent / "assets" / "festival25d"
            for f in root.glob("*.png"):
                im = QImage(str(f))
                if not im.isNull():
                    self._hol_art[f.stem] = im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        return self._hol_art

    def _paint_holiday(self, q: QPainter, world, k: float) -> None:
        pet25d_paint.paint_holiday(self, q, world, k)

    def set_work(self, mode) -> None:
        mode = mode if mode in ("read", "code", "terminal", "draw") else None
        if mode == self._work_mode:
            return
        self._work_mode = mode
        if mode:
            self._ensure_rig()  # classic (non-rig) rendering switches to the rig's idle pose while a prop is out
            self._work_shown = mode
            self._work_clock = 0.0
        self.update()

    def work_mode(self):
        return self._work_mode

    def _work_art_load(self):
        if self._work_art is None:
            self._work_art = False
            root = Path(__file__).resolve().parent.parent / "assets" / "work25d"
            try:
                meta = json.loads((root / "work.json").read_text())
                props = {}
                for n, pm in meta["props"].items():
                    im = QImage(str(root / f"{n}.png"))
                    if im.isNull():
                        raise OSError(n)
                    props[n] = (im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied), pm["box"], pm["pivot"])
                self._work_art = props
            except (OSError, ValueError, KeyError):
                pass
        return self._work_art or None

    def _paint_work(self, q: QPainter, k: float) -> None:
        pet25d_paint.paint_work(self, q, k)

    def set_cling(self, side: int, peek: bool = False) -> None:
        side = -1 if side < 0 else (1 if side > 0 else 0)
        if side and self._cling_art_load() is None:
            side = 0
        if (side, bool(peek)) == (self._cling_side, self._cling_peek):
            return
        self._cling_side, self._cling_peek = side, bool(peek) and bool(side)
        self.update()

    def cling_side(self) -> int:
        return self._cling_side

    def cling_cut_x(self, h: float) -> float | None:
        """x (window px) of the sprite's cut edge; the window must sit with it exactly on the screen border."""
        art = self._cling_art_load()
        if art is None or not self._cling_side:
            return None
        k = h / puppet.CANVAS_H
        return art["cut2"] / 2.0 * k if self._cling_side < 0 else (puppet.CANVAS_W - art["cut2"] / 2.0) * k

    def _cling_art_load(self):
        if self._cling_art is None:
            self._cling_art = False
            root = Path(__file__).resolve().parent.parent / "assets" / "cling25d"
            try:
                meta = json.loads((root / "cling.json").read_text())
                frames = {}
                for n, fm in meta["frames"].items():
                    im = QImage(str(root / f"{n}.png"))
                    if im.isNull():
                        raise OSError(n)
                    frames[n] = (im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied), fm["box"])
                self._cling_art = {"cut2": meta["cut2"], "frames": frames}
            except (OSError, ValueError, KeyError):
                pass
        return self._cling_art or None

    def _paint_cling(self, q: QPainter, k: float) -> None:
        pet25d_paint.paint_cling(self, q, k)

    def _sulk_sprite(self):
        if self._sulk_img is None:
            self._sulk_img = False
            root = Path(__file__).resolve().parent.parent / "assets" / "shake25d"
            try:
                meta = json.loads((root / "sulk.json").read_text())
                im = QImage(str(root / "sulk_back.png"))
                if not im.isNull():
                    self._sulk_img = (im.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied), meta["box"])
            except (OSError, ValueError, KeyError):
                pass
        return self._sulk_img or None

    def _paint_sulk(self, q: QPainter, world, k: float, w: int, h: int) -> None:
        pet25d_paint.paint_sulk(self, q, world, k, w, h)

    def _paint_lounge_art(self, buf: QImage, w: int, h: int, dpr: float, art) -> None:
        pet25d_paint.paint_lounge_art(self, buf, w, h, dpr, art)

    def _present(self, buf: QImage, clip: str, key: tuple, dpr: float) -> None:
        # rig <-> sheet hand-off: short premultiplied cross-fade so the two renderers never show a seam
        fam = "rig" if clip in ("rig", "rigw", "rigt", "lounge") else "sheet"
        now = time.monotonic()
        if self._fam is not None and fam != self._fam and getattr(self, "_buf", None) is not None:
            self._xf_snap, self._xf_t0 = self._buf, now
        self._fam = fam
        if self._xf_t0 is not None and self._xf_snap is not None:
            wgt = (now - self._xf_t0) / _XFADE_S
            if wgt >= 1.0 or self._xf_snap.size() != buf.size():
                self._xf_t0 = self._xf_snap = None
            else:
                mix = QImage(buf.size(), QImage.Format.Format_ARGB32_Premultiplied)
                mix.setDevicePixelRatio(dpr)
                mix.fill(0)
                q = QPainter(mix)
                q.drawImage(0, 0, self._xf_snap)
                q.setOpacity(max(0.0, wgt))
                q.drawImage(0, 0, buf)
                q.end()
                buf = mix
        self._buf = buf

        out = QPainter(self)
        out.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        out.drawImage(0, 0, buf)
        out.end()
        self._sync_mask(buf, key)

    def _sync_mask(self, buf: QImage, key: tuple) -> None:
        # key on the pixels themselves (not on the animation state): a stale mask can never outlive the frame it was built for
        import zlib
        key = (buf.width(), buf.height(), zlib.crc32(bytes(buf.constBits())))
        if key == self._mask_key:
            return
        self._mask_key = key
        win = self.window()
        if win is None:
            return
        region = self._mask_cache.get(key)
        if region is None:
            logical = buf.scaled(self.width(), self.height()) if buf.devicePixelRatio() > 1 else buf
            region = QRegion(QBitmap.fromImage(logical.createAlphaMask()))
            if _MASK_PAD:
                grown = QRegion(region)
                for dx, dy in ((-_MASK_PAD, 0), (_MASK_PAD, 0), (0, -_MASK_PAD), (0, _MASK_PAD)):
                    grown = grown.united(region.translated(dx, dy))
                region = grown
            if len(self._mask_cache) > _MASK_CACHE_MAX:
                self._mask_cache.clear()
            self._mask_cache[key] = region
        r = QRegion(region)
        if win is not self:
            r.translate(self.mapTo(win, self.rect().topLeft()))
        win.setMask(r)
