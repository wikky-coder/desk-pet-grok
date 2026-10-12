"""Paint helpers extracted from Pet25D (slim pass).

Each function takes the Pet25D widget as ``pet`` and mutates only through
its public/private attributes — behaviour identical to the former methods.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QPainter

from desk_pet_grok import fx as fxmod, loungeart, puppet


def paint_holiday(pet, q: QPainter, world, k: float) -> None:
    from desk_pet_grok import holidays

    art = pet._hol_images()
    _label, head, (left, right) = holidays.FESTIVALS[pet._holiday]
    q.save()
    q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    q.setOpacity(max(0.0, min(1.0, pet._hol_a)))
    sx = abs(world.m11()) or 1.0
    mirror = world.m11() < 0
    rig = pet._rig
    if head and head in art and head in fxmod.HEAD_SPEC:
        ax, ay, wd, tilt, anchor = fxmod.HEAD_SPEC[head]
        hx, hy = rig.head_point(ax, ay) if rig is not None else (ax, ay)
        if mirror:  # the hairpin side is the character's; ornaments follow the head, not the screen
            pass
        c = world.map(QPointF(hx * k, hy * k))
        im = art[head]
        w = wd * k * sx
        h = w * im.height() / im.width()
        ang = tilt * (-1.0 if mirror else 1.0) + (rig.head_pose[1] * (-1.0 if mirror else 1.0) if rig is not None else 0.0)
        q.translate(c)
        q.rotate(ang)
        q.drawImage(QRectF(-w / 2.0, -h if anchor == "bottom" else -h / 2.0, w, h), im)
        q.resetTransform()
    for name, x in ((left, fxmod.SIDE_X[0]), (right, fxmod.SIDE_X[1])):
        if name and name in art:
            im = art[name]
            w = fxmod.SIDE_W[name] * k
            h = w * im.height() / im.width()
            bob = 0.8 * k * math.sin(time.monotonic() * 1.6 + x)
            q.drawImage(QRectF(x * k - w / 2.0, fxmod.SIDE_BOTTOM * k - h + bob, w, h), im)
    q.restore()


def paint_work(pet, q: QPainter, k: float) -> None:
    mode, u = pet._work_shown, max(0.0, min(1.0, pet._work_t))
    if pet._rig is not None and pet._rig.has_work_body(mode) and pet._rig_drawing():
        return  # the prop is part of the body layer (two hands, no leftover fists)
    ease = u * u * (3 - 2 * u)
    t = pet._work_clock
    q.save()
    q.setOpacity(ease)
    if mode == "terminal":
        fxmod.paint_terminal(q, k, t, ease)
    else:
        art = pet._work_art_load()
        name = {"read": "book", "code": "laptop", "draw": "palette"}.get(mode)
        if art is not None and name in art:
            im, (x0, y0, x1, y1), (px, py) = art[name]
            rise = (1.0 - ease) * 70.0  # slides up from below when she takes it out
            ang, dy = 0.0, 0.0
            if mode == "read":
                ang = 0.9 * math.sin(t * 0.9)
                dy = 1.2 * math.sin(t * 1.7)
            elif mode == "code":
                burst = max(0.0, math.sin(t * 2.3)) ** 2  # bursts of typing
                dy = -2.2 * burst * abs(math.sin(t * 17.0))
                ang = 0.35 * burst * math.sin(t * 11.0)
            else:
                ang = 2.4 * math.sin(t * 1.6)
                dy = 1.5 * math.sin(t * 2.2)
            q.translate(px / 2.0 * k, (py / 2.0 + rise + dy) * k)
            q.rotate(ang)
            q.translate(-px / 2.0 * k, -py / 2.0 * k)
            q.drawImage(QRectF(x0 / 2.0 * k, y0 / 2.0 * k, (x1 - x0) / 2.0 * k, (y1 - y0) / 2.0 * k), im)
    q.restore()


def paint_cling(pet, q: QPainter, k: float) -> None:
    art = pet._cling_art_load()
    if art is None:
        return
    tag = "L" if pet._cling_side <= 0 else "R"
    if not pet._cling_side:  # fading out: keep the last side
        tag = getattr(pet, "_cling_last", "L")
    pet._cling_last = tag
    feet = 459.0 * k
    bob = 1.0 + 0.004 * math.sin(time.monotonic() * 2.4)
    q.save()
    q.translate(0, feet)
    q.scale(1.0, bob)
    q.translate(0, -feet)
    for name, op in (("cling_" + tag, pet._cling_t), ("peek_" + tag, pet._cling_t * pet._peek_t)):
        if op < 0.002 or (name.startswith("cling_") and pet._peek_t > 0.995):
            continue  # fully peeking: the idle frame would only show through as a second pair of legs
        im, (x0, y0, x1, y1) = art["frames"][name]
        q.setOpacity(min(1.0, op))
        q.drawImage(QRectF(x0 / 2.0 * k, y0 / 2.0 * k, (x1 - x0) / 2.0 * k, (y1 - y0) / 2.0 * k), im)
    q.restore()


def paint_sulk(pet, q: QPainter, world, k: float, w: int, h: int) -> None:
    sp = pet._sulk_sprite()
    if sp is None:
        return
    im, (x0, y0, x1, y1) = sp
    c = world.map(QPointF((x0 + x1) / 4.0 * k, (y0 + y1) / 4.0 * k))
    hw = (x1 - x0) / 4.0 * k * abs(world.m11())
    hh = (y1 - y0) / 4.0 * k * abs(world.m22())
    t = pet.logic.s.t if hasattr(pet.logic.s, "t") else time.monotonic()
    bob = 0.004 * hh * math.sin(time.monotonic() * 2.1)  # slow huffy breathing
    q.setOpacity(min(1.0, pet._sulk_t))
    q.drawImage(QRectF(c.x() - hw, c.y() - hh - bob, 2 * hw, 2 * hh + bob), im)
    q.setOpacity(1.0)


def paint_lounge_art(pet, buf: QImage, w: int, h: int, dpr: float, art) -> None:
    loaf, droop, yawn = pet._lounge  # type: ignore[misc]
    p = QPainter(buf)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    k0 = h / puppet.CANVAS_H
    foot0 = puppet.CANVAS_H * k0 - 12 * k0
    p.translate(w / 2.0, foot0 + (2.5 + 3.0 * (1.0 if pet._lounge_art is not None else 0.0)) * k0 * pet._pat
                + 0.8 * k0 * pet._pat * math.sin(pet._lounge_art.t * 9.0 if pet._lounge_art is not None else 0.0))  # petted: sink a little; fall: squash / stretch about the feet
    p.scale(pet._fall_sq[0], pet._fall_sq[1])
    p.translate(-w / 2.0, -foot0)
    stand = loungeart.standing_opacity(loaf)
    if stand > 0.01 and pet._rig is not None:
        k = h / puppet.CANVAS_H
        foot_y = puppet.CANVAS_H * k - 12 * k
        p.save()
        if stand < 0.995:  # one group fade: overlapping rig layers (hair, ears, head, face) drawn translucent would stack into a solid head over a ghost body
            grp = QImage(max(1, int(w * dpr)), max(1, int(h * dpr)), QImage.Format.Format_ARGB32_Premultiplied)
            grp.setDevicePixelRatio(dpr)
            grp.fill(0)
            q = QPainter(grp)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            q.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            q.translate(w / 2.0, foot_y)
            q.scale(-1.0 if pet.logic.mirror() else 1.0, 1.0)
            q.translate(-w / 2.0, -foot_y)
            pet._rig.paint(q, w, h, dpr)
            q.end()
            p.setOpacity(stand)
            p.drawImage(0, 0, grp)
        else:
            p.translate(w / 2.0, foot_y)
            p.scale(-1.0 if pet.logic.mirror() else 1.0, 1.0)
            p.translate(-w / 2.0, -foot_y)
            pet._rig.paint(p, w, h, dpr)
        p.restore()
    for a_, mult, sink in pet._active_arts():
        a_.set_pose(loaf, droop, yawn)
        a_.paint(p, w, h, dpr, loaf, droop, yawn, mult=mult, sink=sink)
    p.end()
    main = pet._main_art() or art
    pet._present(buf, "lounge", ("lounge",) + main.state_key() + (pet._var_to, round(pet._var_t * 20), w, h), dpr)
