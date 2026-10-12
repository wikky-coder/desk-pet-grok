"""Settings panel (F3): one non-modal, never-focus-stealing window for the options that live in the right-click menu.

The panel is driven by the same ``PetMenuCallbacks`` as the menu, so both always show the same state: every edit goes
through the callbacks, and the panel re-reads all getters after each edit and on a short timer while visible (so a menu
change shows up here too; the menu itself is rebuilt on every right-click). Qt-free spec in ``build_sections``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from desk_pet_grok.menu import SIZE_PRESETS, PetMenuCallbacks


@dataclass
class Row:
    kind: str  # "check" | "choice" | "text" | "button"
    text: str
    get: Callable[[], object] = lambda: None
    set: Callable[[object], None] = lambda v: None
    choices: tuple[tuple[str, object], ...] = ()
    enabled: Callable[[], bool] = lambda: True
    note: Callable[[], str] = lambda: ""  # shown under the row when non-empty (e.g. "permission missing")
    action_text: str = ""  # button label for the note (kind == "check"/"button")
    action: Callable[[], None] | None = None


@dataclass
class Section:
    title: str
    rows: list[Row] = field(default_factory=list)


def ax_note(ax_wanted: bool, trusted: bool) -> str:
    """Explicit hint instead of a silent failure when 「精确到输入框」 is on but Accessibility is not granted."""
    if ax_wanted and not trusted:
        return "未授权「辅助功能」：现在只会趴在窗口上沿。点右侧按钮打开系统设置并勾选本应用。"
    if not ax_wanted:
        return "需要「辅助功能」权限；未开启时不会请求。"
    return "已授权。"


def build_sections(
    cb: PetMenuCallbacks,
    *,
    ax_trusted: Callable[[], bool] = lambda: False,
    open_ax: Callable[[], None] = lambda: None,
    usage_label: Callable[[], str] | None = None,
    screen=None,
    show_advanced: bool = True,
) -> list[Section]:
    rig_ok = cb.part_rig_available()
    look = [
        Row("choice", "大小", cb.get_height, cb.set_height, tuple(SIZE_PRESETS)),
        Row("choice", "模式", cb.get_motion_mode, cb.set_motion_mode, (("散步", "wander"), ("原地", "still"))),
        Row("check", "置顶", cb.is_always_on_top, cb.set_always_on_top),
        Row("check", "显示气泡", cb.is_bubble_visible, cb.set_bubble_visible),
        Row("check", "安静模式", cb.is_quiet, cb.set_quiet),
        Row("check", "鼠标穿透", cb.is_penetrate, cb.set_penetrate),
    ]
    behave = [
        Row("check", "主动开口（关 = 只在你点击/摸头时说话）", cb.is_proactive, cb.set_proactive),
        Row("check", "　限频模式：每小时 ≤3 句、间隔 ≥5 分钟，并按事件开口", cb.is_proactive_v2, cb.set_proactive_v2,
            enabled=cb.is_proactive),
        Row("check", "眼睛看向鼠标（只动瞳孔）", cb.is_look_at_mouse, cb.set_look_at_mouse),
        Row("check", "表情情绪（开心/困/烦/惊讶/委屈；需部件骨架素材）", cb.is_mood, cb.set_mood, enabled=lambda: rig_ok),
        Row("check", "摸头反应（鼠标在头顶来回摆动）", cb.is_petting, cb.set_petting),
        Row("choice", "摸头灵敏度", cb.get_petting_level, cb.set_petting_level,
            (("低", "low"), ("中", "mid"), ("高", "high")), enabled=cb.is_petting),
        Row("check", "部件骨架动画（关闭 = 回退预渲染片）", cb.is_part_rig, cb.set_part_rig, enabled=lambda: rig_ok,
            note=lambda: "" if rig_ok else "缺少骨架素材，已自动使用预渲染片。"),
        Row("check", "部件转身", cb.is_part_turn, cb.set_part_turn, enabled=lambda: rig_ok and bool(cb.is_part_rig())),
        Row("check", "尾巴摆动增强", cb.is_tail_boost, cb.set_tail_boost),
        Row("check", "趴在窗口上沿", cb.is_lounge, cb.set_lounge, enabled=lambda: rig_ok),
        Row("check", "　也趴程序坞", cb.is_lounge_dock, cb.set_lounge_dock, enabled=lambda: rig_ok and bool(cb.is_lounge())),
        Row("check", "　多种趴姿（侧趴 / 托腮 / 伸懒腰 / 睡着蜷成一团）", cb.is_lounge_variants, cb.set_lounge_variants,
            enabled=lambda: rig_ok and bool(cb.is_lounge())),
        Row("check", "　偶尔自己走过去（空闲 10 分钟后）", cb.is_lounge_selfwalk, cb.set_lounge_selfwalk,
            enabled=lambda: rig_ok and bool(cb.is_lounge())),
        Row("check", "　精确到输入框", cb.is_lounge_ax, cb.set_lounge_ax, enabled=lambda: rig_ok and bool(cb.is_lounge()),
            note=lambda: ax_note(bool(cb.is_lounge_ax()), bool(ax_trusted())),
            action_text="打开辅助功能设置", action=open_ax),
    ]
    mem = [
        Row("check", "跨会话记忆（每天最多 5 次摘要调用，默认关）", cb.is_memory, cb.set_memory),
        Row("button", "", action_text="查看记忆…", action=cb.view_memory),
        Row("button", "", action_text="清除记忆…", action=cb.clear_memory),
    ]
    out = [Section("外观", look), Section("行为", behave)]
    if cb.extras:
        out.append(Section("陪伴 / 新功能", [Row("check", e[0], e[1], e[2], note=(e[3] if len(e) > 3 else (lambda: ""))) for e in cb.extras]))
    out.append(Section("记忆", mem))
    if screen is not None:
        sc = [
            Row("check", "读前台软件名（不花额度）", lambda: screen.get("screen_aware"), lambda v: screen.set_flag("screen_aware", bool(v))),
            Row("check", "允许截屏看（花额度，需屏幕录制权限）", lambda: screen.get("screen_vision"),
                lambda v: screen.set_flag("screen_vision", bool(v))),
            Row("check", "　偶尔主动评论", lambda: screen.get("screen_proactive"), lambda v: screen.set_flag("screen_proactive", bool(v))),
            Row("check", "安静时段 22:00–08:00 不截屏", lambda: screen.get("screen_quiet_hours"),
                lambda v: screen.set_flag("screen_quiet_hours", bool(v))),
        ]
        if usage_label is not None:
            sc.append(Row("text", "", note=usage_label))
        out.append(Section("屏幕感知", sc))
    if show_advanced:
        out.append(Section("高级", [
            Row("check", "记录校准数据（只记数字，不含标题/内容；默认关）", cb.is_calibration_log, cb.set_calibration_log),
        ]))
    return out


class SettingsPanel(QWidget):
    """Non-modal settings window. Never takes keyboard focus; closing it only hides it."""

    def __init__(self, sections: list[Section], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("桌宠grok 设置")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            "QWidget{background:#fffaf2;color:#4a3426;font-size:13px;}"
            "QLabel#title{font-size:14px;font-weight:600;color:#a0522d;}"
            "QLabel#note{color:#8a7766;font-size:12px;}"
            "QPushButton{background:#ffe3c9;border:1px solid #e8b88f;border-radius:8px;padding:3px 10px;}"
        )
        self._sections = sections
        self.setFixedWidth(440)
        self._widgets: list[tuple[Row, object]] = []
        self._busy = False
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(4)
        for sec in sections:
            t = QLabel(sec.title)
            t.setObjectName("title")
            root.addSpacing(6)
            root.addWidget(t)
            for row in sec.rows:
                root.addLayout(self._make_row(row))
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    # ---- building ----
    def _make_row(self, row: Row):
        box = QVBoxLayout()
        box.setSpacing(0)
        line = QHBoxLayout()
        w: dict = {}
        if row.kind == "check":
            cb = QCheckBox(row.text)
            cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            cb.toggled.connect(lambda v, r=row: self._edit(r, bool(v)))
            line.addWidget(cb)
            w["check"] = cb
        elif row.kind == "choice":
            line.addWidget(QLabel(row.text + "："))
            grp = QButtonGroup(self)
            btns = []
            for label, val in row.choices:
                rb = QRadioButton(label)
                rb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                rb.toggled.connect(lambda on, r=row, v=val: on and self._edit(r, v))
                grp.addButton(rb)
                line.addWidget(rb)
                btns.append((val, rb))
            w["choice"] = btns
        if row.action is not None:
            b = QPushButton(row.action_text or "打开")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda: row.action())
            line.addStretch(1)
            line.addWidget(b)
            w["button"] = b
        line.addStretch(1)
        box.addLayout(line)
        note = QLabel("")
        note.setObjectName("note")
        note.setWordWrap(True)
        note.setMaximumWidth(400)
        note.hide()
        box.addWidget(note)
        w["note"] = note
        self._widgets.append((row, w))
        return box

    # ---- state sync ----
    def _edit(self, row: Row, value: object) -> None:
        if self._busy:
            return
        row.set(value)
        self.refresh()

    def refresh(self) -> None:
        """Re-read every getter (also called after each edit and on a timer while visible)."""
        self._busy = True
        try:
            for row, w in self._widgets:
                en = bool(row.enabled())
                if "check" in w:
                    c = w["check"]
                    c.setChecked(bool(row.get()))
                    c.setEnabled(en)
                if "choice" in w:
                    cur = row.get()
                    for val, rb in w["choice"]:
                        rb.setChecked(val == cur)
                        rb.setEnabled(en)
                text = row.note()
                w["note"].setText(text)
                w["note"].setVisible(bool(text))
        finally:
            self._busy = False
        self.layout().activate()
        self.setFixedHeight(self.layout().totalHeightForWidth(self.width()))

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._timer.stop()
        super().hideEvent(event)

    def checkbox_for(self, text_part: str):
        for row, w in self._widgets:
            if text_part in row.text and "check" in w:
                return w["check"]
        raise KeyError(text_part)

    def note_for(self, text_part: str) -> str:
        for row, w in self._widgets:
            if text_part in row.text:
                return w["note"].text()
        raise KeyError(text_part)
