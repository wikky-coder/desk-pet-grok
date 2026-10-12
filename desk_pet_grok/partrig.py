"""Live part-based rig for the FRONT idle pose (feature flag ``part_rig``; default off).

Parts are cut from the existing art (assets/rig25d, built by _genrig/build_rig.py) and animated with
damped springs (springs.py) driven by body acceleration: ears, ahoge, side-hair tips, a 4-link tail chain,
head lag, skirt-hem shear, plus breathing and a runtime ear flick. Everything else (turn/walk) still uses
the pre-rendered sheets, so the rig only draws while the pet is idle at the front.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QTransform

from desk_pet_grok.springs import Chain, Spring
from desk_pet_grok.tailmotion import TailDriver

RIG_DIR = Path(__file__).resolve().parents[1] / "assets" / "rig25d"
BREATH_S = 3.2
FLICK = (0, 11, 14, 5, -3, 0)  # outward degrees, 15 steps/s (same curve as idle_flick.png)
FLICK_GAP_S = (6.0, 14.0)
# (f Hz, zeta, limit deg, gain) -- bible §3.14 with gains rescaled to degrees per px/s^2 of canvas acceleration
P_EAR = (5.0, 0.45, 10.0, 3.3)
P_AHOGE = (4.5, 0.18, 20.0, 5.0)
P_HAIR = (2.4, 0.40, 4.0, 0.6)
P_HEAD = (2.8, 0.70, 3.0, 0.6)
P_SKIRT = (2.6, 0.50, 9.0, 1.8)  # canvas px at 2x
TAIL_RIG_GAIN = 1.0  # tailmotion degrees spread over the links (sum = total bend)
TAIL_LINK_SHARE = (0.15, 0.25, 0.30, 0.30)
TAIL_ROOT = (1.6, 0.45, 15.0, 0.8)
TAIL_TIP = (1.1, 0.30, 22.0, 1.2)
HEM = (610.0, 800.0, 826.0)  # 2x canvas rows: sway ramp start, full, end (legs below stay fixed)


def available(root: Path | None = None) -> bool:
    return ((Path(root) if root else RIG_DIR) / "rig.json").is_file()


LID_Y0, LID_Y1, LID_FEATHER, LID_SPAN = 262.0, 495.0, 18.0, 0.45  # sweep done after LID_SPAN of the fade  # head_base px: where the sweep starts / ends


class PartRig:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else RIG_DIR
        j = json.loads((self.root / "rig.json").read_text())
        self.cw, self.ch = j["canvas"]
        self.neck = j["neck"]
        self.belt = j["belt"]
        self.parts = sorted(j["parts"], key=lambda p: p["z"])
        self._src = {p["name"]: QImage(str(self.root / p["file"])).convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied) for p in self.parts}
        self._scaled: dict[str, tuple[QImage, float]] = {}
        self._scaled_h = 0
        self.t = 0.0
        self.ear_l = Spring(*P_EAR)
        self.ear_r = Spring(*P_EAR)
        self.ahoge = Spring(*P_AHOGE)
        self.hair_l = Spring(*P_HAIR)
        self.hair_r = Spring(*P_HAIR)
        self.head = Spring(*P_HEAD)
        self.skirt = Spring(*P_SKIRT)
        self.tail = Chain(4, TAIL_ROOT[:4], TAIL_TIP[:4])
        self.tail_x = [0.0] * 4
        self.tail_boost = True  # 「尾巴摆动增强」: irregular slow sway + quick wags (tailmotion) instead of the plain 8 deg sine
        self.tail_driver = TailDriver()
        self.flick_t = -1.0
        self.flick_side = (1, 1)
        self.next_flick = random.uniform(*FLICK_GAP_S)
        self.breath = 0.0  # -1..1
        self._bph = 0.0
        self.loaf = 0.0  # lounge pose amounts (set_pose)
        self.droop = 0.0
        self.yawn = 0.0
        self.head_pose = (0.0, 0.0, 0.0)
        self.happy = 0.0  # opacity of the full 'enjoying it' face layer (face_happy.png), 0..1
        self._face = None
        fp = self.root / "face_happy.png"
        if fp.is_file():
            fi = QImage(str(fp))
            if not fi.isNull():
                self._face = fi.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                self._src["face_happy"] = self._face
        self._moods: dict[str, QImage] = {}  # F6 mood faces (same box as head_base); loaded when the files exist
        for mname, fname in (("surprised", "surprised"), ("annoyed", "annoyed"), ("sleepy", "sleepy"),
                             ("pouty", "pouty"), ("happy", "cheerful"), ("dizzy", "dizzy"), ("puffed", "puffed"),
                             ("fuming", "fuming")):
            mp = self.root / f"face_{fname}.png"
            if mp.is_file():
                mi = QImage(str(mp))
                if not mi.isNull():
                    self._moods[mname] = self._src[f"mood_{mname}"] = mi.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.mood_mix: tuple[str, str, float] = ("calm", "calm", 1.0)  # (from, to, fade progress 0..1)
        self.work_body: tuple[str, float] | None = None  # v4b: (mode, 0..1) replace the fists-at-chest trunk by 'holding the prop' body
        self._work_pos: dict[str, tuple[int, int]] = {}
        wroot = self.root.parent / "work25d"
        try:
            wm = json.loads((wroot / "work.json").read_text()).get("trunks", {})
            for mode, pos in wm.items():
                wi = QImage(str(wroot / f"trunk_work_{mode}.png"))
                if not wi.isNull():
                    self._src[f"work_{mode}"] = wi.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                    self._work_pos[mode] = (int(pos["x"]), int(pos["y"]))
        except (OSError, ValueError, KeyError):
            pass
        self.pat = 0.0  # head-pat reaction amount 0..1 (ears down, tail wag, head sinks)
        self.lift = 0.0  # fall: ears / ahoge / tail / hair streamed up by the air, 0..1

    def has_work_body(self, mode) -> bool:
        return mode in self._work_pos

    def set_work_body(self, mode, a: float) -> None:
        self.work_body = (mode, max(0.0, min(1.0, a))) if (mode in self._work_pos and a > 0.002) else None

    def has_mood_face(self, mood: str) -> bool:
        return mood in self._moods

    def mood_faces(self) -> list[tuple[str, float]]:
        """[(face name, opacity)] to stack above head_base, from -> to; the outgoing face stays opaque underneath so the
        two never show the base head through each other."""
        a, b, t = self.mood_mix
        out: list[tuple[str, float]] = []
        if a != b and a in self._moods and t < 1.0:
            out.append((a, 1.0))
        if b in self._moods:
            out.append((b, 1.0 if a == b else min(1.0, t * t * (3 - 2 * t))))
        return out

    def has_happy_face(self) -> bool:
        return self._face is not None

    def set_pose(self, loaf: float = 0.0, droop: float = 0.0, yawn: float = 0.0) -> None:
        """Lounge pose amounts 0..1 (loaf = squat/loaf body, droop = sleepy head, yawn = head-up yawn)."""
        self.loaf = max(0.0, min(1.0, loaf))
        self.droop = max(0.0, min(1.0, droop))
        self.yawn = max(0.0, min(1.0, yawn))

    # ---- dynamics ----
    def step(self, dt: float, a_body: float, *, walking: bool = False, allow_flick: bool = True) -> None:
        dt = max(1e-3, min(dt, 0.1))
        self.t += dt
        self.ear_l.step(dt, a_body)
        self.ear_r.step(dt, a_body)
        self.ahoge.step(dt, a_body)
        self.hair_l.step(dt, a_body)
        self.hair_r.step(dt, a_body)
        self.head.step(dt, a_body)
        self.skirt.step(dt, a_body)
        idle_sway = 8.0 * math.sin(2 * math.pi * 0.25 * self.t)
        if self.pat > 0.01:  # happy tail wag
            idle_sway = (8.0 + 16.0 * self.pat) * math.sin(2 * math.pi * (0.25 + 0.9 * self.pat) * self.t)
        if self.lift > 0.01:  # tail streams upward, fluttering
            idle_sway += self.lift * (-26.0 + 6.0 * math.sin(2 * math.pi * 8.0 * self.t))
        self.tail_x = self.tail.step(dt, a_body, drive=idle_sway)
        if self.tail_boost:  # F8: add the natural wag directly, spread over the links (the chain's own spring drive is too weak to see)
            ang = TAIL_RIG_GAIN * self.tail_driver.step(dt, pat=self.pat, happy=1.0 if self.mood_mix[1] in ("happy", "cheerful") else 0.0,
                                                        asleep=1.0 if self.droop > 0.85 else 0.0)
            self.tail_x = [x + ang * w for x, w in zip(self.tail_x, TAIL_LINK_SHARE)]
        self._bph += 2 * math.pi * dt / (BREATH_S * (1.0 + 0.6 * self.droop))  # slower breathing when asleep
        self.breath = math.sin(self._bph)
        if self.flick_t >= 0:
            self.flick_t += dt
            if self.flick_t >= (len(FLICK) - 1) / 15.0:
                self.flick_t = -1.0
                self.next_flick = self.t + random.uniform(*FLICK_GAP_S)
        elif allow_flick and self.t >= self.next_flick:
            self.flick_t = 0.0
            self.flick_side = random.choices(((1, 0), (0, 1), (1, 1)), weights=(38, 37, 25))[0]

    def flick_deg(self) -> float:
        if self.flick_t < 0:
            return 0.0
        f = self.flick_t * 15.0
        i = min(int(f), len(FLICK) - 2)
        return FLICK[i] + (FLICK[i + 1] - FLICK[i]) * (f - i)

    def at_rest(self) -> bool:
        """True when the pose equals the sheet's front pose closely enough to hand over to the turn clip."""
        springs = (self.ear_l, self.ear_r, self.ahoge, self.hair_l, self.hair_r, self.head, self.skirt)
        return (self.loaf < 0.01 and self.droop < 0.01 and self.yawn < 0.01 and self.pat < 0.02 and self.lift < 0.02
                and abs(self.breath) < 0.25 and self.flick_t < 0 and all(s.at_rest(0.15) for s in springs)
                and all(abs(x) < 1.5 for x in self.tail_x))

    def active(self) -> bool:
        return True  # breathing never stops while the rig is drawn

    def state_key(self) -> tuple:
        return (round(self.breath * 4), round(self.ear_l.x), round(self.ear_r.x), round(self.ahoge.x),
                round(self.skirt.x), round(self.flick_deg()), round(self.tail_x[0] / 3), round(self.tail_x[3] / 3),
                round(self.loaf * 12), round(self.droop * 12), round(self.yawn * 12),
                round(self.pat * 12), round(self.happy * 20), self.mood_mix[:2], round(self.mood_mix[2] * 20), round(self.lift * 12), round(self.lift * math.sin(2 * math.pi * 8.0 * self.t) * 3),
                (self.work_body[0], round(self.work_body[1] * 20)) if self.work_body else None)

    # ---- drawing ----
    def _get(self, name: str, ph: int) -> tuple[QImage, float]:
        if ph != self._scaled_h:
            self._scaled.clear()
            self._scaled_h = ph
        hit = self._scaled.get(name)
        if hit is None:
            k = ph / self.ch
            src = self._src[name]
            im = src.scaled(max(1, round(src.width() * k)), max(1, round(src.height() * k)),
                            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            hit = (im, k)
            self._scaled[name] = hit
        return hit

    def paint(self, p: QPainter, w: int, h: int, dpr: float) -> None:
        """Draw into logical rect (0,0,w,h) (same mapping as the sheet frames)."""
        ph = max(1, int(h * dpr))
        kl = h / self.ch  # canvas px -> logical px
        by = -0.8 * self.breath  # canvas 2x px (head rides the breath)
        sc = 1.0 + 0.008 * (self.breath * 0.5 + 0.5)
        sx = 0.6 * math.sin(2 * math.pi * self.t / (2 * BREATH_S))
        fl = self.flick_deg()
        flutter = math.sin(2 * math.pi * 8.0 * self.t)
        ang = {
            "ear_L": -(fl * self.flick_side[0]) + self.ear_l.x + 6.0 * self.droop - 5.0 * self.yawn
            + 17.0 * self.pat - 24.0 * self.lift - 4.0 * self.lift * flutter,
            "ear_R": (fl * self.flick_side[1]) + self.ear_r.x - 6.0 * self.droop + 5.0 * self.yawn
            - 17.0 * self.pat + 24.0 * self.lift + 4.0 * self.lift * flutter,
            "hair_L": -self.hair_l.x - 7.0 * self.lift * flutter, "hair_R": -self.hair_r.x + 7.0 * self.lift * flutter,
            "ahoge": self.ahoge.x + 14.0 * self.lift * flutter,
        }
        for i, x in enumerate(self.tail_x):
            ang[f"tail{i}"] = x
        head_ang = (self.head.x + 9.0 * self.droop - 5.0 * self.yawn
                    + self.pat * 2.2 * math.sin(2 * math.pi * 1.1 * self.t))
        by += 11.0 * self.pat  # head sinks into the hand
        by += 16.0 * self.loaf + 12.0 * self.droop - 6.0 * self.yawn  # head sinks into the loaf / lifts for a yawn
        nx, ny = self.neck
        bx, by0 = self.belt
        self.head_pose = (by, head_ang, sx)  # for overlays that must follow the head (eye effects)
        op0 = p.opacity()  # the caller may be fading the whole figure (lie-down hand-off, sulk / cling cross-fade): every layer follows it
        for part in self.parts:
            name = part["name"]
            im, k = self._get(name, ph)
            p.save()
            p.translate(sx * kl, 0)
            if name == "trunk":
                p.translate(bx * kl, by0 * kl)
                p.scale(1.0, sc)
                p.translate(-bx * kl, -by0 * kl)
                wb = self.work_body
                if wb is None or wb[1] < 0.995:
                    self._draw_trunk(p, im, part, kl, dpr, k)
                if wb is not None:
                    wim, _ = self._get(f"work_{wb[0]}", ph)
                    p.setOpacity(op0 * wb[1])
                    self._draw_trunk(p, wim, {"x": self._work_pos[wb[0]][0], "y": self._work_pos[wb[0]][1]}, kl, dpr, k)
                    p.setOpacity(op0)
                p.restore()
                continue
            if name in ("head_base", "ear_L", "ear_R", "hair_L", "hair_R", "ahoge"):
                p.translate(0, by * kl)
                p.translate(nx * kl, ny * kl)
                p.rotate(head_ang)
                p.translate(-nx * kl, -ny * kl)
            if name.startswith("tail"):
                chain = []
                i = int(name[4:])
                a = sum(ang[f"tail{j}"] for j in range(i + 1))
                # rotate by the cumulative angle about each ancestor pivot (root first)
                for j in range(i + 1):
                    pv = next(q for q in self.parts if q["name"] == f"tail{j}")["pivot"]
                    chain.append((pv, ang[f"tail{j}"]))
                for pv, aj in chain:
                    p.translate(pv[0] * kl, pv[1] * kl)
                    p.rotate(aj)
                    p.translate(-pv[0] * kl, -pv[1] * kl)
            elif name in ang:
                pv = part["pivot"]
                p.translate(pv[0] * kl, pv[1] * kl)
                p.rotate(ang[name])
                p.translate(-pv[0] * kl, -pv[1] * kl)
            im.setDevicePixelRatio(dpr)
            p.drawImage(QPointF(part["x"] * kl, part["y"] * kl), im)
            if name == "head_base":
                for fname, fa in self.mood_faces():
                    mim, _ = self._get(f"mood_{fname}", ph)
                    mim.setDevicePixelRatio(dpr)
                    p.setOpacity(op0 * fa)
                    p.drawImage(QPointF(part["x"] * kl, part["y"] * kl), mim)
                p.setOpacity(op0)
            if name == "head_base" and self._face is not None and self.happy > 0.004:
                fim, kf = self._get("face_happy", ph)  # same box as head_base, so it rides every head transform
                fim.setDevicePixelRatio(dpr)
                u = min(1.0, self.happy)
                if u < 0.999:
                    fim = self._lid_reveal(fim, kf, u)
                p.drawImage(QPointF(part["x"] * kl, part["y"] * kl), fim)  # (opacity already op0)
            p.restore()

    def _lid_reveal(self, fim: QImage, k: float, u: float) -> QImage:
        """The happy face is revealed top -> bottom like an eyelid sweeping down (u 0..1) with a soft edge, so the open
        eyes and the closed eyes are never blended into each other (no double-eye ghost)."""
        e = LID_Y0 + (LID_Y1 + LID_FEATHER - LID_Y0) * min(1.0, u / LID_SPAN)
        tmp = QImage(fim.size(), QImage.Format.Format_ARGB32_Premultiplied)
        tmp.setDevicePixelRatio(1.0)
        tmp.fill(0)
        q = QPainter(tmp)
        src = QImage(fim)
        src.setDevicePixelRatio(1.0)
        q.drawImage(0, 0, src)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        g = QLinearGradient(0, (e - LID_FEATHER) * k, 0, e * k)
        g.setColorAt(0.0, QColor(0, 0, 0, 255))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        q.fillRect(0, 0, tmp.width(), tmp.height(), QBrush(g))
        q.end()
        tmp.setDevicePixelRatio(fim.devicePixelRatio())
        return tmp

    def _draw_trunk(self, p: QPainter, im: QImage, part: dict, kl: float, dpr: float, k: float) -> None:
        """Trunk with a sheared skirt-hem band (rows weight 0 -> 1 -> 0 around the hem)."""
        dx = self.skirt.x + 5.0 * self.lift * math.sin(2 * math.pi * 7.0 * self.t)  # canvas px at 2x
        if abs(dx) < 0.05:
            im.setDevicePixelRatio(dpr)
            p.drawImage(QPointF(part["x"] * kl, part["y"] * kl), im)
            return
        y0, y1, y2 = HEM
        H = im.height()
        band = max(2, int(round(3 * dpr)))
        src = QImage(im)
        src.setDevicePixelRatio(1.0)
        out = QImage(im.width() + 2 * int(abs(dx) * k) + 4, H, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(0)
        pad = (out.width() - im.width()) // 2
        q = QPainter(out)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        top = int(max(0, (y0 - part["y"]) * k))
        q.drawImage(QPointF(pad, 0), src, QRectF(0, 0, im.width(), top))
        y = top
        while y < H:
            bh = min(band, H - y)
            m = part["y"] + (y + bh / 2.0) / k
            if m < y1:
                u = max(0.0, (m - y0) / (y1 - y0))
                wgt = u * u * (3 - 2 * u)
            else:
                u = min(1.0, (m - y1) / (y2 - y1))
                wgt = 1.0 - u * u * (3 - 2 * u)
            q.drawImage(QPointF(pad + dx * k * wgt, y), src, QRectF(0, y, im.width(), bh))
            y += bh
        q.end()
        out.setDevicePixelRatio(dpr)
        p.drawImage(QPointF(part["x"] * kl - pad / dpr, part["y"] * kl), out)

    def head_point(self, x: float, y: float) -> tuple[float, float]:
        """Where the head-attached canvas point (x, y) (1x canvas px) currently is, following sink / tilt / sway."""
        by, ang, sx = self.head_pose
        nx, ny = self.neck[0] / 2.0, self.neck[1] / 2.0
        a = math.radians(ang)
        dx, dy = x - nx, y - ny
        rx = dx * math.cos(a) - dy * math.sin(a)
        ry = dx * math.sin(a) + dy * math.cos(a)
        return nx + rx + sx / 2.0, ny + ry + by / 2.0
