"""Part rig for the SIDE WALK (feature flag ``part_rig``). Pieces are exported from the existing gait solver
(_genrig/build_walk_rig.py): every rigid piece carries a per-frame affine from the SAME solver as the pre-rendered
sheet, so foot planting and stride are identical (no slide). On top, springs drive ear, ahoge, back hair lock,
head lag, tail chain and skirt hem from body acceleration and the walk bob."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QTransform

from desk_pet_grok.tailmotion import TailDriver
from desk_pet_grok.partrig import P_AHOGE, P_EAR, P_HAIR, P_HEAD, P_SKIRT, TAIL_ROOT, TAIL_TIP
from desk_pet_grok.springs import Chain, Spring

WALK_DIR = Path(__file__).resolve().parents[1] / "assets" / "rig25d" / "walk"
BOB_GAIN = 0.02  # vertical bob acceleration (canvas px/s^2) -> equivalent lateral accel for the loose parts


def available(root: Path | None = None) -> bool:
    return ((Path(root) if root else WALK_DIR) / "walk.json").is_file()


class WalkRig:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else WALK_DIR
        j = json.loads((self.root / "walk.json").read_text())
        self.n = j["frames"]
        self.ch = j["canvas"][1]
        self.bob = j["bob"]
        self.tail_drive = j["tail_drive"]
        self.tail_s = j.get("tail_s", [0.0, 0.25, 0.5, 0.75, 1.0])
        self.neck = j["neck"]
        self.pelvis = j.get("pelvis", j["neck"])
        self.parts = j["parts"]
        self._src = {p["name"]: QImage(str(self.root / p["file"])).convertToFormat(
            QImage.Format.Format_ARGB32_Premultiplied) for p in self.parts}
        self._scaled: dict[str, QImage] = {}
        self._scaled_h = 0
        self.ear = Spring(*P_EAR)
        self.ahoge = Spring(*P_AHOGE)
        self.hair = Spring(*P_HAIR)
        self.head = Spring(*P_HEAD)
        self.skirt = Spring(*P_SKIRT)
        self.tail = Chain(4, TAIL_ROOT[:4], TAIL_TIP[:4])
        self.tail_x = [0.0] * 4
        self.tail_boost = True
        self.tail_driver = TailDriver()
        self._last_idx = 0
        self.lean_s = Spring(2.2, 0.4, 4.0, 0.0012)  # inertial pitch: pitches forward on stop, back on start
        self.lean_steady = 0.0
        self.dip = 0.0
        self._bob_v = 0.0
        self._bob_prev = 0.0

    def step(self, dt: float, a_body: float, idx: int | None = None, walking: bool = True, speed: float = 0.0) -> None:
        """a_body: acceleration in the sprite's native frame (+x = toward the back of the native-left-facing walk)."""
        dt = max(1e-3, min(dt, 0.1))
        tgt = -min(3.0, 0.045 * speed) if walking else 0.0  # steady forward lean (CCW on the native frame)
        self.lean_steady += (tgt - self.lean_steady) * min(1.0, dt / 0.3)
        self.lean_s.step(dt, a_body)
        self.dip += (min(2.5, 0.0015 * abs(a_body)) - self.dip) * min(1.0, dt / 0.12)
        a = a_body
        drive = 0.0
        if idx is not None and walking:
            idx %= self.n
            b = self.bob[idx]
            v = (b - self._bob_prev) / dt
            acc = (v - self._bob_v) / dt
            self._bob_prev, self._bob_v = b, v
            a += max(-3000.0, min(3000.0, BOB_GAIN * acc * 50))  # canvas bob -> loose-part lag
            drive = 0.0  # the gait's tail wiggle is applied deterministically in paint() (matches the sheet pose exactly)
            self._last_idx = idx
        else:
            self._bob_v = 0.0
        for s in (self.ear, self.ahoge, self.hair, self.head, self.skirt):
            s.step(dt, a)
        self.tail_x = self.tail.step(dt, a, drive=drive)
        if self.tail_boost:  # extra natural wag on top of the gait's own tail swing (less while walking)
            ang = (0.6 if walking else 1.0) * self.tail_driver.step(dt)
            self.tail_x = [x + ang * w for x, w in zip(self.tail_x, (0.15, 0.25, 0.30, 0.30))]

    def at_rest(self) -> bool:
        return abs(self.lean_steady) < 0.1 and self.lean_s.at_rest(0.1) and all(s.at_rest(0.2) for s in (self.ear, self.ahoge, self.hair, self.head, self.skirt))

    def state_key(self) -> tuple:
        return (round(self.ear.x), round(self.ahoge.x), round(self.hair.x), round(self.head.x),
                round(self.skirt.x), round((self.lean_steady + self.lean_s.x) * 4), round(self.dip), round(self.tail_x[1] / 3), round(self.tail_x[3] / 3))

    def _tail_det(self, idx: int, j: int) -> float:
        """Gait tail wiggle share of link j (same bend the pre-rendered walk uses), so hand-off poses match."""
        s = self.tail_s
        return self.tail_drive[idx] * (s[j + 1] - s[j])

    def _get(self, name: str, ph: int) -> QImage:
        if ph != self._scaled_h:
            self._scaled.clear()
            self._scaled_h = ph
        im = self._scaled.get(name)
        if im is None:
            k = ph / self.ch
            src = self._src[name]
            im = src.scaled(max(1, round(src.width() * k)), max(1, round(src.height() * k)),
                            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._scaled[name] = im
        return im

    def paint(self, p: QPainter, w: int, h: int, dpr: float, idx: int) -> None:
        idx %= self.n
        ph = max(1, int(h * dpr))
        kl = h / self.ch
        nx, ny = self.neck
        # hem shear = gait term + spring term (local px at 2x)
        for part in self.parts:
            name = part["name"]
            m = part["M"][idx]
            kind = part.get("kind")
            p.save()
            legs = name.startswith(("thigh", "shin", "foot"))
            if not legs:  # body pitch about the pelvis + start/stop dip; feet stay planted
                p.translate(0, self.dip * kl)
                px, py = self.pelvis
                p.translate(px * kl, py * kl)
                p.rotate(self.lean_steady + self.lean_s.x)
                p.translate(-px * kl, -py * kl)
            if kind == "head":
                p.translate(nx * kl, ny * kl)
                p.rotate(self.head.x)
                p.translate(-nx * kl, -ny * kl)
            p.setTransform(QTransform(m[0], m[3], m[1], m[4], m[2] * kl, m[5] * kl), True)
            if kind == "tail":
                for j in range(part["idx"] + 1):
                    pv = next(q for q in self.parts if q["name"] == f"tail{j}")["pivot"]
                    p.translate(pv[0] * kl, pv[1] * kl)
                    p.rotate(self.tail_x[j] + self._tail_det(idx, j))
                    p.translate(-pv[0] * kl, -pv[1] * kl)
            elif kind == "head" and part.get("spr"):
                pv = part["pivot"]
                a = {"ear": self.ear.x, "hair": -self.hair.x, "ahoge": self.ahoge.x}[part["spr"]]
                p.translate(pv[0] * kl, pv[1] * kl)
                p.rotate(a)
                p.translate(-pv[0] * kl, -pv[1] * kl)
            im = self._get(name, ph)
            ox, oy = part["ox"] * kl, part["oy"] * kl
            if kind == "skirt":
                self._draw_skirt(p, im, part, idx, kl, dpr, ox, oy)
            else:
                im.setDevicePixelRatio(dpr)
                p.drawImage(QPointF(ox, oy), im)
            p.restore()

    def _draw_skirt(self, p: QPainter, im: QImage, part: dict, idx: int, kl: float, dpr: float,
                    ox: float, oy: float) -> None:
        dx = part["hem"][idx] + self.skirt.x * 0.5  # canvas(local) px
        dy_all = (part.get("hem_dy") or [0.0] * self.n)[idx]
        H = im.height()
        scale = (self._scaled_h / self.ch)  # image px per canvas px
        y0, y1 = part["hem_y"]
        band = max(2, int(round(3 * dpr)))
        src = QImage(im)
        src.setDevicePixelRatio(1.0)
        pad = int(abs(dx) * scale) + 3
        out = QImage(im.width() + 2 * pad, H, QImage.Format.Format_ARGB32_Premultiplied)
        out.fill(0)
        q = QPainter(out)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        y = 0
        while y < H:
            bh = min(band, H - y)
            ly = part["oy"] + (y + bh / 2.0) / scale  # local canvas y of this strip
            u = max(0.0, min(1.0, (ly - y0) / max(1.0, (y1 - y0))))
            wgt = u * u * (3 - 2 * u)
            q.drawImage(QPointF(pad + dx * scale * wgt, y + dy_all * scale * wgt), src, QRectF(0, y, im.width(), bh))
            y += bh
        q.end()
        out.setDevicePixelRatio(dpr)
        p.drawImage(QPointF(ox - pad / dpr, oy), out)
