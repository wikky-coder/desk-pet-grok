"""QApplication entry: tray, single-instance, pet window, chat loop."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget

from desk_pet_grok import autostart, config
from desk_pet_grok.about import show_about
from desk_pet_grok.bubble import BubbleWidget
from desk_pet_grok.chat import ChatController, prompt_and_save_api_key
from desk_pet_grok.chat_panel import ChatPanel
from desk_pet_grok.menu import PetMenuCallbacks, build_pet_menu
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
        if not window.bubble_visible:
            return
        bubble.show_text(message)
        bubble.reposition_above(window)

    sysmon = SysMon(quiet_checker=lambda: sm.quiet, parent=app)
    sysmon.alert.connect(_on_sysmon_alert)
    sysmon.start()
    app.aboutToQuit.connect(sysmon.stop)

    callbacks = _build_callbacks(window, sm, app, chat, sysmon)

    def make_menu(parent: QWidget | None = None):
        return build_pet_menu(parent or window, callbacks)

    window.set_context_menu_builder(lambda: make_menu(window))

    tray_host = QWidget()
    tray = QSystemTrayIcon(_make_tray_icon(), app)
    tray.setToolTip(PRODUCT_TITLE)
    tray.setContextMenu(make_menu(tray_host))
    tray.activated.connect(
        lambda reason: (
            window.raise_and_activate()
            if reason == QSystemTrayIcon.ActivationReason.Trigger
            else None
        )
    )
    tray.show()

    guard.on_new_connection(window.raise_and_activate)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
