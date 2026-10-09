"""Status / reply bubble for 桌宠grok.

Preview text is truncated for the bubble; full reply lives in chat history.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Weighted budget: CJK-ish ≈ 2 units, ASCII ≈ 1 → ~80 Chinese or ~160 English.
_BUBBLE_UNIT_BUDGET = 160
_ELLIPSIS = "…"

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


class BubbleWidget(QWidget):
    """Frameless translucent bubble near the pet."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self._pref_visible = True
        self._truncate = True

        self.setWindowTitle("桌宠grok · 气泡")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self._label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        font = QFont()
        font.setPointSize(11)
        self._label.setFont(font)
        self._label.setStyleSheet(
            "QLabel {"
            "  background-color: rgba(255, 255, 255, 230);"
            "  color: #222;"
            "  border: 1px solid rgba(0, 0, 0, 40);"
            "  border-radius: 10px;"
            "  padding: 8px 10px;"
            "}"
        )
        self._label.setMinimumWidth(160)
        self._label.setMaximumWidth(280)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self.hide()

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
        """Place the bubble roughly above ``anchor`` (e.g. pet window)."""
        self.adjustSize()
        geo = anchor.frameGeometry()
        x = geo.x() + max(0, (geo.width() - self.width()) // 2)
        y = geo.y() - self.height() - 8
        if y < 0:
            y = geo.y() + geo.height() + 8
        self.move(x, y)

    def _refresh(self) -> None:
        display = bubble_display_text(self._full_text, truncate=self._truncate)
        self._label.setText(display)
        self.adjustSize()
        if self._pref_visible and self._full_text:
            self.show()
            self.raise_()
        else:
            self.hide()
