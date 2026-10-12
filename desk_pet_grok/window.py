"""Frameless translucent pet window: drag, geometry, motion, click hooks."""

from __future__ import annotations

import logging
import time
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
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget

from desk_pet_grok import config, macwin
from desk_pet_grok.motion import MotionController, MotionMode, parse_mode
from desk_pet_grok import cling, powersave, petting, puppet, shake, workalong
from desk_pet_grok.dbglog import CalibrationLog
from desk_pet_grok.interaction import PAT_SAY_COOLDOWN_S, InteractionMixin  # noqa: F401
from desk_pet_grok.lounge_driver import LoungeDriver
from desk_pet_grok.mood import MoodMachine
from desk_pet_grok.motion_driver import _PUPPET_FPS, MotionMixin  # noqa: F401
from desk_pet_grok.pet import PetWidget
from desk_pet_grok.pointer import _DRAG_THRESHOLD_PX, PointerMixin  # noqa: F401
from desk_pet_grok.pet25d import Pet25D, available as puppet_available
from desk_pet_grok.state import StateMachine

DEFAULT_HEIGHT = 220
MIN_HEIGHT = 140
MAX_HEIGHT = 360
_CANVAS_W = 412
_CANVAS_H = 344
_MOTION_INTERVAL_MS = 33
_KEEPVIS_INTERVAL_MS = 4000
_CLICK_DELAY_MS = 260
_JUMP_PX = 12
_JUMP_MS = 280

PRODUCT_TITLE = "桌宠grok"
log = logging.getLogger("desk_pet_grok")


def clamp_window_height(height: int | float) -> int:
    """Clamp pet display height to the allowed 140–360 range."""
    return max(MIN_HEIGHT, min(MAX_HEIGHT, int(height)))


def size_for_height(height: int | float) -> tuple[int, int]:
    """Return (width, height) preserving the 412×344 authoring aspect."""
    h = clamp_window_height(height)
    w = int(round(h * _CANVAS_W / _CANVAS_H))
    return w, h


class PetWindow(PointerMixin, InteractionMixin, MotionMixin, QWidget):
    """Always-on-top frameless pet host."""

    chat_requested = Signal()
    pet_clicked = Signal()
    drag_finished = Signal()
    lounge_say = Signal(str)  # category of a line to say (lounge_*, pet_head, pet_fall)

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

        use25 = self._settings.get("puppet25d", True) and puppet_available()
        self._puppet = bool(use25)
        self._drag_vx = 0.0
        self._last_drag_x: int | None = None
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.setInterval(1500)
        self._persist_timer.timeout.connect(self._persist_geometry)

        mode = parse_mode(self._settings.get("motion_mode", "wander"))
        if mode is MotionMode.follow:
            # legacy "look at mouse" mode: she stays put (still) and the passive eye-follow takes over
            mode = MotionMode.still
            self._settings["motion_mode"] = mode.value
            self._settings["look_at_mouse"] = True
            config.save_settings({"motion_mode": mode.value, "look_at_mouse": True})
        self._look_at_mouse = bool(self._settings.get("look_at_mouse", True))
        self._petting_on = bool(self._settings.get("petting", True))
        self._anger = shake.AngerMachine(enabled=bool(self._settings.get('shake_anger', False)))
        self._anger_last = time.monotonic()
        self._cling = cling.ClingMachine(enabled=bool(self._settings.get('cling_edge', False)))
        self._cling_said_peek = False
        self._work = workalong.WorkAlong(enabled=bool(self._settings.get('work_along', False)))
        self._work_poller = None
        self._power = powersave.PowerSaver(enabled=bool(self._settings.get('power_save', False)))
        self._mood = MoodMachine(enabled=bool(self._settings.get("mood", False)))
        self._mood_last = time.monotonic()
        self._calib = CalibrationLog()
        self._calib.enabled = bool(self._settings.get("calibration_log", False))
        self._pat_det_lie = petting.LyingPettingDetector(
            str(self._settings.get("petting_level", "mid")),
            overrides=self._settings.get("petting_params"),
            on_event=lambda kind, **kw: self._calib.log(kind, lying=True, **kw),
        )
        self._pat_det_anger = petting.LyingPettingDetector(str(self._settings.get("petting_level", "mid")), overrides=self._settings.get("petting_params"))
        self._pat_det = petting.PettingDetector(
            str(self._settings.get("petting_level", "mid")),
            overrides=self._settings.get("petting_params"),
            on_event=self._calib.log,
        )
        self._pat_now = False
        self._pat_last_say = -1e9
        self._motion = MotionController(mode=mode)
        self._motion.flat = self._puppet

        self.setWindowTitle(PRODUCT_TITLE)
        # Never steal keyboard focus from the app the user is typing in (macOS: non-activating panel).
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)  # Tool windows stay when the app is inactive
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)

        self._pet = Pet25D(self) if self._puppet else PetWidget(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pet)
        if self._puppet:
            self._init_rig()

        if self._puppet:
            self._pet.set_gaze_enabled(self._look_at_mouse)  # type: ignore[union-attr]

        height = self._settings.get("window_height") or DEFAULT_HEIGHT
        self.apply_height(int(height), persist=False)
        self._restore_position()

        if self._settings.get("quiet"):
            self.set_quiet(True, persist=False)
        else:
            self._sync_pet_state()

        self.set_penetrate(self._penetrate, persist=False)

        self._context_menu_builder: Callable[[], object] | None = None

        # Gentle keep-visible: only acts when the window is covered/hidden; never raise_()/activateWindow().
        self._keepvis_timer = QTimer(self)
        self._keepvis_timer.setInterval(_KEEPVIS_INTERVAL_MS)
        self._keepvis_timer.timeout.connect(self._keep_visible)
        self._keepvis_timer.start()

        if self._puppet and hasattr(self._pet, "set_mood_enabled"):
            self._pet.set_mood_enabled(self._mood.enabled)
        if self._puppet and hasattr(self._pet, "set_tail_boost"):
            self._pet.set_tail_boost(bool(self._settings.get("tail_boost", True)))
        if self._puppet and hasattr(self._pet, "set_lounge_variants"):
            self._pet.set_lounge_variants(bool(self._settings.get("lounge_variants", False)))
        if self._puppet and hasattr(self._pet, "set_variant_interval"):
            iv = self._settings.get("lounge_variant_interval", [40, 120])
            iv = iv if isinstance(iv, (list, tuple)) and len(iv) == 2 else (None, None)
            self._pet.set_variant_interval(*iv)
        self._lounge = LoungeDriver(self)
        self._lounge.say.connect(self.lounge_say)
        self.lounge_say.connect(self._mood_on_say)
        self._lounge.lounge.on_event = self._calib.log
        for key, attr in (("lounge_fall_gap", "fall_gap"), ("lounge_fall_follow", "fall_follow")):
            try:
                if self._settings.get(key) is not None:
                    setattr(self._lounge.lounge, attr, float(self._settings[key]))
            except (TypeError, ValueError):
                pass
        self._lounge.set_selfwalk(bool(self._settings.get("lounge_selfwalk", True)))
        self._lounge.dock_enabled = bool(self._settings.get("lounge_dock", True))
        try:
            self._lounge.dock_tol = float(self._settings.get("lounge_dock_tol", 40.0))
        except (TypeError, ValueError):
            pass
        self._apply_lounge_probe(bool(self._settings.get("lounge_ax", False)), prompt=False)
        if self._puppet and self._settings.get("lounge", False):
            self.set_lounge(True, persist=False)

        self._motion_clock = QElapsedTimer()
        self._motion_clock.start()
        self._motion_timer = QTimer(self)
        self._motion_timer.setInterval(_MOTION_INTERVAL_MS)
        self._motion_timer.timeout.connect(self._on_motion_tick)
        self._motion_timer.start()

    def _rig_choice(self, key: str) -> bool:
        """Explicit user choice wins; never chosen -> follow ``rig_auto`` (default off, so defaults are unchanged)."""
        v = self._settings.get(key)
        return bool(v) if v is not None else bool(self._settings.get("rig_auto", False))

    def _init_rig(self) -> None:
        want_rig, want_turn = self._rig_choice("part_rig"), self._rig_choice("part_turn")
        if not want_rig:
            return
        if not self.part_rig_available():
            log.warning("part rig requested but assets are missing; using pre-rendered sheets")
            return
        if not self._pet.set_part_rig(True):  # type: ignore[union-attr]
            log.warning("part rig failed to load; using pre-rendered sheets")
            return
        if want_turn:
            self._pet.set_part_turn(True)  # type: ignore[union-attr]

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
        if parse_mode(mode) is MotionMode.follow:  # legacy value: stay put + eyes follow
            mode = MotionMode.still
            self.set_look_at_mouse(True, persist=persist)
        self._motion.set_mode(mode)
        if persist:
            value = self._motion.mode.value
            self._settings["motion_mode"] = value
            config.save_settings({"motion_mode": value})

    # ---- passive eye-follow and head-pat ----


    @property
    def puppet_mode(self) -> bool:
        return self._puppet

    def apply_height(self, height: int, *, persist: bool = True) -> None:
        w, h = puppet.size_for_height(height) if self._puppet else size_for_height(height)
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
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
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

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        macwin.apply(self, on_top=self._always_on_top)

    def _keep_visible(self) -> None:
        macwin.reassert(self, on_top=self._always_on_top)

    def raise_and_activate(self) -> None:
        if self._penetrate:
            # Keep penetrate; still try to surface the window.
            pass
        # Explicit tray click / second launch: show + raise only (WA_ShowWithoutActivating + DoesNotAcceptFocus keep keyboard focus elsewhere).
        self.show()
        self.raise_()

    def play_reaction(self) -> None:
        """Schedule single-click reaction (deferred so double-click can cancel)."""
        self._click_timer.start()

    def play_jump(self) -> None:
        """Tiny vertical bob for click feedback (window + sprite procedural)."""
        self._pet.play_jump()
        if self._puppet:
            return  # puppet hops inside its own canvas
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
