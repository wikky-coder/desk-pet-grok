"""Small vector effects drawn over the standing figure (canvas px, mapped through the figure's world transform):
dizzy stars, anger mark, steam. Used by the v4 shake-anger feature; the same overlay hook carries props / hats later."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

HEAD_CENTER = (176.0, 120.0)  # 1x canvas px (face centre)
EAR_STEAM = ((60.0, 64.0), (292.0, 64.0))  # where steam leaves (the ear roots)
CROWN = (176.0, 44.0)


def _star(cx: float, cy: float, r: float) -> QPainterPath:
    path = QPainterPath()
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pt = QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a))
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    return path


class AngerFx:
    """stage 1 dizzy stars circle the head; 2/3/4 pulsing anger mark; 4 steam puffs out of the ears and a faster mark."""

    def __init__(self) -> None:
        self.stage = 0
        self.t = 0.0
        self.alpha = 0.0
        self.puffs: list[list[float]] = []  # [side, x, y, age, life, r0, drift]
        self._spawn = 0.0
        self.rng = random.Random(7)

    def set_stage(self, stage: int) -> None:
        self.stage = stage

    def active(self) -> bool:
        return self.stage in (1, 2, 3, 4) or self.alpha > 0.01 or bool(self.puffs)

    def step(self, dt: float) -> None:
        self.t += dt
        tgt = 1.0 if self.stage in (1, 2, 3, 4) else 0.0
        self.alpha += max(-dt * 3.0, min(dt * 5.0, tgt - self.alpha))
        if self.stage == 4:
            self._spawn += dt
            while self._spawn >= 0.11:
                self._spawn -= 0.11
                side = self.rng.choice((0, 1))
                self.puffs.append([side, EAR_STEAM[side][0] + self.rng.uniform(-6, 6), EAR_STEAM[side][1], 0.0,
                                   self.rng.uniform(0.9, 1.4), self.rng.uniform(7, 11), self.rng.uniform(-14, 14)])
        for p in self.puffs:
            p[3] += dt
            p[2] -= (46.0 + 14.0 * p[3]) * dt
            p[1] += (p[6] + (-1 if p[0] == 0 else 1) * 10.0) * dt
        self.puffs = [p for p in self.puffs if p[3] < p[4]]

    def paint(self, q: QPainter, world, k: float, dpr: float, pet) -> None:
        rig = pet._rig
        hp = (lambda x, y: rig.head_point(x, y)) if rig is not None else (lambda x, y: (x, y))
        sx = abs(world.m11()) or 1.0

        def M(x: float, y: float) -> QPointF:
            hx, hy = hp(x, y)
            return world.map(QPointF(hx * k, hy * k))

        q.save()
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # steam first (behind the stars / mark)
        for side, x, y, age, life, r0, _ in self.puffs:
            u = age / life
            c = M(x, y)
            r = (r0 + 16.0 * u) * k * sx
            col = QColor(250, 250, 252, int(200 * (1 - u) ** 1.3))
            q.setPen(QPen(QColor(170, 178, 196, int(150 * (1 - u))), max(1.0, 1.4 * k * sx)))
            q.setBrush(QBrush(col))
            q.drawEllipse(c, r, r * 0.86)
            q.setPen(Qt.PenStyle.NoPen)
            q.setBrush(QBrush(QColor(255, 255, 255, int(150 * (1 - u)))))
            q.drawEllipse(QPointF(c.x() - r * 0.25, c.y() - r * 0.2), r * 0.45, r * 0.35)
        a = max(0.0, min(1.0, self.alpha))
        if a > 0.01 and self.stage == 1:
            for i in range(3):
                ang = self.t * 3.2 + i * 2 * math.pi / 3
                x = CROWN[0] + 92.0 * math.cos(ang)
                y = CROWN[1] - 8.0 + 16.0 * math.sin(ang)
                c = M(x, y)
                s = (9.0 + 2.0 * math.sin(self.t * 6 + i)) * k * sx
                path = _star(c.x(), c.y(), s)
                front = math.sin(ang) > 0
                q.setPen(QPen(QColor(205, 150, 30, int(230 * a)), max(1.0, 1.2 * k * sx)))
                q.setBrush(QBrush(QColor(255, 224, 80, int((255 if front else 170) * a))))
                q.drawPath(path)
        if a > 0.01 and self.stage in (2, 3, 4):
            pulse = 1.0 + (0.16 if self.stage == 4 else 0.07) * math.sin(self.t * (13.0 if self.stage == 4 else 7.0))
            c = M(292.0 if world.m11() > 0 else 60.0, 40.0)  # always on the viewer's right
            s = (15.0 + 2.0 * (self.stage - 2)) * pulse * k * sx
            for col, wid in ((QColor(140, 20, 20, int(255 * a)), 6.4), (QColor(235, 55, 55, int(255 * a)), 4.0)):
                pen = QPen(col, max(1.6, wid * k * sx))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                q.setPen(pen)
                q.setBrush(Qt.BrushStyle.NoBrush)
                for rot in (45, 135, 225, 315):
                    rc = QPointF(c.x() + s * 1.15 * math.cos(math.radians(rot)), c.y() + s * 1.15 * math.sin(math.radians(rot)))
                    q.drawArc(QRectF(rc.x() - s * 0.85, rc.y() - s * 0.85, s * 1.7, s * 1.7), int((-(rot + 180) - 42) * 16), 84 * 16)
        q.restore()


def paint_terminal(q: QPainter, k: float, t: float, ease: float) -> None:
    """A small floating terminal window in front of her (vector, same navy / cream palette as the figure)."""
    q.save()
    q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    bob = 2.0 * math.sin(t * 1.9)
    x0, y0, w, h = 98.0, 258.0 + (1.0 - ease) * 50.0 + bob, 164.0, 100.0  # 1x canvas px, below her chin, over the fists
    r = QRectF(x0 * k, y0 * k, w * k, h * k)
    lw = max(1.2, 1.7 * k)
    q.translate(0, 0)
    q.setPen(QPen(QColor(20, 22, 44), lw))
    q.setBrush(QBrush(QColor(34, 38, 66)))  # body (navy)
    q.drawRoundedRect(r, 9 * k, 9 * k)
    bar = QRectF(r.left(), r.top(), r.width(), 17 * k)
    path = QPainterPath(); path.addRoundedRect(r, 9 * k, 9 * k)
    clip = QPainterPath(); clip.addRect(bar)
    q.save(); q.setClipPath(path.intersected(clip)); q.fillRect(bar, QColor(250, 240, 226)); q.restore()  # cream title bar
    q.setPen(QPen(QColor(20, 22, 44), lw)); q.setBrush(Qt.BrushStyle.NoBrush); q.drawRoundedRect(r, 9 * k, 9 * k)
    for i, col in enumerate((QColor(240, 122, 122), QColor(244, 200, 110), QColor(140, 206, 150))):
        q.setPen(Qt.PenStyle.NoPen); q.setBrush(col)
        q.drawEllipse(QPointF(r.left() + (11 + 11 * i) * k, r.top() + 8.5 * k), 3.3 * k, 3.3 * k)
    # text lines (rounded bars), the last line types itself
    rows = ((0.62, QColor(150, 230, 170)), (0.82, QColor(255, 216, 150)), (0.48, QColor(150, 230, 170)), (0.74, QColor(200, 210, 255)))
    ty = r.top() + 26 * k
    q.setPen(Qt.PenStyle.NoPen)
    for i, (frac, col) in enumerate(rows):
        q.setBrush(col)
        q.drawRoundedRect(QRectF(r.left() + 10 * k, ty + i * 11 * k, (w - 24) * frac * k, 4.2 * k), 2 * k, 2 * k)
    typed = (0.25 + 0.55 * ((t * 0.5) % 1.0))
    q.setBrush(QColor(150, 230, 170))
    q.drawRoundedRect(QRectF(r.left() + 10 * k, ty + 4 * 11 * k, 6 * k, 4.2 * k), 2 * k, 2 * k)  # prompt
    q.drawRoundedRect(QRectF(r.left() + 20 * k, ty + 4 * 11 * k, (w - 50) * typed * k, 4.2 * k), 2 * k, 2 * k)
    if int(t * 2.2) % 2 == 0:  # blinking cursor
        q.setBrush(QColor(255, 255, 255))
        q.drawRect(QRectF(r.left() + (22 + (w - 50) * typed) * k, ty + 4 * 11 * k - 1 * k, 5 * k, 6.4 * k))
    q.restore()


class GreetFx:
    """A small vector icon floating up beside her head for a few seconds (sun / rice bowl / tea cup / moon / Zzz)."""
    LIFE = 4.6

    def __init__(self) -> None:
        self.kind = ""
        self.t = 99.0

    def start(self, kind: str) -> None:
        self.kind, self.t = kind, 0.0

    def active(self) -> bool:
        return bool(self.kind) and self.t < self.LIFE

    def step(self, dt: float) -> None:
        self.t += dt

    def paint(self, q: QPainter, world, k: float, dpr: float, pet) -> None:
        if not self.active():
            return
        rig = pet._rig
        hp = (lambda x, y: rig.head_point(x, y)) if rig is not None else (lambda x, y: (x, y))
        sx = abs(world.m11()) or 1.0
        u = self.t / self.LIFE
        a = min(1.0, self.t / 0.35) * min(1.0, (1.0 - u) / 0.22)
        rise = 14.0 * u
        hx, hy = hp(292.0 if world.m11() > 0 else 60.0, 36.0 - rise)
        c = world.map(QPointF(hx * k, hy * k))
        s = 25.0 * k * sx
        q.save()
        q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        q.setOpacity(max(0.0, min(1.0, a)))
        q.translate(c)
        q.rotate(4.0 * math.sin(self.t * 3.0))
        ink = QColor(60, 52, 82)
        pen = QPen(ink, max(1.2, 1.6 * k * sx)); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        kind = self.kind
        if kind == "sun":
            q.setPen(pen); q.setBrush(QColor(255, 214, 72)); q.drawEllipse(QPointF(0, 0), s * 0.62, s * 0.62)
            for i in range(8):
                ang = i * math.pi / 4 + self.t * 0.8
                q.drawLine(QPointF(math.cos(ang) * s * 0.85, math.sin(ang) * s * 0.85), QPointF(math.cos(ang) * s * 1.2, math.sin(ang) * s * 1.2))
        elif kind in ("moon", "moon_zzz"):
            path = QPainterPath(); path.addEllipse(QPointF(0, 0), s * 0.8, s * 0.8)
            cut = QPainterPath(); cut.addEllipse(QPointF(s * 0.42, -s * 0.2), s * 0.7, s * 0.7)
            q.setPen(pen); q.setBrush(QColor(255, 232, 130)); q.drawPath(path.subtracted(cut))
            q.setBrush(QColor(255, 244, 170))
            for dx, dy, r in ((s * 0.9, -s * 0.7, 0.3), (s * 1.15, s * 0.25, 0.22)):
                q.drawPath(_star(dx, dy, s * r))
            if kind == "moon_zzz":
                f = q.font(); f.setBold(True); f.setPixelSize(max(8, int(s * 0.9))); q.setFont(f)
                q.setPen(QColor(120, 110, 190)); q.drawText(QPointF(s * 0.95, -s * 0.55 - 3 * math.sin(self.t * 2)), "z")
        elif kind == "zzz":
            f = q.font(); f.setBold(True)
            q.setPen(QColor(120, 110, 190))
            for i, (txt, dx, dy, sz) in enumerate((("z", 0.0, 1.0, 0.8), ("Z", 0.7, 0.4, 1.05), ("Z", 1.4, -0.25, 1.3))):
                f.setPixelSize(max(8, int(s * sz))); q.setFont(f)
                off = 3.0 * math.sin(self.t * 2.2 + i)
                q.drawText(QPointF(s * dx - s * 0.6, s * dy + off), txt)
        elif kind == "heart":
            beat = 1.0 + 0.12 * math.sin(self.t * 9.0)
            hp = QPainterPath()
            r = s * 0.55 * beat
            hp.moveTo(0, r * 1.1)
            hp.cubicTo(-r * 2.0, -r * 0.2, -r * 0.9, -r * 1.6, 0, -r * 0.5)
            hp.cubicTo(r * 0.9, -r * 1.6, r * 2.0, -r * 0.2, 0, r * 1.1)
            q.setPen(QPen(QColor(150, 40, 70), max(1.2, 1.6 * k * sx)))
            q.setBrush(QColor(255, 120, 150))
            q.drawPath(hp)
        elif kind == "bowl":
            q.setPen(pen); q.setBrush(QColor(250, 246, 236))
            bowl = QPainterPath(); bowl.moveTo(-s * 0.9, -s * 0.1); bowl.lineTo(s * 0.9, -s * 0.1); bowl.quadTo(s * 0.85, s * 0.85, 0, s * 0.85); bowl.quadTo(-s * 0.85, s * 0.85, -s * 0.9, -s * 0.1)
            q.drawPath(bowl)
            q.setBrush(QColor(255, 255, 255)); q.drawEllipse(QPointF(0, -s * 0.1), s * 0.9, s * 0.22)  # rice
            q.setPen(QPen(QColor(150, 110, 70), max(1.2, 1.8 * k * sx))); q.drawLine(QPointF(s * 0.1, -s * 0.2), QPointF(s * 1.0, -s * 1.0)); q.drawLine(QPointF(s * 0.35, -s * 0.2), QPointF(s * 1.25, -s * 0.85))
            self._steam(q, s, k * sx)
        elif kind == "cup":
            q.setPen(pen); q.setBrush(QColor(252, 244, 236))
            q.drawRoundedRect(QRectF(-s * 0.7, -s * 0.35, s * 1.3, s * 1.0), s * 0.18, s * 0.28)
            q.setBrush(Qt.BrushStyle.NoBrush); q.drawArc(QRectF(s * 0.35, -s * 0.15, s * 0.65, s * 0.6), -90 * 16, 180 * 16)
            q.setBrush(QColor(176, 118, 78)); q.setPen(Qt.PenStyle.NoPen); q.drawEllipse(QPointF(-s * 0.05, -s * 0.28), s * 0.55, s * 0.12)
            self._steam(q, s, k * sx)
        q.restore()

    def _steam(self, q: QPainter, s: float, kk: float) -> None:
        q.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(2):
            x = (-0.25 + 0.5 * i) * s
            ph = self.t * 2.4 + i * 1.7
            path = QPainterPath(); path.moveTo(x, -s * 0.5)
            path.cubicTo(x + s * 0.3 * math.sin(ph), -s * 0.8, x - s * 0.3 * math.sin(ph), -s * 1.0, x + s * 0.1 * math.sin(ph), -s * 1.35)
            q.setPen(QPen(QColor(190, 196, 214), max(1.2, 1.9 * kk))); q.drawPath(path)


# ---- festival decorations (stickers from assets/festival25d) ----
# head ornaments: name -> (anchor x, anchor y, width, tilt deg) in 1x canvas px; hats sit with their bottom-centre on the anchor
HEAD_SPEC = {"witch": (170.0, 94.0, 116.0, -7.0, "bottom"), "santa": (174.0, 98.0, 118.0, 6.0, "bottom"),
             "party": (204.0, 80.0, 52.0, 14.0, "bottom"), "flowers": (84.0, 168.0, 70.0, -10.0, "center")}
# floor items next to her feet: name -> width (1x px); left item at x=54, right item at x=306, bottom at y=464
SIDE_W = {"pumpkin": 74.0, "gingerbread": 62.0, "envelope": 50.0, "lantern": 46.0, "tangyuan": 72.0, "zongzi": 62.0, "mooncake": 70.0, "flag": 64.0}
SIDE_X = (54.0, 306.0)
SIDE_BOTTOM = 466.0
