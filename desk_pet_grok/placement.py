"""Where a bubble / chat card goes around the pet so it never leaves the screen. Qt-free (rects are (x, y, w, h)).

* The screen is the one with the largest overlap with the pet window (nearest centre when she is off every screen),
  and its *available* geometry is used (menu bar / Dock excluded).
* Preferred side: above; if it does not fit there it flips to below, then right, then left; when nothing fits fully the
  side with the most room is used and the box is clamped.
* Along the other axis the box is centred on her and clamped inside the screen.
* ``inset`` is transparent shadow room: the widget may overhang the screen edge by that much (only shadow overhangs).
* The result also says where the tail should point: the edge of the box that faces her and the position of the tip
  along that edge, so the tail always points at her even after clamping."""

from __future__ import annotations

from dataclasses import dataclass

Rect = tuple[float, float, float, float]
SIDES = ("above", "below", "right", "left")


@dataclass(frozen=True)
class Placement:
    x: float
    y: float
    side: str  # where the box sits relative to her
    tail_edge: str  # edge of the box facing her: "bottom" (box above her), "top", "left" (box right of her), "right"
    tail_pos: float  # tip position along that edge, in box-local px (x for top/bottom edges, y for left/right)
    screen: Rect


def _overlap(a: Rect, b: Rect) -> float:
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def pick_screen(anchor: Rect, screens: list[Rect]) -> Rect:
    if not screens:
        return (0.0, 0.0, 1920.0, 1080.0)
    best = max(screens, key=lambda s: _overlap(anchor, s))
    if _overlap(anchor, best) > 0:
        return best
    cx, cy = anchor[0] + anchor[2] / 2, anchor[1] + anchor[3] / 2
    return min(screens, key=lambda s: (s[0] + s[2] / 2 - cx) ** 2 + (s[1] + s[3] / 2 - cy) ** 2)


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if hi < lo else max(lo, min(hi, v))


def place_box(anchor: Rect, size: tuple[float, float], screens: list[Rect], *, gap: float = 8.0, inset: float = 0.0,
              margin: float = 2.0, order: tuple[str, ...] = SIDES, tail_room: float = 0.0,
              force_side: str | None = None) -> Placement:
    """``size`` includes the shadow inset (and the tail room when the tail edge is known)."""
    ax, ay, aw, ah = anchor
    bw, bh = size
    scr = pick_screen(anchor, screens)
    sx0, sy0, sx1, sy1 = scr[0] - inset + margin, scr[1] - inset + margin, scr[0] + scr[2] + inset - margin, scr[1] + scr[3] + inset - margin
    space = {
        "above": ay - gap - sy0,
        "below": sy1 - (ay + ah + gap),
        "right": sx1 - (ax + aw + gap),
        "left": ax - gap - sx0,
    }
    need = {"above": bh, "below": bh, "right": bw, "left": bw}
    if force_side in SIDES:
        side = force_side
    else:
        side = next((s for s in order if space[s] >= need[s]), None) or max(order, key=lambda s: space[s] - need[s])
    if side in ("above", "below"):
        x = _clamp(ax + aw / 2 - bw / 2, sx0, sx1 - bw)
        y = ay - gap - bh if side == "above" else ay + ah + gap
        y = _clamp(y, sy0, sy1 - bh)
    else:
        y = _clamp(ay + ah / 2 - bh / 2, sy0, sy1 - bh)
        x = ax + aw + gap if side == "right" else ax - gap - bw
        x = _clamp(x, sx0, sx1 - bw)
    edge = {"above": "bottom", "below": "top", "right": "left", "left": "right"}[side]
    if edge in ("top", "bottom"):
        tip = ax + aw / 2 - x
    else:
        tip = ay + ah / 2 - y
    return Placement(x, y, side, edge, tip, scr)
