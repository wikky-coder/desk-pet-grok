"""QApplication entry: tray, single-instance, pet window, chat loop."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QWidget

from desk_pet_grok import autostart, config
from desk_pet_grok.about import show_about
from desk_pet_grok.bubble import BubbleWidget
from desk_pet_grok.meow import ensure_meow
from desk_pet_grok.chat import ChatController, prompt_and_save_api_key
from desk_pet_grok.chat_panel import ChatPanel
from desk_pet_grok.menu import PetMenuCallbacks, build_pet_menu
from desk_pet_grok.screen_glue import ScreenController, populate_screen_menu
from desk_pet_grok.state import StateMachine
from desk_pet_grok.sysmon import SysMon
from desk_pet_grok.window import PRODUCT_TITLE, PetWindow

SINGLE_INSTANCE_KEY = "desk-pet-grok"


def _make_tray_icon() -> QIcon:
    """Tiny solid icon so tray works without asset files."""
    pix = QPixmap(32, 32)
    pix.fill(QColor("#5B8DEF"))
    return QIcon(pix)


class SingleInstanceGuard:
    """Best-effort single instance via QLocalServer named desk-pet-grok."""

    def __init__(self, key: str = SINGLE_INSTANCE_KEY) -> None:
        self.key = key
        self._server: QLocalServer | None = None

    def try_become_primary(self) -> bool:
        """Return True if this process owns the instance lock."""
        probe = QLocalSocket()
        probe.connectToServer(self.key)
        if probe.waitForConnected(200):
            probe.write(QByteArray(b"raise\n"))
            probe.flush()
            probe.waitForBytesWritten(200)
            probe.disconnectFromServer()
            return False

        QLocalServer.removeServer(self.key)
        server = QLocalServer()
        if not server.listen(self.key):
            return False
        self._server = server
        return True

    def on_new_connection(self, raise_cb) -> None:
        if self._server is None:
            return

        def _handle() -> None:
            assert self._server is not None
            sock = self._server.nextPendingConnection()
            if sock is None:
                return
            sock.waitForReadyRead(200)
            sock.readAll()
            sock.disconnectFromServer()
            raise_cb()

        self._server.newConnection.connect(_handle)



def _project_root() -> Path:
    """Repository / install root that contains run.py."""
    return Path(__file__).resolve().parent.parent


def _build_callbacks(
    window: PetWindow,
    sm: StateMachine,
    app: QApplication,
    chat: ChatController,
    sysmon: SysMon | None = None,
    screen=None,
) -> PetMenuCallbacks:

    def _set_autostart(enabled: bool) -> None:
        root = _project_root()
        if enabled:
            autostart.enable(root)
        else:
            autostart.disable()
        config.save_settings({"autostart": bool(enabled)})

    def quit_app() -> None:
        chat.stop_stream()
        chat.flush_memory()
        if sysmon is not None:
            sysmon.stop()
        window.close()
        chat.bubble.close()
        chat.panel.close()
        app.quit()

    return PetMenuCallbacks(
        get_height=lambda: window.height(),
        set_height=lambda h: window.apply_height(h),
        is_quiet=lambda: sm.quiet,
        set_quiet=lambda q: window.set_quiet(q),
        is_penetrate=lambda: window.penetrate,
        set_penetrate=lambda p: window.set_penetrate(p),
        is_always_on_top=lambda: window.always_on_top,
        set_always_on_top=lambda v: window.set_always_on_top(v),
        is_bubble_visible=lambda: window.bubble_visible,
        set_bubble_visible=chat.set_bubble_visible,
        get_motion_mode=lambda: window.motion_mode.value,
        set_motion_mode=lambda m: window.set_motion_mode(m),
        set_api_key=lambda: prompt_and_save_api_key(window),
        clear_chat=chat.clear_chat,
        say_line=chat.say_random_line,
        show_weather=chat.show_weather,
        show_about=lambda: show_about(window),
        is_autostart=lambda: (
            bool(config.load_settings().get("autostart"))
            or autostart.is_enabled()
        ),
        set_autostart=lambda enabled: _set_autostart(enabled),
        quit_app=quit_app,
        is_part_rig=lambda: window.part_rig,
        set_part_rig=lambda enabled: window.set_part_rig(enabled),
        part_rig_available=lambda: window.part_rig_available(),
        is_part_turn=lambda: window.part_turn,
        set_part_turn=lambda enabled: window.set_part_turn(enabled),
        is_lounge=lambda: window.lounge,
        set_lounge=lambda enabled: window.set_lounge(enabled),
        is_lounge_dock=lambda: window.lounge_dock,
        set_lounge_dock=lambda enabled: window.set_lounge_dock(enabled),
        is_lounge_selfwalk=lambda: window.lounge_selfwalk,
        set_lounge_selfwalk=lambda enabled: window.set_lounge_selfwalk(enabled),
        is_lounge_ax=lambda: window.lounge_ax,
        set_lounge_ax=lambda enabled: window.set_lounge_ax(enabled),
        is_look_at_mouse=lambda: window.look_at_mouse,
        set_look_at_mouse=lambda enabled: window.set_look_at_mouse(enabled),
        is_petting=lambda: window.petting_enabled,
        set_petting=lambda enabled: window.set_petting_enabled(enabled),
        get_petting_level=lambda: window.petting_level,
        set_petting_level=lambda level: window.set_petting_level(level),
        is_proactive=lambda: chat.proactive_talk,
        set_proactive=lambda enabled: chat.set_proactive_talk(enabled),
        is_proactive_v2=lambda: chat.proactive_v2,
        set_proactive_v2=lambda enabled: chat.set_proactive_v2(enabled),
        is_memory=lambda: chat.memory_on,
        set_memory=lambda enabled: chat.set_memory_on(enabled),
        view_memory=lambda: QMessageBox.information(window, "记忆", chat.memory_text()),
        clear_memory=lambda: (
            chat.clear_memory()
            if QMessageBox.question(window, "清除记忆", "确定清除全部记忆吗？") == QMessageBox.StandardButton.Yes
            else None
        ),
        is_tail_boost=lambda: window.tail_boost,
        set_tail_boost=lambda enabled: window.set_tail_boost(enabled),
        is_lounge_variants=lambda: window.lounge_variants,
        set_lounge_variants=lambda enabled: window.set_lounge_variants(enabled),
        is_mood=lambda: window.mood_enabled,
        set_mood=lambda enabled: window.set_mood_enabled(enabled),
        is_calibration_log=lambda: window.calibration_log,
        set_calibration_log=lambda enabled: window.set_calibration_log(enabled),
        screen_menu=(lambda m: populate_screen_menu(m, screen)) if screen is not None else None,
    )


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(PRODUCT_TITLE)
    app.setQuitOnLastWindowClosed(False)

    guard = SingleInstanceGuard()
    if not guard.try_become_primary():
        return 0

    settings = config.load_settings()
    sm = StateMachine()
    window = PetWindow(state_machine=sm, settings=settings)
    bubble = BubbleWidget()
    panel = ChatPanel()
    chat = ChatController(
        window,
        state_machine=sm,
        bubble=bubble,
        panel=panel,
        parent=app,
    )
    window.set_chat_open_checker(lambda: panel.isVisible())

    def _on_sysmon_alert(message: str) -> None:
        if sm.quiet:
            return
        if not window.bubble_visible or not window.isVisible():
            return
        bubble.show_text(ensure_meow(message))
        bubble.reposition_above(window)

    sysmon = SysMon(quiet_checker=lambda: sm.quiet, parent=app)
    sysmon.alert.connect(_on_sysmon_alert)
    sysmon.start()
    app.aboutToQuit.connect(sysmon.stop)

    screen = ScreenController(window, chat, parent=app)
    chat.screen_hook = screen.handle_chat_text
    from desk_pet_grok import screen_mac

    chat.mood_fn = window.mood_event
    chat.front_app_fn = lambda: screen_mac.front_app_name() if screen.get("screen_aware") else None

    callbacks = _build_callbacks(window, sm, app, chat, sysmon, screen)
    from desk_pet_grok.v4wire import V4

    v4 = V4(window, app, chat, bubble, panel, settings)
    callbacks.extras = tuple(v4.extras())
    panel_holder: list = []

    def open_settings() -> None:
        from desk_pet_grok import ax_probe
        from desk_pet_grok.settings_panel import SettingsPanel, build_sections

        if not panel_holder:
            panel_holder.append(SettingsPanel(build_sections(
                callbacks, ax_trusted=ax_probe.is_trusted, open_ax=ax_probe.open_accessibility_settings,
                usage_label=screen.aware.usage_label, screen=screen)))
        p = panel_holder[0]
        p.show()
        p.raise_()  # raise only; never activate (keeps the user's keyboard focus)

    callbacks.open_settings = open_settings

    def make_menu(parent: QWidget | None = None):
        return build_pet_menu(parent or window, callbacks)

    window.set_context_menu_builder(lambda: make_menu(window))

    tray_host = QWidget()
    tray = QSystemTrayIcon(_make_tray_icon(), app)
    tray.setToolTip(PRODUCT_TITLE)
    tray.setContextMenu(make_menu(tray_host))
    tray.activated.connect(
        lambda reason: (
            (v4.vis.set_manual(False), window.raise_and_activate())
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
    )
    tray.show()

    guard.on_new_connection(lambda: (v4.vis.set_manual(False), window.raise_and_activate()))
    window.show()
    v4.start()
    from desk_pet_grok import onboarding

    if onboarding.should_onboard(settings):
        guide = onboarding.OnboardingPanel(on_done=lambda: config.save_settings({"onboarded": True}))
        app._onboarding = guide  # keep alive
        guide.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
