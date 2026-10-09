"""Chat loop: history, system prompt, stream worker, controller.

Streaming uses a ``QThread`` that runs ``asyncio.run(stream_response(...))``
per request so the Qt UI thread stays responsive without adding ``qasync``.
Cancel sets a flag and closes the async generator (which closes httpx).
"""

from __future__ import annotations

import asyncio
import random
import threading
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from desk_pet_grok import config, secrets
from desk_pet_grok.lines import LineCooldown, pick_line
from desk_pet_grok.motion import MotionMode
from desk_pet_grok.api import (
    DEFAULT_MODEL,
    ApiError,
    AuthError,
    RateLimitError,
    TimeoutApiError,
    probe_api_key,
    stream_response,
)
from desk_pet_grok.bubble import BubbleWidget
from desk_pet_grok.chat_panel import ChatPanel
from desk_pet_grok.state import StateMachine
from desk_pet_grok.weather import WeatherError, fetch_weather
from desk_pet_grok.window import PRODUCT_TITLE, PetWindow

SYSTEM_PROMPT = (
    "你是用户桌面上的助手，通过 xAI API 被本机桌宠调用。\n"
    "用用户正在用的语言回答，默认中文。\n"
    "桌面气泡最多 80 个汉字或 160 个英文字符；用户明确要求展开时再写长。\n"
    "不要声称自己是 Grok 网页、Grok App 或 Grok Bot 里的同一个会话。\n"
    "不要编造已经执行过的本机操作。只有工具结果里写了成功，才能说做过。\n"
    "不要索要 API Key。"
)

HISTORY_LIMIT = 20
DONE_HOLD_MS = 1200
IDLE_CHATTER_MIN_MS = 45_000
IDLE_CHATTER_MAX_MS = 90_000
AFTER_DRAG_CHANCE = 0.45
LINE_BUBBLE_HOLD_MS = 4500

MSG_THINKING = "在想。"
MSG_NO_KEY = "还没有 API Key。右键可以填写。"
MSG_AUTH = "Key 无效。"
MSG_RATE = "请求太密，稍后再试。"
MSG_TIMEOUT = "这一轮超时了。"
MSG_GENERIC = "请求失败。"
MSG_CANCELLED = "已停止。"


def trim_history(
    messages: list[dict[str, Any]],
    *,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    """Keep the last ``limit`` non-system messages."""
    non_system = [m for m in messages if m.get("role") != "system"]
    if len(non_system) <= limit:
        return list(non_system)
    return list(non_system[-limit:])


def map_error_message(exc: BaseException) -> str:
    """Map API exceptions to user-facing Chinese copy (never echo secrets)."""
    if isinstance(exc, AuthError):
        return MSG_AUTH
    if isinstance(exc, RateLimitError):
        return MSG_RATE
    if isinstance(exc, TimeoutApiError):
        return MSG_TIMEOUT
    if isinstance(exc, ApiError):
        return MSG_GENERIC
    return MSG_GENERIC


def build_api_messages(
    history: list[dict[str, Any]],
    *,
    system: str = SYSTEM_PROMPT,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, Any]]:
    """System prompt + trimmed history for the Responses API."""
    return [{"role": "system", "content": system}, *trim_history(history, limit=limit)]


class StreamWorker(QThread):
    """Run one streamed completion off the UI thread."""

    token = Signal(str)
    completed = Signal(str)
    failed = Signal(object)
    cancelled = Signal()

    def __init__(
        self,
        messages: list[dict[str, Any]],
        api_key: str,
        *,
        model: str = DEFAULT_MODEL,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._messages = messages
        self._api_key = api_key
        self._model = model
        self._stop = threading.Event()

    def request_stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # noqa: N802
        try:
            asyncio.run(self._stream())
        except Exception as exc:  # noqa: BLE001 — marshalled to UI
            if not self._stop.is_set():
                self.failed.emit(exc)

    async def _stream(self) -> None:
        parts: list[str] = []
        agen = stream_response(
            messages=self._messages,
            api_key=self._api_key,
            model=self._model,
        )
        try:
            async for delta in agen:
                if self._stop.is_set():
                    self.cancelled.emit()
                    return
                parts.append(delta)
                self.token.emit(delta)
            if self._stop.is_set():
                self.cancelled.emit()
                return
            self.completed.emit("".join(parts))
        except Exception as exc:  # noqa: BLE001
            if self._stop.is_set():
                self.cancelled.emit()
                return
            self.failed.emit(exc)
        finally:
            aclose = getattr(agen, "aclose", None)
            if callable(aclose):
                try:
                    await aclose()
                except Exception:  # noqa: BLE001
                    pass



class WeatherWorker(QThread):
    """Fetch weather off the UI thread."""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        city: str,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._city = city

    def run(self) -> None:  # noqa: N802
        try:
            text = fetch_weather(self._city)
            self.succeeded.emit(text)
        except WeatherError as exc:
            self.failed.emit(str(exc) or "查天气失败。")
        except Exception:  # noqa: BLE001
            self.failed.emit("查天气失败，请检查网络。")


class ChatController(QObject):
    """Wires panel → state machine → stream → bubble."""

    def __init__(
        self,
        window: PetWindow,
        *,
        state_machine: StateMachine | None = None,
        bubble: BubbleWidget | None = None,
        panel: ChatPanel | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._sm = state_machine or window.state_machine
        self._bubble = bubble or BubbleWidget()
        self._panel = panel or ChatPanel()
        self._history: list[dict[str, Any]] = []
        self._worker: StreamWorker | None = None
        self._weather_worker: WeatherWorker | None = None
        self._awaiting_first_token = False
        self._partial = ""

        self._bubble.set_pref_visible(window.bubble_visible)
        self._panel.send_requested.connect(self.send_user_text)
        self._panel.stop_requested.connect(self.stop_stream)
        window.chat_requested.connect(self.open_chat)

        self._done_timer = QTimer(self)
        self._done_timer.setSingleShot(True)
        self._done_timer.timeout.connect(self._after_done_hold)

        self._line_cooldown = LineCooldown()
        self._line_rng = random.Random()
        self._line_clear_timer = QTimer(self)
        self._line_clear_timer.setSingleShot(True)
        self._line_clear_timer.timeout.connect(self._maybe_clear_line_bubble)

        self._idle_chatter_timer = QTimer(self)
        self._idle_chatter_timer.setSingleShot(True)
        self._idle_chatter_timer.timeout.connect(self._on_idle_chatter_tick)
        self._schedule_idle_chatter()

        window.pet_clicked.connect(self.on_pet_clicked)
        window.drag_finished.connect(self.on_drag_finished)

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    @property
    def bubble(self) -> BubbleWidget:
        return self._bubble

    @property
    def panel(self) -> ChatPanel:
        return self._panel

    def open_chat(self) -> None:
        self._panel.reposition_above(self._window)
        self._panel.open_panel()

    def clear_chat(self) -> None:
        self.stop_stream()
        self._history.clear()
        self._bubble.clear()
        self._partial = ""

    def set_bubble_visible(self, visible: bool) -> None:
        self._window.set_bubble_visible(visible)
        self._bubble.set_pref_visible(visible)
        if visible and self._bubble.full_text:
            self._bubble.reposition_above(self._window)

    def send_user_text(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if self._worker is not None and self._worker.isRunning():
            return

        key = secrets.get_api_key()
        if not key:
            self._sm.on_error()
            self._window.sync_pet_state()
            self._bubble.show_text(MSG_NO_KEY)
            self._bubble.reposition_above(self._window)
            return

        self._history.append({"role": "user", "content": text})
        self._history = trim_history(self._history)
        self._partial = ""
        self._awaiting_first_token = True

        self._sm.on_send()
        self._window.sync_pet_state()
        self._bubble.show_text(MSG_THINKING)
        self._bubble.reposition_above(self._window)
        self._panel.set_streaming(True)

        messages = build_api_messages(self._history)
        worker = StreamWorker(messages, key, parent=self)
        worker.token.connect(self._on_token)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def stop_stream(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_stop()

    def _on_token(self, delta: str) -> None:
        if self._awaiting_first_token:
            self._awaiting_first_token = False
            self._sm.on_first_token()
            self._window.sync_pet_state()
            self._partial = delta
            self._bubble.show_text(delta)
        else:
            self._partial += delta
            self._bubble.append_text(delta)
        self._bubble.reposition_above(self._window)

    def _on_completed(self, full: str) -> None:
        reply = full or self._partial
        if reply:
            self._history.append({"role": "assistant", "content": reply})
            self._history = trim_history(self._history)
        self._sm.on_stream_end()
        self._window.sync_pet_state()
        self._panel.set_streaming(False)
        self._done_timer.start(DONE_HOLD_MS)

    def _on_failed(self, exc: object) -> None:
        msg = map_error_message(exc if isinstance(exc, BaseException) else ApiError())
        self._sm.on_error()
        self._window.sync_pet_state()
        self._bubble.show_text(msg)
        self._bubble.reposition_above(self._window)
        self._panel.set_streaming(False)
        self._awaiting_first_token = False

    def _on_cancelled(self) -> None:
        if self._partial:
            self._history.append({"role": "assistant", "content": self._partial})
            self._history = trim_history(self._history)
            self._bubble.show_text(self._partial)
        else:
            self._bubble.show_text(MSG_CANCELLED)
        self._bubble.reposition_above(self._window)
        self._sm.on_cancel()
        self._window.sync_pet_state()
        self._panel.set_streaming(False)
        self._awaiting_first_token = False

    def _on_worker_finished(self) -> None:
        self._worker = None
        self._panel.set_streaming(False)

    def _after_done_hold(self) -> None:
        self._sm.tick_done_elapsed()
        self._window.sync_pet_state()

    # --- random lines / click interact ---------------------------------

    def _streaming(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _chat_panel_open(self) -> bool:
        return self._panel.isVisible()

    def _can_show_proactive_line(self) -> bool:
        if self._sm.quiet:
            return False
        if not self._window.bubble_visible:
            return False
        if self._chat_panel_open():
            return False
        if self._streaming():
            return False
        return True

    def show_line(
        self,
        category: str,
        *,
        jump: bool = False,
        force: bool = False,
        cooldown_key: str | None = None,
    ) -> bool:
        """Show a line in the bubble. Returns True if shown."""
        if not force and not self._window.bubble_visible:
            return False
        if self._streaming() and not force:
            return False
        key = cooldown_key or category
        if not force and not self._line_cooldown.try_acquire(key):
            return False
        if force:
            self._line_cooldown.mark(key)
        try:
            text = pick_line(category, rng=self._line_rng)
        except (KeyError, ValueError):
            return False
        self._bubble.show_text(text)
        self._bubble.reposition_above(self._window)
        self._line_clear_timer.start(LINE_BUBBLE_HOLD_MS)
        if jump:
            self._window.play_jump()
        return True

    def on_pet_clicked(self) -> None:
        """Single click (not drag): click_reply + tiny jump."""
        if self._chat_panel_open():
            return
        self.show_line("click_reply", jump=True, force=True, cooldown_key="click")

    def on_drag_finished(self) -> None:
        """Sometimes say an after_drag line."""
        if not self._can_show_proactive_line():
            return
        if self._line_rng.random() > AFTER_DRAG_CHANCE:
            return
        self.show_line("after_drag", cooldown_key="after_drag")

    def say_random_line(self) -> None:
        """Menu「说句话」: force an idle_chatter line."""
        self.show_line("idle_chatter", force=True, cooldown_key="menu_say")

    def show_weather(self) -> None:
        """Menu「查看天气」: fetch wttr.in and show bubble (QThread)."""
        if self._weather_worker is not None and self._weather_worker.isRunning():
            return
        settings = config.load_settings()
        city = str(settings.get("city") or "Hong Kong")
        self._bubble.show_text("查天气中…")
        self._bubble.reposition_above(self._window)
        worker = WeatherWorker(city, parent=self)
        worker.succeeded.connect(self._on_weather_ok)
        worker.failed.connect(self._on_weather_err)
        worker.finished.connect(self._on_weather_finished)
        self._weather_worker = worker
        worker.start()

    def _on_weather_ok(self, text: str) -> None:
        self._bubble.show_text(text)
        self._bubble.reposition_above(self._window)
        self._line_clear_timer.start(LINE_BUBBLE_HOLD_MS + 2000)

    def _on_weather_err(self, msg: str) -> None:
        self._bubble.show_text(msg)
        self._bubble.reposition_above(self._window)
        self._line_clear_timer.start(LINE_BUBBLE_HOLD_MS)

    def _on_weather_finished(self) -> None:
        self._weather_worker = None


    def _schedule_idle_chatter(self) -> None:
        delay = self._line_rng.randint(IDLE_CHATTER_MIN_MS, IDLE_CHATTER_MAX_MS)
        self._idle_chatter_timer.start(delay)

    def _on_idle_chatter_tick(self) -> None:
        try:
            mode = self._window.motion_mode
            if mode in (MotionMode.wander, MotionMode.still) and self._can_show_proactive_line():
                self.show_line("idle_chatter", cooldown_key="idle_chatter")
        finally:
            self._schedule_idle_chatter()

    def _maybe_clear_line_bubble(self) -> None:
        """Hide short interaction lines after hold; leave chat replies alone if streaming."""
        if self._streaming():
            return
        # Only clear if panel is closed — chat replies may still be on bubble.
        if self._chat_panel_open():
            return
        self._bubble.clear()


def prompt_and_save_api_key(parent: QWidget | None = None) -> None:
    """Password dialog → probe → save. UI only shows 已保存 / 未保存."""
    text, ok = QInputDialog.getText(
        parent,
        PRODUCT_TITLE,
        "xAI API Key：",
        QLineEdit.EchoMode.Password,
    )
    if not ok:
        return
    key = text.strip()
    if not key:
        QMessageBox.information(parent, PRODUCT_TITLE, "未保存")
        return
    try:
        probe_api_key(key)
    except AuthError:
        QMessageBox.warning(parent, PRODUCT_TITLE, f"未保存\n{MSG_AUTH}")
        return
    except RateLimitError:
        QMessageBox.warning(parent, PRODUCT_TITLE, f"未保存\n{MSG_RATE}")
        return
    except TimeoutApiError:
        QMessageBox.warning(parent, PRODUCT_TITLE, f"未保存\n{MSG_TIMEOUT}")
        return
    except ApiError:
        QMessageBox.warning(parent, PRODUCT_TITLE, f"未保存\n{MSG_GENERIC}")
        return
    except Exception:  # noqa: BLE001
        QMessageBox.warning(parent, PRODUCT_TITLE, f"未保存\n{MSG_GENERIC}")
        return

    secrets.set_api_key(key)
    QMessageBox.information(parent, PRODUCT_TITLE, "已保存")
