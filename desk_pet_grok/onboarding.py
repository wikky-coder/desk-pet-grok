"""First-run guide (F3): three short pages, non-modal, never takes keyboard focus. Shown once, only on a fresh install."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

PAGES: tuple[tuple[str, str], ...] = (
    ("她会做什么",
     "拖着我走到哪里都行～\n"
     "· 在桌面上散步 / 待着，眼睛会看向鼠标（只动瞳孔）\n"
     "· 鼠标在我头顶来回摆动 = 摸头\n"
     "· 拖到窗口顶边或程序坞上，我就趴下（需先在「设置」里打开）\n"
     "· 双击我就能聊天；我不会抢你正在输入的窗口的焦点。"),
    ("默认关闭的权限",
     "下面这些默认都是关的，只有你主动打开才会请求权限：\n"
     "· 精确趴到输入框：需要「辅助功能」\n"
     "· 看屏幕：读前台软件名（免费）；截屏看（花额度，需「屏幕录制」，每小时/每天有上限）\n"
     "随时可以在右键菜单 →「设置…」里改。"),
    ("完成",
     "准备好啦！右键我 →「设置…」可以调大小、灵敏度、开关各项功能。\n"
     "要聊天请先「设置 API Key…」。"),
)


def should_onboard(settings: dict) -> bool:
    """Only a fresh install (never onboarded and no saved window position): existing users are never interrupted."""
    return not settings.get("onboarded") and settings.get("window_x") is None and settings.get("window_y") is None


class OnboardingPanel(QWidget):
    def __init__(self, on_done: Callable[[], None] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_done = on_done
        self._i = 0
        self._finished = False
        self.setWindowTitle("欢迎")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            "QWidget{background:#fffaf2;color:#4a3426;font-size:13px;}"
            "QLabel#h{font-size:16px;font-weight:600;color:#a0522d;}"
            "QPushButton{background:#ffe3c9;border:1px solid #e8b88f;border-radius:8px;padding:4px 14px;}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 14)
        self._head, self._body, self._step = QLabel(), QLabel(), QLabel()
        self._head.setObjectName("h")
        self._body.setWordWrap(True)
        self._body.setMinimumWidth(340)
        lay.addWidget(self._head)
        lay.addWidget(self._body)
        row = QHBoxLayout()
        row.addWidget(self._step)
        row.addStretch(1)
        self._skip = QPushButton("跳过")
        self._next = QPushButton("下一步")
        for b in (self._skip, self._next):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            row.addWidget(b)
        lay.addLayout(row)
        self._skip.clicked.connect(self.finish)
        self._next.clicked.connect(self.advance)
        self._show_page()

    @property
    def page(self) -> int:
        return self._i

    def _show_page(self) -> None:
        head, body = PAGES[self._i]
        self._head.setText(head)
        self._body.setText(body)
        self._step.setText(f"{self._i + 1}/{len(PAGES)}")
        self._next.setText("完成" if self._i == len(PAGES) - 1 else "下一步")
        self._skip.setVisible(self._i < len(PAGES) - 1)

    def advance(self) -> None:
        if self._i >= len(PAGES) - 1:
            self.finish()
            return
        self._i += 1
        self._show_page()

    def finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self.hide()
        if self._on_done is not None:
            self._on_done()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.finish()
        super().closeEvent(event)
