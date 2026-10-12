"""Status / reply bubble for 桌宠grok.

Preview text is truncated for the bubble; full reply lives in chat history.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from desk_pet_grok import chat_theme as theme
from desk_pet_grok import macwin, placement

# Weighted budget: CJK-ish ≈ 2 units, ASCII ≈ 1 → ~80 Chinese or ~160 English.
_BUBBLE_UNIT_BUDGET = 160
_ELLIPSIS = "…"

# speech-bubble geometry (px)
_TAIL_W = 9
_PAD_X = 14
_PAD_Y = 10
_SHADOW = 7
_RADIUS = 16

_CJK_RE = re.compile(
    r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
    r"\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]"
)


def _char_units(ch: str) -> int:
    return 2 if _CJK_RE.match(ch) else 1


def truncate_for_bubble(
    text: str,
    *,
    max_units: int = _BUBBLE_UNIT_BUDGET,
) -> str:
    """Truncate for bubble preview (~80 CJK / ~160 ASCII units)."""
    if not text:
        return ""
    used = 0
    out: list[str] = []
    for ch in text:
        u = _char_units(ch)
        if used + u > max_units:
            return "".join(out).rstrip() + _ELLIPSIS
        out.append(ch)
        used += u
    return "".join(out)


def bubble_display_text(full: str, *, truncate: bool = True) -> str:
    """Return text shown in the bubble (optionally truncated)."""
    if not truncate:
        return full
    return truncate_for_bubble(full)


def screen_rects() -> list[tuple[float, float, float, float]]:
    """Available geometry (menu bar / Dock excluded) of every screen."""
    from PySide6.QtGui import QGuiApplication

    out = []
    for sc in QGuiApplication.screens():
        g = sc.availableGeometry()
        out.append((float(g.x()), float(g.y()), float(g.width()), float(g.height())))
    return out


class BubbleWidget(QWidget):
    """Frameless translucent bubble near the pet."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self._pref_visible = True
        self._truncate = True
        self._tail_edge = "left"  # edge of the bubble facing her (the tail sits there and points at her)
        self._tail_pos = -1.0  # tip position along that edge (widget px); <0 = default spot
        self._anchor: QWidget | None = None

        self.setWindowTitle("桌宠grok · 气泡")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._label.setFont(theme.round_font(11))
        self._label.setStyleSheet(
            f"QLabel {{ background: transparent; color: {theme.INK}; border: none; padding: 0; }}"
        )
        self._label.setMinimumWidth(150)
        self._label.setMaximumWidth(260)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        self._apply_margins()
        self.hide()

    def _apply_margins(self) -> None:
        """Shadow room all round, plus the tail's room on the edge that faces her."""
        e = self._tail_edge
        t = lambda name: _TAIL_W if e == name else 0  # noqa: E731
        self.layout().setContentsMargins(
            t("left") + _PAD_X + _SHADOW, t("top") + _PAD_Y + _SHADOW,
            t("right") + _PAD_X + _SHADOW, t("bottom") + _PAD_Y + _SHADOW + 2)

    @property
    def full_text(self) -> str:
        return self._full_text

    @property
    def pref_visible(self) -> bool:
        return self._pref_visible

    def set_pref_visible(self, visible: bool) -> None:
        """Menu toggle: whether the bubble may appear."""
        self._pref_visible = visible
        if not visible:
            self.hide()
        elif self._full_text:
            self._refresh()

    def show_text(self, text: str, *, truncate: bool = True) -> None:
        """Replace bubble content and show (if preference allows)."""
        self._full_text = text
        self._truncate = truncate
        self._refresh()

    def append_text(self, delta: str) -> None:
        """Append streamed delta and refresh preview."""
        if not delta:
            return
        self._full_text += delta
        self._truncate = True
        self._refresh()

    def clear(self) -> None:
        self._full_text = ""
        self._label.clear()
        self.hide()

    def reposition_above(self, anchor: QWidget) -> None:
        """Place the bubble next to ``anchor`` (the pet window) on its screen: above if it fits, else below / beside;
        clamped inside the available screen area; the tail turns to point at her. Re-run whenever the text grows."""
        self._anchor = anchor
        self._fit()

    def _fit(self) -> None:
        anchor = self._anchor
        if anchor is None:
            return
        g = anchor.frameGeometry()
        rect = (float(g.x()), float(g.y()), float(g.width()), float(g.height()))
        screens = screen_rects()
        self.adjustSize()
        first = placement.place_box(rect, (self.width(), self.height()), screens, gap=4.0, inset=_SHADOW)
        if first.tail_edge != self._tail_edge:  # the tail room moves to another edge: size changes, so place again
            self._tail_edge = first.tail_edge
            self._apply_margins()
            self.layout().activate()
            self.adjustSize()
        pl = placement.place_box(rect, (self.width(), self.height()), screens, gap=4.0, inset=_SHADOW,
                                 force_side=first.side)
        self._tail_pos = pl.tail_pos
        self.move(int(round(pl.x)), int(round(pl.y)))
        self.update()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        macwin.apply(self)
        if not hasattr(self, "_keepvis_timer"):
            self._keepvis_timer = QTimer(self)
            self._keepvis_timer.setInterval(4000)
            self._keepvis_timer.timeout.connect(lambda: macwin.reassert(self))
            self._keepvis_timer.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        """Rounded cream speech bubble with a small tail on the edge facing her, soft shadow."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        e = self._tail_edge
        l = _SHADOW + (_TAIL_W if e == "left" else 0)
        t = _SHADOW + (_TAIL_W if e == "top" else 0)
        r = self.width() - _SHADOW - (_TAIL_W if e == "right" else 0)
        b = self.height() - _SHADOW - 2 - (_TAIL_W if e == "bottom" else 0)
        body = QRectF(l, t, r - l, b - t)
        theme.draw_soft_shadow(p, body, _RADIUS, spread=_SHADOW)
        path = QPainterPath()
        path.addRoundedRect(body, _RADIUS, _RADIUS)
        tail = QPainterPath()
        half = 7.0
        if e in ("left", "right"):
            ty = self._tail_pos if self._tail_pos >= 0 else body.bottom() - _RADIUS - 2
            ty = max(body.top() + _RADIUS + half, min(body.bottom() - _RADIUS - half, ty))
            if e == "left":
                x0, x1 = body.left() + 1, body.left() - _TAIL_W
            else:
                x0, x1 = body.right() - 1, body.right() + _TAIL_W
            tail.moveTo(x0, ty - half)
            tail.lineTo(x1, ty + 2)
            tail.lineTo(x0, ty + half)
        else:
            tx = self._tail_pos if self._tail_pos >= 0 else body.center().x()
            tx = max(body.left() + _RADIUS + half, min(body.right() - _RADIUS - half, tx))
            if e == "bottom":
                y0, y1 = body.bottom() - 1, body.bottom() + _TAIL_W
            else:
                y0, y1 = body.top() + 1, body.top() - _TAIL_W
            tail.moveTo(tx - half, y0)
            tail.lineTo(tx, y1)
            tail.lineTo(tx + half, y0)
        tail.closeSubpath()
        path = path.united(tail)
        p.setBrush(QColor(255, 251, 243, 245))
        p.setPen(QPen(QColor(106, 166, 232, 140), 1.2))
        p.drawPath(path)
        p.end()

    def _refresh(self) -> None:
        display = bubble_display_text(self._full_text, truncate=self._truncate)
        self._label.setText(display)
        self.layout().activate()
        self.adjustSize()
        if self._pref_visible and self._full_text:
            self._fit()  # text length changed the height: keep it on screen
            self.show()  # WA_ShowWithoutActivating: proactive bubbles never activate the app
        else:
            self.hide()
