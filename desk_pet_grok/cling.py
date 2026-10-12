"""v4-3: 「贴边扒着」 (Qt-free logic). Drop her at the far left / right of the screen: she shrinks to the edge, only half of her body shows,
and she clings to the screen border; when the mouse comes close she leans out and peeks; dragging her away cancels it.
Only outer screen edges count (an edge shared with another screen is not an edge), and a lounge drop (window edge / Dock) wins."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

Rect = tuple[float, float, float, float]  # x, y, w, h (global logical px)
ZONE_FRAC = 0.32  # figure centre within this fraction of the window width from the edge -> cling
PEEK_NEAR_PX = 300.0  # mouse this close (horizontally from the edge) -> peek
PEEK_FAR_PX = 380.0  # hysteresis: back to hiding beyond this
PEEK_HOLD_S = 0.8  # stays peeking this long after the mouse left the near zone
SLIDE_PX_S = 1400.0  # window slide speed into the edge
CANCEL_PX = 14.0  # dragged this far from the clung position -> cancel


def attach_side(win: Rect, screen: Rect, others: Sequence[Rect] = (), zone_frac: float = ZONE_FRAC) -> int:
    """-1 = left edge, +1 = right edge, 0 = no cling. ``win`` = window rect when released."""
    wx, wy, ww, wh = win
    sx, sy, sw, sh = screen
    cx = wx + ww / 2.0
    zone = zone_frac * ww
    side = 0
    if cx - sx <= zone:
        side = -1
    elif (sx + sw) - cx <= zone:
        side = 1
    if side == 0:
        return 0
    probe_x = sx - 2.0 if side < 0 else sx + sw + 2.0
    for ox, oy, ow, oh in others:
        if ox <= probe_x < ox + ow and oy <= wy + wh / 2.0 < oy + oh:
            return 0  # another screen continues here: not a screen border
    return side


def window_x(side: int, screen: Rect, cut_x_win: float) -> float:
    """Window x that puts the sprite's cut edge (at ``cut_x_win`` px inside the window) exactly on the screen border."""
    sx, _sy, sw, _sh = screen
    return (sx if side < 0 else sx + sw) - cut_x_win


def wants_peek(side: int, cursor: tuple[float, float], screen: Rect, win: Rect, peeking: bool) -> bool:
    cx, cy = cursor
    sx, _sy, sw, _sh = screen
    d = (cx - sx) if side < 0 else (sx + sw - cx)
    if d < 0:
        d = 0.0
    wy, wh = win[1], win[3]
    if not (wy - 0.25 * wh <= cy <= wy + 1.25 * wh):
        return False
    return d <= (PEEK_FAR_PX if peeking else PEEK_NEAR_PX)


@dataclass
class ClingMachine:
    enabled: bool = False
    side: int = 0  # 0 none, -1 / +1 clinging to that border
    peek: bool = False
    _hold: float = 0.0

    def attach(self, side: int) -> None:
        self.side, self.peek, self._hold = side, False, 0.0

    def cancel(self) -> None:
        self.side, self.peek, self._hold = 0, False, 0.0

    @property
    def active(self) -> bool:
        return self.enabled and self.side != 0

    def tick(self, dt: float, want_peek: bool) -> None:
        if not self.active:
            self.peek = False
            return
        if want_peek:
            self.peek, self._hold = True, PEEK_HOLD_S
        elif self.peek:
            self._hold -= dt
            if self._hold <= 0:
                self.peek = False
