"""Eye-only effects drawn over the finished front pose: gaze (iris slides toward the mouse), happy squint, wide eyes.

Works on the final frame buffer (so it serves both the pre-rendered sheet frames and the live part rig): for each eye
the eye-opening region is copied from the buffer and re-drawn shifted / scaled inside an elliptical clip, so no extra
art is needed and the head never moves. Coordinates are canvas px (360x470 authoring canvas)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QLinearGradient, QPainterPath, QPen, QRadialGradient, QTransform

EYES = ((156.0, 210.0), (231.0, 210.0))  # eye centres in the front pose (canvas px)
CLIP = (21.0, 17.0)  # eye-opening half axes (canvas px)
MAX_SHIFT = (4.5, 2.6)  # max iris shift at full gaze (canvas px)


def load_rig_eyes(path: Path | str | None = None) -> bool:
    """Read eye centres / clip / max shift from rig.json ("eyes" block) so a different character needs no code change.
    Missing file or block keeps the built-in constants. Returns whether anything was applied."""
    global EYES, CLIP, MAX_SHIFT
    import json

    try:
        rig = Path(path) if path else Path(__file__).resolve().parents[1] / "assets" / "rig25d" / "rig.json"
        e = json.loads(rig.read_text())["eyes"]
        eyes = tuple((float(a), float(b)) for a, b in e["centres"])
        if len(eyes) != 2:
            return False
        clip = (float(e["clip"][0]), float(e["clip"][1])) if "clip" in e else CLIP
        shift = (float(e["max_shift"][0]), float(e["max_shift"][1])) if "max_shift" in e else MAX_SHIFT
    except (OSError, KeyError, ValueError, TypeError, IndexError):
        return False
    EYES, CLIP, MAX_SHIFT = eyes, clip, shift
    return True


SKIN = QColor(255, 243, 228)
LASH = QColor(86, 44, 30)


def gaze_vector(cursor: tuple[float, float], eye_c: tuple[float, float], reach: float = 260.0) -> tuple[float, float]:
    """Unit-ish gaze (-1..1 per axis) from the eye centre toward the cursor; saturates at ``reach`` px."""
    dx, dy = cursor[0] - eye_c[0], cursor[1] - eye_c[1]
    d = (dx * dx + dy * dy) ** 0.5
    if d < 1e-6:
        return 0.0, 0.0
    m = min(1.0, d / reach)
    return dx / d * m, dy / d * m

_PLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "sprites25d"
_plates: list | None = None  # [QImage, QImage] closed-eye plates (one per eye), or [] when the asset is missing
_PLATE_HALF = (34.0, 30.0)


def _load_plates() -> list:
    """Closed-eye plates built by scripts/build_closed_eyes.py from the smiling Q-version art (footprint skin fill +
    smiling lash line, colour-matched to the sprite). Two plates side by side in one png."""
    global _plates, _PLATE_HALF
    if _plates is None:
        _plates = []
        try:
            img = QImage(str(_PLATE_DIR / "eyes_closed.png"))
            meta = json.loads((_PLATE_DIR / "eyes_closed.json").read_text())
            hw, hh = int(meta["half"][0]) * 2, int(meta["half"][1]) * 2
            if not img.isNull() and img.width() == hw * int(meta["plates"]) and img.height() == hh:
                img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                _plates = [img.copy(i * hw, 0, hw, hh) for i in range(int(meta["plates"]))]
                _PLATE_HALF = (float(meta["half"][0]), float(meta["half"][1]))
        except Exception:
            _plates = []
    return _plates


def _lid_path(t: float, hx: float, hy: float, n: int = 24) -> QPainterPath:
    """Region (plate-local canvas px, origin at eye centre) already swept by the upper lid: top edge down to a gently
    sagging lid line at progress ``t`` (0..1)."""
    import math
    y_edge = -hy - 2.0 + t * (2.0 * hy + 6.0)
    sag = 4.5 * math.sin(math.pi * min(1.0, t))
    path = QPainterPath()
    path.moveTo(-hx - 1.0, -hy - 3.0)
    path.lineTo(hx + 1.0, -hy - 3.0)
    for i in range(n + 1):
        x = hx + 1.0 - (2.0 * hx + 2.0) * i / n
        u = max(-1.0, min(1.0, x / 26.0))
        path.lineTo(x, y_edge + sag * (1.0 - u * u))
    path.closeSubpath()
    return path


def _closed_plate(p: QPainter, plate: QImage, c: QPointF, sx: float, sy: float, mirror: bool, t: float) -> None:
    """Draw one closed-eye plate over the open eye, revealed top-down by the lid line (no old+new line overlap: the
    plate also carries the skin that replaces the old lash / white / iris)."""
    hx, hy = _PLATE_HALF
    p.save()
    p.translate(c)
    p.scale(-abs(sx) if mirror else abs(sx), abs(sy))
    if t < 0.999:
        p.setClipPath(_lid_path(t, hx, hy))
    p.drawImage(QRectF(-hx, -hy, 2.0 * hx, 2.0 * hy), plate)
    p.restore()



def _smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _skin_at(src: QImage, c: QPointF, rx: float, ry: float, dpr: float) -> QColor:
    """Average skin colour around the eye (below / beside it) so the lids blend with the cheek and blush."""
    r = g = b = n = 0
    for dx, dy in ((0.0, 1.25), (-0.95, 1.0), (0.95, 1.0), (0.0, 1.5)):
        x, y = int((c.x() + dx * rx) * dpr), int((c.y() + dy * ry) * dpr)
        if 0 <= x < src.width() and 0 <= y < src.height():
            q = src.pixelColor(x, y)
            r, g, b, n = r + q.red(), g + q.green(), b + q.blue(), n + 1
    if not n:
        return SKIN
    return QColor((7 * SKIN.red() + 3 * (r // n)) // 10, (7 * SKIN.green() + 3 * (g // n)) // 10, (7 * SKIN.blue() + 3 * (b // n)) // 10)


def _arc_y(u: float, ry: float, e: float, top: bool) -> float:
    """Lid edge height at normalised x ``u``: open (flat, outside the eye) -> the happy "n" arc at e=1."""
    final = ry * (-0.70 + 0.84 * u * u)  # ends low, middle high: a smile-shaped closed eye
    open_ = -1.45 * ry if top else 1.45 * ry
    eu = min(1.0, e * 1.7 * (1.0 + 0.8 * u * u))  # corners close slightly ahead of the middle: no stray eye-white
    return open_ + (final - open_) * eu


def _lash_y(u: float, ry: float) -> float:
    return ry * (-0.97 + 0.62 * u * u)  # lower edge of the drawn upper lash (kept as in the art)


def _ribbon(c: QPointF, rx: float, ys, widths, n: int, u0: float, u1: float, extra=None) -> QPainterPath:
    """Filled band of thickness ``widths(u)`` centred on ``ys(u)``; ``extra(u)`` (>=0) additionally grows it upward."""
    up, lo = [], []
    for i in range(n + 1):
        u = u0 + (u1 - u0) * i / n
        y, w = ys(u), widths(u) * 0.5
        up.append(QPointF(c.x() + u * rx, c.y() + y - w - (extra(u) if extra else 0.0)))
        lo.append(QPointF(c.x() + u * rx, c.y() + y + w))
    path = QPainterPath(up[0])
    for pt in up[1:] + lo[::-1]:
        path.lineTo(pt)
    path.closeSubpath()
    return path


def _happy_eye(p: QPainter, src: QImage, c: QPointF, rx: float, ry: float, squint: float, ks: float, dpr: float,
               outward: float = 1.0) -> None:
    """Closing lids: skin lids slide in from above and below along arcs that meet in a smile; at full closure the
    kept upper lash is backed by a tapered dark lash arc plus a thin crescent lower line (both meet at the corners),
    the socket is filled with the surrounding skin colour and a faint small blush sits below-outside the eye."""
    e = _smooth(squint)
    ex = rx * 1.9
    x0, y0 = c.x() - ex, c.y() - ry * 2.0
    layer = QImage(int(2 * ex * dpr) + 2, int(3.3 * ry * dpr) + 2, QImage.Format.Format_ARGB32_Premultiplied)
    layer.setDevicePixelRatio(dpr)
    layer.fill(0)
    q = QPainter(layer)
    q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    q.translate(-x0, -y0)
    n = 28
    us = [-1.6 + 3.2 * i / n for i in range(n + 1)]
    skin = _skin_at(src, c, rx, ry, dpr)
    up = QPainterPath()  # upper lid: only the band below the kept lash, down to the moving lid edge
    up.moveTo(c.x() + us[0] * rx, c.y() + _lash_y(us[0], ry))
    for u in us:
        up.lineTo(c.x() + u * rx, c.y() + _lash_y(u, ry))
    for u in reversed(us):
        up.lineTo(c.x() + u * rx, c.y() + max(_arc_y(u, ry, e, True), _lash_y(u, ry)))
    up.closeSubpath()
    q.fillPath(up, skin)
    lo = QPainterPath()  # lower lid rises from below
    lo.moveTo(c.x() + us[0] * rx, c.y() + 3.0 * ry)
    for u in us:
        lo.lineTo(c.x() + u * rx, c.y() + _arc_y(u, ry, e, False))
    lo.lineTo(c.x() + us[-1] * rx, c.y() + 3.0 * ry)
    lo.closeSubpath()
    q.fillPath(lo, skin)
    # transition: the old lid line rides the closing lid and melts away
    top = lambda u: max(_arc_y(u, ry, e, True), _lash_y(u, ry) + 0.1 * ry)  # noqa: E731
    wl = lambda u: max(1.3 * ks, (0.9 + 1.2 * e) * ks * (0.35 + 0.65 * (1.0 - abs(u) ** 2.0)))  # noqa: E731
    fade = 1.0 - _smooth((e - 0.40) / 0.3)
    if fade > 0.01:
        q.setOpacity(min(1.0, 0.35 + e * 1.4) * fade)
        q.fillPath(_ribbon(c, rx, top, wl, n, -1.0, 1.0), LASH)
    # wipe: the whole original eye (lash, tail, crease, white, iris) dissolves into smooth skin; cross-fades with e
    wa = _smooth((e - 0.50) / 0.22)
    if wa > 0.01:
        sg = QLinearGradient(QPointF(c.x(), c.y() - 1.9 * ry), QPointF(c.x(), c.y() + 1.3 * ry))
        top_c = QColor(SKIN)
        sg.setColorAt(0.0, top_c)
        sg.setColorAt(1.0, skin)
        wc = QColor(255, 255, 255)
        q.setOpacity(wa)
        q.fillRect(QRectF(c.x() - 2.4 * rx, c.y() - 2.2 * ry, 4.8 * rx, 3.6 * ry), sg)
    # new smile eye: one tapered lash arc (kept to the art lash weight) + one very thin crescent below it, meeting
    # in a small tail at the outer corner. Shared geometry, mirrored by ``outward``.
    def lash(u: float) -> float:
        uo = max(0.0, u * outward)
        return ry * (-0.74 + 0.90 * u * u) + 0.20 * ry * _smooth((uo - 0.45) / 0.65)

    def lash_w(u: float) -> float:
        uo = u * outward
        r = abs(u) / 1.12
        body = 1.0 - r ** 2.4
        tail = 0.18 if uo > 0 else 0.1  # a thin pointed end, slightly longer outward
        return max(0.0, (4.0 * ks) * (tail + (1.0 - tail) * body) * (0.55 + 0.45 * (1.0 - u * u)) * (1.0 if r < 1.0 else 0.0))
    tl = _smooth((e - 0.62) / 0.34)
    if tl > 0.01:
        q.setOpacity(tl)
        q.fillPath(_ribbon(c, rx, lash, lash_w, n, -1.12, 1.12), LASH)

        def low(u: float) -> float:
            return lash(u) + 0.52 * ry * max(0.0, 1.0 - u * u) ** 0.8
        lw = lambda u: 1.6 * ks * (1.0 - abs(u) ** 2.2) + 0.2 * ks  # noqa: E731
        q.setOpacity(_smooth((e - 0.82) / 0.18))
        q.fillPath(_ribbon(c, rx, low, lw, n, -0.98, 0.98), LASH)
    q.setOpacity(1.0)
    # feather the whole patch into the face: opaque plateau, soft edge (kept short below to spare the whiskers)
    q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    g = QRadialGradient(QPointF(c.x(), c.y() - 0.28 * ry), 1.0)
    g.setColorAt(0.0, QColor(0, 0, 0, 255))
    g.setColorAt(0.82, QColor(0, 0, 0, 255))
    g.setColorAt(1.0, QColor(0, 0, 0, 0))
    tr = QTransform()
    tr.translate(c.x(), c.y() - 0.28 * ry)
    tr.scale(rx * 1.6, ry * 1.6)
    tr.translate(-c.x(), -(c.y() - 0.28 * ry))
    q.setTransform(tr, True)
    q.fillRect(QRectF(c.x() - 3.0, c.y() - 3.0 - 0.28 * ry, 6.0, 6.0), g)
    q.end()
    p.save()
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.drawImage(QPointF(x0, y0), layer)
    # very faint, small blush below and slightly outside the eye (above the whisker roots)
    bc = QPointF(c.x() + outward * rx * 0.28, c.y() + ry * 1.0)
    bl = QRadialGradient(bc, rx * 0.5)
    bl.setColorAt(0.0, QColor(255, 135, 135, int(34 * e)))
    bl.setColorAt(1.0, QColor(255, 135, 135, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bl)
    p.drawEllipse(bc, rx * 0.5, ry * 0.3)
    p.restore()


def apply(buf: QImage, world: QTransform, k: float, dpr: float, *, gaze: tuple[float, float] = (0.0, 0.0),
          squint: float = 0.0, wide: float = 0.0,
          eyes: tuple[tuple[float, float], ...] = EYES) -> None:
    """Modify ``buf`` in place. ``world`` maps widget-logical image coords (canvas px * k) to buf-logical coords."""
    squint = max(0.0, min(1.0, squint))
    wide = max(0.0, min(1.0, wide))
    gx, gy = gaze
    if squint < 0.01 and wide < 0.01 and abs(gx) < 0.02 and abs(gy) < 0.02:
        return
    src = QImage(buf)  # pristine copy to sample from
    p = QPainter(buf)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    for idx, (ex, ey) in enumerate(eyes):
        c = world.map(QPointF(ex * k, ey * k))
        sx = world.m11() if abs(world.m11()) > 1e-6 else 1.0
        sy = world.m22() if abs(world.m22()) > 1e-6 else 1.0
        rx, ry = CLIP[0] * k * abs(sx), CLIP[1] * k * abs(sy)
        clip = QPainterPath()
        clip.addEllipse(c, rx, ry)
        # source image is in device px: draw it back at logical scale
        def blit(dx: float, dy: float, scale: float = 1.0) -> None:
            p.save()
            p.setClipPath(clip)
            p.translate(c)
            p.scale(scale, scale)
            p.translate(-c.x() + dx, -c.y() + dy)
            img = src
            p.drawImage(QRectF(0, 0, buf.width() / dpr, buf.height() / dpr), img)
            p.restore()
        if wide > 0.01 or abs(gx) > 0.02 or abs(gy) > 0.02:
            mx = gx * MAX_SHIFT[0] * k * abs(sx) * (1.0 - squint)
            my = gy * MAX_SHIFT[1] * k * abs(sy) * (1.0 - squint)
            blit(mx, my, 1.0 + 0.16 * wide)  # opaque: no double-exposed iris while the lids close
        if squint > 0.01:
            plates = _load_plates()
            if idx < len(plates):
                # sx / sy here are the world scales; canvas px -> buf px is k * |s|
                _closed_plate(p, plates[idx], c, k * abs(sx), k * abs(sy), sx < 0, _smooth(min(1.0, squint * 1.75)))
            else:
                _happy_eye(p, src, c, rx, ry, squint, k * abs(sx), dpr,
                           (-1.0 if idx == 0 else 1.0) * (1.0 if sx >= 0 else -1.0))
    p.end()


load_rig_eyes()
