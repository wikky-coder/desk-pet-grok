"""Input slip above the pet for 桌宠grok chat."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

PANEL_WIDTH = 280
MAX_LINES = 4


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


class ChatPanel(QWidget):
    """Compact chat input (~280px, up to 4 lines) with Stop."""

    send_requested = Signal(str)
    stop_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("桌宠grok · 输入")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedWidth(PANEL_WIDTH)

        self._input = _InputEdit(self)
        self._input.setPlaceholderText("跟我说点什么…（Enter 发送，Shift+Enter 换行）")
        self._input.setAcceptRichText(False)
        # ~4 lines worth of height
        line_h = self._input.fontMetrics().lineSpacing()
        self._input.setFixedHeight(line_h * MAX_LINES + 16)
        self._input.submit.connect(self._on_submit)
        self._input.escape.connect(self.close_panel)

        self._send_btn = QPushButton("发送", self)
        self._send_btn.clicked.connect(self._on_submit)
        self._stop_btn = QPushButton("停止", self)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._stop_btn.setEnabled(False)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._send_btn)
        row.addWidget(self._stop_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._input)
        layout.addLayout(row)

        self.setStyleSheet(
            "ChatPanel {"
            "  background-color: rgba(250, 250, 252, 235);"
            "  border: 1px solid rgba(0, 0, 0, 45);"
            "  border-radius: 10px;"
            "}"
        )
        self.hide()

    def open_panel(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    def close_panel(self) -> None:
        self.hide()
        self.closed.emit()

    def set_streaming(self, streaming: bool) -> None:
        self._stop_btn.setEnabled(streaming)
        self._send_btn.setEnabled(not streaming)
        self._input.setReadOnly(streaming)

    def clear_input(self) -> None:
        self._input.clear()

    def reposition_above(self, anchor: QWidget) -> None:
        self.adjustSize()
        geo = anchor.frameGeometry()
        x = geo.x() + max(0, (geo.width() - self.width()) // 2)
        y = geo.y() - self.height() - 8
        if y < 0:
            y = geo.y() + 8
        self.move(x, y)

    def _on_submit(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self.clear_input()
        self.send_requested.emit(text)
