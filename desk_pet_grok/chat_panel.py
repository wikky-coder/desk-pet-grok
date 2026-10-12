"""Input slip above the pet for 桌宠grok chat: cream rounded card, avatar header, paw send button."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desk_pet_grok import chat_theme as theme
from desk_pet_grok import macwin  # noqa: E402

PANEL_WIDTH = 320  # window width incl. the 14px shadow margin on each side
MAX_LINES = 4
THINKING_TEXT = "本喵想想…"
_MARGIN = 14
_FADE_MS = 180
_ECHO_CHARS = 60


class _InputEdit(QTextEdit):
    """Enter sends; Shift+Enter inserts newline; Esc closes."""

    submit = Signal()
    escape = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            self.submit.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.escape.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def _chat_bubble(text: str, *, mine: bool) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setFont(theme.round_font(10))
    fm_w = lab.fontMetrics().horizontalAdvance(text) + 26
    lab.setFixedWidth(max(40, min(220, fm_w)))
    if mine:
        css = f"background:{theme.BLUE}; color:white; border-radius:12px; border-bottom-right-radius:4px;"
    else:
        css = (
            f"background:white; color:{theme.INK}; border:1px solid {theme.BLUE_PALE};"
            " border-radius:12px; border-bottom-left-radius:4px;"
        )
    lab.setStyleSheet(f"QLabel {{ {css} padding:6px 10px; }}")
    return lab


class ChatPanel(QWidget):
    """Compact chat card (~320px incl. shadow, up to 4 input lines) with paw Send and Stop."""

    send_requested = Signal(str)
    stop_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("桌宠grok · 输入")
        # NOTE: deliberately no WindowDoesNotAcceptFocus: this is the one window that may take focus (explicit open only).
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFixedWidth(PANEL_WIDTH)
        self._fade: QPropertyAnimation | None = None

        card = QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet(
            f"QFrame#card {{ background:{theme.CREAM_RGBA}; border:1px solid rgba(106,166,232,110);"
            " border-radius:18px; }"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(40, 55, 100, 70))
        card.setGraphicsEffect(shadow)

        # header: avatar + name
        self._avatar = QLabel(card)
        self._avatar.setFixedSize(38, 38)
        pm = theme.circle_avatar(38)
        if pm is not None:
            self._avatar.setPixmap(pm)
        name = QLabel(theme.PET_NAME, card)
        name.setFont(theme.round_font(12, bold=True))
        name.setStyleSheet(f"color:{theme.NAVY}; background:transparent;")
        sub = QLabel("Enter 发送 · Shift+Enter 换行", card)
        sub.setFont(theme.round_font(8))
        sub.setStyleSheet("color:#8a97b5; background:transparent;")
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(name)
        names.addWidget(sub)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(self._avatar)
        head.addLayout(names)
        head.addStretch(1)

        # transcript echo: master's last line (right), her status while thinking (left)
        self._mine_row = QHBoxLayout()
        self._mine_row.addStretch(1)
        self._mine_bubble = _chat_bubble("", mine=True)
        self._mine_row.addWidget(self._mine_bubble)
        self._mine_bubble.hide()
        self._think_row = QHBoxLayout()
        self._think_bubble = _chat_bubble(THINKING_TEXT, mine=False)
        self._think_row.addWidget(self._think_bubble)
        self._think_row.addStretch(1)
        self._think_bubble.hide()

        self._input = _InputEdit(card)
        self._input.setPlaceholderText("跟本喵说点什么喵…")
        self._input.setAcceptRichText(False)
        self._input.setFont(theme.round_font(10))
        line_h = self._input.fontMetrics().lineSpacing()
        self._input.setFixedHeight(line_h * MAX_LINES + 16)
        self._input.setStyleSheet(
            f"QTextEdit {{ background:white; color:{theme.INK}; border:1.5px solid {theme.BLUE_PALE};"
            " border-radius:14px; padding:4px 6px; }"
            f"QTextEdit:focus {{ border:1.5px solid {theme.BLUE}; }}"
        )
        self._input.submit.connect(self._on_submit)
        self._input.escape.connect(self.close_panel)

        self._send_btn = QPushButton(card)
        self._send_btn.setToolTip("发送（Enter）")
        self._send_btn.setIcon(QIcon(theme.paw_pixmap(22)))
        self._send_btn.setIconSize(QSize(22, 22))
        self._send_btn.setFixedSize(40, 40)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet(
            f"QPushButton {{ background:{theme.BLUE}; border:none; border-radius:20px; }}"
            f"QPushButton:hover {{ background:{theme.BLUE_DARK}; }}"
            "QPushButton:disabled { background:#c9d3e3; }"
        )
        self._send_btn.clicked.connect(self._on_submit)
        self._stop_btn = QPushButton("停止", card)
        self._stop_btn.setFont(theme.round_font(9))
        self._stop_btn.setFixedHeight(30)
        self._stop_btn.setStyleSheet(
            f"QPushButton {{ background:{theme.BLUE_PALE}; color:{theme.NAVY}; border:none; border-radius:15px; padding:0 14px; }}"
            "QPushButton:hover { background:#c3dcf8; }"
            "QPushButton:disabled { background:#eef2f8; color:#a9b4cb; }"
        )
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._stop_btn.setEnabled(False)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self._stop_btn)
        row.addWidget(self._send_btn)

        inner = QVBoxLayout(card)
        inner.setContentsMargins(12, 10, 12, 12)
        inner.setSpacing(8)
        inner.addLayout(head)
        inner.addLayout(self._mine_row)
        inner.addLayout(self._think_row)
        inner.addWidget(self._input)
        inner.addLayout(row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(_MARGIN, _MARGIN, _MARGIN, _MARGIN)
        outer.addWidget(card)
        self.hide()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        macwin.apply(self)

    def open_panel(self) -> None:
        """Only called from an explicit double-click / menu action: this is the one window allowed to take focus."""
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(_FADE_MS)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.start()

    def close_panel(self) -> None:
        if self._fade is not None:
            self._fade.stop()
        self.setWindowOpacity(1.0)
        self.hide()
        self.closed.emit()

    def set_streaming(self, streaming: bool) -> None:
        self._stop_btn.setEnabled(streaming)
        self._send_btn.setEnabled(not streaming)
        self._input.setReadOnly(streaming)
        self._think_bubble.setVisible(streaming)
        self._relayout()

    def clear_input(self) -> None:
        self._input.clear()

    def reposition_above(self, anchor: QWidget) -> None:
        """Place the card next to the pet on her screen (above if it fits, else below / beside), inside the screen."""
        from desk_pet_grok import placement
        from desk_pet_grok.bubble import screen_rects

        self._anchor = anchor
        self.adjustSize()
        g = anchor.frameGeometry()
        pl = placement.place_box((float(g.x()), float(g.y()), float(g.width()), float(g.height())),
                                 (self.width(), self.height()), screen_rects(), gap=8.0 - _MARGIN, inset=_MARGIN,
                                 order=("above", "below", "right", "left"))
        self._side = pl.side
        self.move(int(round(pl.x)), int(round(pl.y)))

    def _relayout(self) -> None:
        self.layout().activate()
        old_h = self.height()
        self.adjustSize()
        if not self.isVisible():
            return
        anchor = getattr(self, "_anchor", None)
        if anchor is not None:  # the card grew / shrank: place and clamp again (flips side if needed)
            self.reposition_above(anchor)
        elif self.height() != old_h:
            self.move(self.x(), self.y() + old_h - self.height())

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.clear_input()
        echo = text if len(text) <= _ECHO_CHARS else text[:_ECHO_CHARS].rstrip() + "…"
        self._mine_bubble.setText(echo)
        self._mine_bubble.setFixedWidth(max(40, min(220, self._mine_bubble.fontMetrics().horizontalAdvance(echo) + 26)))
        self._mine_bubble.show()
        self._relayout()
        self.send_requested.emit(text)
