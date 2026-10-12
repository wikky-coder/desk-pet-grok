"""Pointer handling for the pet window: press / drag / release / double-click, context menu, geometry persistence.

Mixed into ``PetWindow`` (see window.py)."""

from __future__ import annotations

import time

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent

from desk_pet_grok import config, puppet

_DRAG_THRESHOLD_PX = 4


class PointerMixin:
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
        if self._puppet and event.button() == Qt.MouseButton.LeftButton:
            if not self._pet.hit(event.position().toPoint()):
                event.ignore()
                return
            self._pet.wake()
            self._lounge.on_press()
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
                if self._cling.active:
                    self._cling_cancel()
                new_pos = event.globalPosition().toPoint() - self._drag_origin
                self._anger.drag_sample(time.monotonic(), float(event.globalPosition().x()))
                dx = new_pos.x() - self.x()
                if self._puppet:
                    new_pos = QPoint(*(int(v) for v in puppet.clamp_to_screen(
                        new_pos.x(), new_pos.y(), self.width(), self.height(), self._screen_rect(), -self.width() * 0.4)))
                    self._drag_vx = self._drag_vx * 0.5 + dx * 30.0 * 0.5
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
            self._anger.release()
            if self._drag_origin is not None and self._drag_moved:
                cling_side = self._cling_side_now()  # before the release clamp pulls her back onto the screen
                if self._puppet:
                    self._motion.release()
                    cx, cy = puppet.clamp_to_screen(self.x(), self.y(), self.width(), self.height(), self._screen_rect())
                    self.move(int(cx), int(cy))
                self._persist_geometry()
                if not self._lounge.on_drop():
                    self._cling_try(cling_side)
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
