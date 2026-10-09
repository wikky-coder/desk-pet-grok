"""Frameless translucent pet window: drag, geometry, motion, click hooks."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QElapsedTimer,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QCursor, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from desk_pet_grok import config
from desk_pet_grok.motion import MotionController, MotionMode, parse_mode
from desk_pet_grok.pet import PetWidget
from desk_pet_grok.state import StateMachine

DEFAULT_HEIGHT = 220
MIN_HEIGHT = 140
MAX_HEIGHT = 360
_CANVAS_W = 412
_CANVAS_H = 344
_DRAG_THRESHOLD_PX = 4
_MOTION_INTERVAL_MS = 33
_CLICK_DELAY_MS = 260
_JUMP_PX = 12
_JUMP_MS = 280

PRODUCT_TITLE = "桌宠grok"


def clamp_window_height(height: int | float) -> int:
    """Clamp pet display height to the allowed 140–360 range."""
    return max(MIN_HEIGHT, min(MAX_HEIGHT, int(height)))


def size_for_height(height: int | float) -> tuple[int, int]:
    """Return (width, height) preserving the 412×344 authoring aspect."""
    h = clamp_window_height(height)
    w = int(round(h * _CANVAS_W / _CANVAS_H))
    return w, h


class PetWindow(QWidget):
    """Always-on-top frameless pet host."""

    chat_requested = Signal()
    pet_clicked = Signal()
    drag_finished = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        state_machine: StateMachine | None = None,
        settings: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self._sm = state_machine or StateMachine()
        self._settings = dict(settings) if settings is not None else config.load_settings()
        self._bubble_visible = bool(self._settings.get("bubble_visible", True))
        self._penetrate = bool(self._settings.get("penetrate", False))
        self._always_on_top = True
        self._drag_origin: QPoint | None = None
        self._drag_moved = False
        self._press_global: QPoint | None = None
        self._chat_open_checker: Callable[[], bool] | None = None
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(_CLICK_DELAY_MS)
        self._click_timer.timeout.connect(self._emit_pet_clicked)
        self._jump_anim: QPropertyAnimation | None = None

        mode = parse_mode(self._settings.get("motion_mode", "wander"))
        self._motion = MotionController(mode=mode)

        self.setWindowTitle(PRODUCT_TITLE)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)

        self._pet = PetWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pet)

        height = self._settings.get("window_height") or DEFAULT_HEIGHT
        self.apply_height(int(height), persist=False)
        self._restore_position()

        if self._settings.get("quiet"):
            self.set_quiet(True, persist=False)
        else:
            self._sync_pet_state()

        self.set_penetrate(self._penetrate, persist=False)

        self._context_menu_builder: Callable[[], object] | None = None

        self._motion_clock = QElapsedTimer()
        self._motion_clock.start()
        self._motion_timer = QTimer(self)
        self._motion_timer.setInterval(_MOTION_INTERVAL_MS)
        self._motion_timer.timeout.connect(self._on_motion_tick)
        self._motion_timer.start()

    @property
    def state_machine(self) -> StateMachine:
        return self._sm

    @property
    def pet(self) -> PetWidget:
        return self._pet

    @property
    def bubble_visible(self) -> bool:
        return self._bubble_visible

    @property
    def penetrate(self) -> bool:
        return self._penetrate

    @property
    def always_on_top(self) -> bool:
        return self._always_on_top

    @property
    def motion_mode(self) -> MotionMode:
        return self._motion.mode

    @property
    def motion(self) -> MotionController:
        return self._motion

    def set_context_menu_builder(self, builder: Callable[[], object]) -> None:
        """Provide a callable that returns a QMenu for right-click."""
        self._context_menu_builder = builder

    def set_chat_open_checker(self, checker: Callable[[], bool] | None) -> None:
        """When True, wander/follow pause (breath animation continues)."""
        self._chat_open_checker = checker

    def set_motion_mode(self, mode: MotionMode | str, *, persist: bool = True) -> None:
        self._motion.set_mode(mode)
        if persist:
            value = self._motion.mode.value
            self._settings["motion_mode"] = value
            config.save_settings({"motion_mode": value})

    def apply_height(self, height: int, *, persist: bool = True) -> None:
        w, h = size_for_height(height)
        self.resize(w, h)
        if persist:
            self._persist_geometry()

    def set_quiet(self, quiet: bool, *, persist: bool = True) -> None:
        if quiet:
            self._sm.enter_quiet()
        else:
            self._sm.leave_quiet()
        self._sync_pet_state()
        if persist:
            self._settings["quiet"] = quiet
            config.save_settings({"quiet": quiet})

    def set_penetrate(self, enabled: bool, *, persist: bool = True) -> None:
        self._penetrate = enabled
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            enabled,
        )
        # Re-show only if already visible so the attribute sticks on some platforms.
        if self.isVisible():
            self.hide()
            self.show()
        if persist:
            self._settings["penetrate"] = enabled
            config.save_settings({"penetrate": enabled})

    def set_always_on_top(self, enabled: bool) -> None:
        self._always_on_top = enabled
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        if self._penetrate:
            self.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                True,
            )
        self.show()

    def set_bubble_visible(self, visible: bool, *, persist: bool = True) -> None:
        self._bubble_visible = visible
        if persist:
            self._settings["bubble_visible"] = visible
            config.save_settings({"bubble_visible": visible})

    def raise_and_activate(self) -> None:
        if self._penetrate:
            # Keep penetrate; still try to surface the window.
            pass
        self.show()
        self.raise_()
        self.activateWindow()

    def play_reaction(self) -> None:
        """Schedule single-click reaction (deferred so double-click can cancel)."""
        self._click_timer.start()

    def play_jump(self) -> None:
        """Tiny vertical bob for click feedback (window + sprite procedural)."""
        self._pet.play_jump()
        if self._jump_anim is not None and self._jump_anim.state() == QPropertyAnimation.State.Running:
            return
        start = self.pos()
        anim = QPropertyAnimation(self, b"pos", self)
        anim.setDuration(_JUMP_MS)
        anim.setKeyValueAt(0.0, start)
        anim.setKeyValueAt(0.45, start + QPoint(0, -_JUMP_PX))
        anim.setKeyValueAt(1.0, start)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._jump_anim = anim
        anim.start()

    def _emit_pet_clicked(self) -> None:
        self.pet_clicked.emit()

    def _cancel_pending_click(self) -> None:
        self._click_timer.stop()

    def sync_pet_state(self) -> None:
        """Push current state machine value to the pet widget."""
        self._pet.set_state(self._sm.state)

    def _sync_pet_state(self) -> None:
        self.sync_pet_state()

    def _chat_open(self) -> bool:
        if self._chat_open_checker is None:
            return False
        try:
            return bool(self._chat_open_checker())
        except Exception:
            return False

    def _motion_paused(self) -> bool:
        """Pause auto-move when penetrating or chat panel is open."""
        return self._penetrate or self._chat_open()

    def _screen_rect(self) -> tuple[float, float, float, float]:
        screen = self.screen()
        if screen is None:
            screen = QApplication.primaryScreen()
        if screen is None:
            return (0.0, 0.0, 1920.0, 1080.0)
        geo = screen.availableGeometry()
        return (float(geo.x()), float(geo.y()), float(geo.width()), float(geo.height()))

    def _on_motion_tick(self) -> None:
        elapsed_ms = self._motion_clock.restart()
        dt = max(0.001, min(elapsed_ms / 1000.0, 0.1))
        dragging = self._drag_origin is not None and self._drag_moved

        if self._motion_paused() and not dragging:
            self._pet.set_motion(False, 0.0)
            return

        cursor = QCursor.pos()
        new_x, new_y, facing = self._motion.tick(
            dt,
            (float(self.x()), float(self.y())),
            (float(self.width()), float(self.height())),
            self._screen_rect(),
            (float(cursor.x()), float(cursor.y())),
            dragging,
        )
        self._pet.set_facing(facing)
        speed = (self._motion.vx ** 2 + self._motion.vy ** 2) ** 0.5
        # Lower threshold so walk cycle / side sprite engage during ease-in.
        moving = (not dragging) and speed >= 5.0 and not self._motion_paused()
        if dragging:
            # Dragging still counts as "moving" for side sprite / walk bob.
            moving = self._drag_moved
            if self._press_global is not None:
                # Approximate drag speed from last move is unavailable; match cruise.
                speed = 65.0 if moving else 0.0
        self._pet.set_motion(moving, speed)
        if not dragging:
            ix, iy = int(round(new_x)), int(round(new_y))
            if ix != self.x() or iy != self.y():
                self.move(ix, iy)
            elif not moving:
                self._pet.set_motion(False, 0.0)

    def _restore_position(self) -> None:
        x = self._settings.get("window_x")
        y = self._settings.get("window_y")
        if isinstance(x, int) and isinstance(y, int):
            self.move(x, y)

    def _persist_geometry(self) -> None:
        geo = {
            "window_x": self.x(),
            "window_y": self.y(),
            "window_width": self.width(),
            "window_height": self.height(),
        }
        self._settings.update(geo)
        config.save_settings(geo)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_global = event.globalPosition().toPoint()
            self._drag_moved = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._drag_origin is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            if self._press_global is not None:
                delta = event.globalPosition().toPoint() - self._press_global
                if abs(delta.x()) + abs(delta.y()) >= _DRAG_THRESHOLD_PX:
                    self._drag_moved = True
            if self._drag_moved:
                new_pos = event.globalPosition().toPoint() - self._drag_origin
                dx = new_pos.x() - self.x()
                if abs(dx) >= 1:
                    facing = 1 if dx > 0 else -1
                    self._motion.facing = facing
                    self._pet.set_facing(facing)
                self.move(new_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if self._drag_origin is not None and self._drag_moved:
                self._persist_geometry()
                self.drag_finished.emit()
            elif self._drag_origin is not None and not self._drag_moved:
                self.play_reaction()
            self._drag_origin = None
            self._press_global = None
            self._drag_moved = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._cancel_pending_click()
            self.chat_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        if self._context_menu_builder is None:
            return
        menu = self._context_menu_builder()
        if menu is not None:
            menu.exec(global_pos)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Erase the top-level translucent buffer (Source replace, not Clear).

        CompositionMode_Clear is unreliable on macOS Cocoa for frameless
        translucent windows and can leave the previous pose as a white
        silhouette. Source + transparent fill replaces every pixel.
        The pet child then Source-blits its own buffer and updates setMask.
        """
        del event
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.end()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._persist_geometry()
        self._motion_timer.stop()
        super().closeEvent(event)
