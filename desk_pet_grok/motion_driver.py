"""Window motion: wander / still driving for both the legacy sprite pet and the 2.5D puppet, screen rect, restore.

Mixed into ``PetWindow`` (see window.py)."""

from __future__ import annotations

import time

from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from desk_pet_grok import puppet
from desk_pet_grok.motion import MotionMode
from desk_pet_grok.pet25d import Pet25D

_PUPPET_FPS = 42.0  # walk-frames per second at cruise (ground speed derived)


class MotionMixin:
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
        self._power_tick(elapsed_ms / 1000.0, dragging)

        if self._puppet:
            self._puppet_tick(dt, dragging)
            return

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
            if self._puppet:
                x, y = puppet.clamp_to_screen(x, y, self.width(), self.height(), self._screen_rect())
                x, y = int(x), int(y)
            self.move(x, y)

    def _puppet_tick(self, dt: float, dragging: bool) -> None:
        pet: Pet25D = self._pet  # type: ignore[assignment]
        mode = self._motion.mode
        paused = self._motion_paused() and not dragging
        rect = self._screen_rect()
        cursor = QCursor.pos()
        self._mood_tick()
        patted = self.feed_cursor(time.monotonic(), float(cursor.x()), float(cursor.y()), dragging=dragging,
                                  buttons_down=QApplication.mouseButtons() != Qt.MouseButton.NoButton)
        self._anger_tick(dt)
        self._work_tick(dt, dragging)
        self._greet_tick(dt)
        if not dragging and self._cling_tick(dt):
            pet.drive(dt, want_walk=False, facing=self._motion.facing, look=False, dragging=False)
            return
        if dragging:
            self._lounge.on_drag_start()
        elif self._lounge.tick(dt):
            return
        if dragging:
            pet.drive(dt, want_walk=False, facing=self._motion.facing, look=False,
                      dragging=True, drag_vx=self._drag_vx)
            self._drag_vx *= 0.85
            return
        if paused or patted or mode is MotionMode.still or self._anger.stage >= 4 or self._work.mode is not None:
            pet.drive(dt, want_walk=False, facing=self._motion.facing, look=False, dragging=False)
            return
        old_x, old_y = self.x(), self.y()
        new_x, _ny, facing = self._motion.tick(
            dt,
            (float(old_x), float(old_y)),
            (float(self.width()), float(self.height())),
            rect,
            (float(cursor.x()), float(cursor.y())),
            False,
        )
        speed = (self._motion.vx ** 2 + self._motion.vy ** 2) ** 0.5
        want = speed >= 5.0
        lg = pet.logic
        k = self.height() / puppet.CANVAS_H
        v_walk = _PUPPET_FPS * puppet.STRIDE_PX_PER_FRAME * k  # ground px/s at cruise
        scale = (v_walk / 65.0) * (lg.s.gain if lg.walking else 0.0)
        dx = (new_x - old_x) * scale
        # horizontal-only stroll on the "ground"; keep y, never leave the screen
        nx, ny = puppet.clamp_to_screen(old_x + dx, float(old_y), self.width(), self.height(), rect)
        moved = nx - old_x
        if want and abs((old_x + dx) - nx) > 0.001:
            # hit the edge of the usable area: stop and pick a new target
            self._motion.release()
            want = False
        if abs(moved) >= 0.01 or True:
            self._frac_x = getattr(self, "_frac_x", 0.0) + (nx - old_x)
            step = int(self._frac_x)
            if step:
                self._frac_x -= step
                self.move(old_x + step, int(ny))
            elif int(ny) != old_y:
                self.move(old_x, int(ny))
        pet.drive(dt, want_walk=want, facing=facing, look=False, dragging=False,
                  ground_dx=moved)
        if want and abs(moved) > 0.0:
            self._persist_timer.start()
