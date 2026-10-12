"""Chat loop: history, system prompt, stream worker, controller.

Streaming uses a ``QThread`` that runs ``asyncio.run(stream_response(...))``
per request so the Qt UI thread stays responsive without adding ``qasync``.
Cancel sets a flag and closes the async generator (which closes httpx).
"""

from __future__ import annotations

import asyncio
import random
import time
import threading
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QWidget

from desk_pet_grok import lines_v4  # noqa: F401  (registers the v4 event pools)
from desk_pet_grok import config, secrets
from desk_pet_grok.meow import ensure_meow
from desk_pet_grok.memory import SUMMARY_PROMPT, MemoryStore, transcript_for_summary
from desk_pet_grok.proactive import EVENT_LINES, EventDetector, Scheduler
from desk_pet_grok.lines import (
    LONG_IDLE_LEVELS,
    LineCooldown,
    is_rapid_click,
    long_idle_level,
    pick_line,
)
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
    "你是一只金发猫娘女仆，名叫小 Grok。自称「本喵」，偶尔也用「Wiki」称呼自己；称呼用户为「主人」。\n"
    "说话软萌、简短、口语化，像在耳边轻声说；颜文字只偶尔用，认真问题先把答案说清楚。\n"
    "不涉及任何暧昧或亲密内容，保持女仆式的体贴与分寸。\n"
    "每一句话都以「喵」结尾（放在句末标点之前，例如「好的喵。」「要不要试试喵？」），包括列表项和问句；代码块、命令和链接除外。\n"
    "桌面气泡最多 80 个汉字或 160 个英文字符，尽量每句不超过 24 个字；用户明确要求展开时再写长。\n"
    "不要声称自己是 Grok 网页、Grok App 或 Grok Bot 里的同一个会话。\n"
    "不要编造已经执行过的本机操作。只有工具结果里写了成功，才能说做过。\n"
    "不要索要 API Key。"
)

ANGER_PROMPT = ("\n现在本喵在生气（刚被主人甩晕了，还没被摸头哄好）：回复要带赌气口吻（哼、不太想理主人），"
                "但不失礼，仍然称呼主人、自称本喵、句尾带喵，认真的问题照样回答。\n")

HISTORY_LIMIT = 20
DONE_HOLD_MS = 1200
IDLE_CHATTER_MIN_MS = 45_000
IDLE_CHATTER_MAX_MS = 90_000
AFTER_DRAG_CHANCE = 0.45
LINE_BUBBLE_HOLD_MS = 4500
NEGLECT_S = 1200.0  # left alone this long -> a pouty mood event (only when the mood switch is on)
PAT_SPOIL_COUNT = 3  # this many head-pats within the window -> one spoiled line
PAT_SPOIL_WINDOW_S = 600.0

BOOT_DELAY_MS = 2500
SLOW_TICK_MS = 30_000  # long_idle / top_of_hour check
EDGE_MARGIN_PX = 12
EDGE_CHANCE = 0.35

MSG_THINKING = "本喵在想喵。"
MSG_NO_KEY = "还没有 API Key，右键可以填写喵。"
MSG_AUTH = "Key 好像无效喵。"
MSG_RATE = "请求太密，等一下再试喵。"
MSG_TIMEOUT = "这一轮超时了喵。"
MSG_GENERIC = "请求没成功喵。"
MSG_CANCELLED = "已停下来了喵。"


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

    screen_hook = None  # optional callable(text) -> bool, set by app (screen awareness)

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

        st = getattr(window, "_settings", None) or {}
        self._proactive_talk = bool(st.get("proactive_talk", True))  # off = silent unless the user triggers a line
        self._sched = Scheduler(
            enabled=bool(st.get("proactive_v2", False)),
            max_per_hour=int(st.get("proactive_max_per_hour", 3) or 3),
            min_gap_s=float(st.get("proactive_min_gap_s", 300.0) or 300.0),
        )
        self._events = EventDetector()
        self._memory_on = bool(st.get("memory", False))  # cross-session memory: off by default (it sends summaries to the API)
        self._memory: MemoryStore | None = None
        self._pending_mem: list[dict[str, Any]] = []  # messages not summarised yet
        self._sum_worker: StreamWorker | None = None
        self._pat_times: list[float] = []
        self.anger_fn = None  # optional callable() -> int: her anger stage (0 = calm); while > 0 every line is an angry one
        self.hidden_fn = None  # optional callable() -> bool (set by app: the pet is hidden)
        self.front_app_fn = None  # optional callable() -> str | None (set by app when screen_aware is on)
        self.cursor_fn = None  # optional callable() -> (x, y); defaults to QCursor
        self._bubble.set_pref_visible(window.bubble_visible)
        self._panel.send_requested.connect(self.send_user_text)
        self._panel.stop_requested.connect(self.stop_stream)
        window.chat_requested.connect(self.open_chat)

        self._done_timer = QTimer(self)
        self._done_timer.setSingleShot(True)
        self._done_timer.timeout.connect(self._after_done_hold)

        self._line_cooldown = LineCooldown()
        self._extra_last: dict[str, float] = {}
        self._line_rng = random.Random()
        self._line_clear_timer = QTimer(self)
        self._line_clear_timer.setSingleShot(True)
        self._line_clear_timer.timeout.connect(self._maybe_clear_line_bubble)

        self._idle_chatter_timer = QTimer(self)
        self._idle_chatter_timer.setSingleShot(True)
        self._idle_chatter_timer.timeout.connect(self._on_idle_chatter_tick)
        self._schedule_idle_chatter()

        self._click_times: list[float] = []
        self._neglect_at = 0.0
        self.mood_fn = None  # window.mood_event (F6); None = no mood layer
        self._last_activity = time.monotonic()
        self._idle_level_shown = 0
        self._last_hour_said = -1
        self._slow_timer = QTimer(self)
        self._slow_timer.timeout.connect(self._on_slow_tick)
        self._slow_timer.start(SLOW_TICK_MS)
        QTimer.singleShot(BOOT_DELAY_MS, self._say_boot)

        window.pet_clicked.connect(self.on_pet_clicked)
        window.drag_finished.connect(self.on_drag_finished)
        window.lounge_say.connect(self.on_lounge_say)

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
        self._maybe_summarize(min_msgs=2)
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
        if self.screen_hook is not None and self.screen_hook(text):
            return  # 「你看我屏幕」 etc. handled by screen awareness
        if self._worker is not None and self._worker.isRunning():
            return

        key = secrets.get_api_key()
        if not key:
            self._sm.on_error()
            self._window.sync_pet_state()
            self._bubble.show_text(MSG_NO_KEY)
            self._bubble.reposition_above(self._window)
            return

        self.note_activity()
        self._history.append({"role": "user", "content": text})
        if self._memory_on:
            self._pending_mem.append({"role": "user", "content": text})
        self._history = trim_history(self._history)
        self._partial = ""
        self._awaiting_first_token = True

        self._sm.on_send()
        self._window.sync_pet_state()
        self._bubble.show_text(MSG_THINKING)
        self._bubble.reposition_above(self._window)
        self._panel.set_streaming(True)

        messages = build_api_messages(self._history, system=self._system_prompt())
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
            if self._memory_on:
                self._pending_mem.append({"role": "assistant", "content": reply})
                self._maybe_summarize(min_msgs=8)
            self._history = trim_history(self._history)
            # display-only 喵 rule: history keeps the model's original text
            shown = ensure_meow(reply)
            if shown != self._bubble.full_text:
                self._bubble.show_text(shown)
                self._bubble.reposition_above(self._window)
        self._sm.on_stream_end()
        self._window.sync_pet_state()
        self._panel.set_streaming(False)
        self._done_timer.start(DONE_HOLD_MS)

    def _on_failed(self, exc: object) -> None:
        msg = map_error_message(exc if isinstance(exc, BaseException) else ApiError())
        self._sm.on_error()
        self._window.sync_pet_state()
        try:
            lead = pick_line("error", rng=self._line_rng)
        except (KeyError, ValueError):
            lead = ""
        self._bubble.show_text(f"{lead}{msg}" if lead else msg)
        self._bubble.reposition_above(self._window)
        self._panel.set_streaming(False)
        self._awaiting_first_token = False

    def _on_cancelled(self) -> None:
        if self._partial:
            self._history.append({"role": "assistant", "content": self._partial})
            self._history = trim_history(self._history)
            self._bubble.show_text(ensure_meow(self._partial))
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

    # ---- F4 memory ----
    @property
    def memory(self) -> MemoryStore:
        if self._memory is None:
            self._memory = MemoryStore()
        return self._memory

    @property
    def memory_on(self) -> bool:
        return self._memory_on

    def set_memory_on(self, on: bool, *, persist: bool = True) -> None:
        self._memory_on = bool(on)
        if not on:
            self._pending_mem.clear()
        if persist:
            config.save_settings({"memory": bool(on)})

    def memory_text(self) -> str:
        m = self.memory
        if m.empty:
            return "（还没有记忆）"
        rows = ["【我记得的事】"] + ["· " + f for f in m.facts] + ["", "【最近聊过】"] + ["· " + r["s"] for r in m.recent]
        return "\n".join(rows)

    def clear_memory(self) -> None:
        self.memory.clear()
        self._pending_mem.clear()

    def _angry(self) -> bool:
        try:
            return bool(self.anger_fn is not None and int(self.anger_fn()) > 0)
        except Exception:  # noqa: BLE001
            return False

    def _system_prompt(self) -> str:
        base = SYSTEM_PROMPT + (ANGER_PROMPT if self._angry() else "")
        if not self._memory_on:
            return base
        try:
            return base + self.memory.prompt_block()
        except Exception:  # noqa: BLE001 - memory must never break chatting
            return base

    def _maybe_summarize(self, *, min_msgs: int) -> bool:
        """Summarise the not-yet-remembered messages with ONE model call (<= 5/day). Returns whether a call started."""
        if not self._memory_on or len(self._pending_mem) < min_msgs:
            return False
        if self._sum_worker is not None and self._sum_worker.isRunning():
            return False
        key = secrets.get_api_key()
        mem = self.memory
        if not key or not mem.can_summarize():
            return False
        transcript = transcript_for_summary(self._pending_mem)
        self._pending_mem = []
        mem.note_summary_call()
        msgs = [{"role": "system", "content": SUMMARY_PROMPT}, {"role": "user", "content": transcript}]
        w = StreamWorker(msgs, key, parent=self)
        w.completed.connect(lambda reply: mem.apply_summary_reply(reply))
        self._sum_worker = w
        w.start()
        return True

    def flush_memory(self, wait_ms: int = 4000) -> None:
        """On quit: best-effort summary of what is left, waiting briefly for it."""
        if self._maybe_summarize(min_msgs=2) and self._sum_worker is not None:
            self._sum_worker.wait(wait_ms)

    @property
    def proactive_talk(self) -> bool:
        return self._proactive_talk

    def set_proactive_talk(self, on: bool, *, persist: bool = True) -> None:
        self._proactive_talk = bool(on)
        if persist:
            config.save_settings({"proactive_talk": bool(on)})

    @property
    def proactive_v2(self) -> bool:
        return self._sched.enabled

    def set_proactive_v2(self, on: bool, *, persist: bool = True) -> None:
        self._sched.enabled = bool(on)
        if persist:
            config.save_settings({"proactive_v2": bool(on)})

    def _proactive_gate(self) -> bool:
        """Every UNPROMPTED line asks here (user-triggered click / pat / fall lines do not)."""
        if not self._proactive_talk or not self._can_show_proactive_line():
            return False
        return self._sched.acquire(time.monotonic())

    def show_line(
        self,
        category: str,
        *,
        jump: bool = False,
        force: bool = False,
        cooldown_key: str | None = None,
    ) -> bool:
        """Show a line in the bubble. Returns True if shown."""
        if self.hidden_fn is not None and self.hidden_fn():
            return False  # the pet is hidden (手动 / 全屏): never talk to nobody
        if not force and not self._window.bubble_visible:
            return False
        if self._streaming() and not force:
            return False
        if self._angry():  # angry: ordinary chatter / cute lines are replaced by angry ones of the matching kind
            category = lines_v4.angry_equivalent(category)
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

    def _mood(self, kind: str) -> None:
        if self.mood_fn is not None:
            self.mood_fn(kind)

    def on_pet_clicked(self) -> None:
        """Single click (not drag): click_reply + tiny jump."""
        if self._chat_panel_open():
            return
        now = time.monotonic()
        self.note_activity()
        self._click_times = [t for t in self._click_times if now - t <= 10.0] + [now]
        if is_rapid_click(self._click_times, now):
            self._mood("poke")
        else:
            self._mood("activity")
        if is_rapid_click(self._click_times, now) and self._line_cooldown_ok("rapid_clicks", 8.0, now):
            self._click_times.clear()
            self.show_line("rapid_clicks", jump=False, force=True, cooldown_key="rapid_clicks")
            return
        self.show_line("click_reply", jump=True, force=True, cooldown_key="click")

    def on_drag_finished(self) -> None:
        """Sometimes say an after_drag line (or a screen_edge line when dropped against the edge)."""
        self.note_activity()
        if not self._can_show_proactive_line():
            return
        if self._near_screen_edge() and self._line_rng.random() < EDGE_CHANCE:
            if self.show_line("screen_edge", cooldown_key="screen_edge"):
                return
        if self._line_rng.random() > AFTER_DRAG_CHANCE:
            return
        self.show_line("after_drag", cooldown_key="after_drag")

    # --- extra triggers (all gated by _can_show_proactive_line + cooldowns) ---

    def note_activity(self) -> None:
        self._last_activity = time.monotonic()
        self._idle_level_shown = 0

    def _line_cooldown_ok(self, key: str, seconds: float, now: float) -> bool:
        last = self._extra_last.get(key)
        if last is not None and now - last < seconds:
            return False
        self._extra_last[key] = now
        return True

    def _near_screen_edge(self) -> bool:
        try:
            screen = self._window.screen()
            if screen is None:
                return False
            ar = screen.availableGeometry()
            g = self._window.frameGeometry()
            m = EDGE_MARGIN_PX
            return g.left() <= ar.left() + m or g.right() >= ar.right() - m
        except Exception:  # noqa: BLE001
            return False

    def on_lounge_say(self, category: str) -> None:
        """Low-voice lines while lounging (all end with 喵); never while chatting/streaming."""
        if category in lines_v4.EVENT_CATEGORIES:  # v4 events (shake anger ...): a reply to what she was just doing
            if self._can_show_proactive_line():
                self.show_line(category, force=True, cooldown_key=category)
            return
        if category in ("pet_head", "pet_fall"):
            # head-pat / fall exclamations: own cooldown (pat lines at most once per 20 s)
            now = time.monotonic()
            if self._can_show_proactive_line() and self._line_cooldown_ok(category, 20.0 if category == "pet_head" else 6.0, now):
                if category == "pet_head":  # pats keep coming: switch to the "spoiled" lines (user-triggered, not budgeted)
                    self._pat_times = [t for t in self._pat_times if now - t <= PAT_SPOIL_WINDOW_S] + [now]
                    if len(self._pat_times) >= PAT_SPOIL_COUNT:
                        self._pat_times.clear()
                        category = "pat_spoil"
                self.show_line(category, force=True, cooldown_key=category)
            return
        if category not in ("lounge_start", "lounge", "yawn", "lounge_sleep", "lounge_end", "self_walk"):
            return
        if category == "lounge_start":  # she was just dropped on an edge by the user: a reply, not unprompted
            if self._can_show_proactive_line():
                self.show_line(category, cooldown_key=category)
            return
        if self._can_show_proactive_line() and self._line_cooldown.ready(category) and self._proactive_gate():
            self.show_line(category, cooldown_key=category)

    def _say_boot(self) -> None:
        if self._proactive_talk and self._can_show_proactive_line():  # startup greeting: not counted in the hourly budget
            self.show_line("boot", cooldown_key="boot")

    def _on_slow_tick(self) -> None:
        """long_idle (escalating, once per level), top_of_hour, and the v2 local events (app switch / long use / back)."""
        now = time.monotonic()
        if self._pending_mem and now - self._last_activity > 600.0 and not self._streaming():
            self._maybe_summarize(min_msgs=2)  # she has been left alone for 10 min: remember the chat so far
        self._poll_events(now)
        if now - self._last_activity > NEGLECT_S and now - self._neglect_at > NEGLECT_S:
            self._neglect_at = now
            self._mood("neglect")
        if not self._can_show_proactive_line() or not self._proactive_talk:
            return
        lvl = long_idle_level(now - self._last_activity)
        if lvl > self._idle_level_shown:
            if self._proactive_gate():
                self._idle_level_shown = lvl
                self.show_line(LONG_IDLE_LEVELS[lvl - 1], cooldown_key="long_idle")
            return
        lt = time.localtime()
        if lt.tm_min == 0 and lt.tm_hour != self._last_hour_said and self._proactive_gate():
            self._last_hour_said = lt.tm_hour
            self._show_templated("top_of_hour", hour=lt.tm_hour)

    def _poll_events(self, now: float) -> None:
        """Only when v2 is on: local events (no quota) -> at most one line, through the scheduler."""
        if not self._sched.enabled:
            return
        cur = None
        try:
            if self.cursor_fn is not None:
                cur = tuple(self.cursor_fn())
            else:
                from PySide6.QtGui import QCursor

                p = QCursor.pos()
                cur = (float(p.x()), float(p.y()))
        except Exception:  # noqa: BLE001
            cur = None
        app = None
        if self.front_app_fn is not None:
            try:
                app = self.front_app_fn()
            except Exception:  # noqa: BLE001
                app = None
        for kind in self._events.tick(now, cur, app):
            if self._proactive_gate():
                self.show_line(EVENT_LINES[kind], cooldown_key=kind, force=True)
                return

    def _show_templated(self, category: str, **fmt: object) -> bool:
        if self._angry():
            category, fmt = "anger_idle", {}
        try:
            text = pick_line(category, rng=self._line_rng, **fmt)
        except (KeyError, ValueError):
            return False
        self._bubble.show_text(text)
        self._bubble.reposition_above(self._window)
        self._line_clear_timer.start(LINE_BUBBLE_HOLD_MS)
        return True

    def say_random_line(self) -> None:
        """Menu「说句话」: force an idle_chatter line."""
        self.show_line("idle_chatter", force=True, cooldown_key="menu_say")

    def show_weather(self) -> None:
        """Menu「查看天气」: fetch wttr.in and show bubble (QThread)."""
        if self._weather_worker is not None and self._weather_worker.isRunning():
            return
        settings = config.load_settings()
        city = str(settings.get("city") or "Hong Kong")
        self._bubble.show_text("查天气中喵…")
        self._bubble.reposition_above(self._window)
        worker = WeatherWorker(city, parent=self)
        worker.succeeded.connect(self._on_weather_ok)
        worker.failed.connect(self._on_weather_err)
        worker.finished.connect(self._on_weather_finished)
        self._weather_worker = worker
        worker.start()

    def _on_weather_ok(self, text: str) -> None:
        try:
            lead = pick_line("weather_change", rng=self._line_rng)
        except (KeyError, ValueError):
            lead = ""
        self._bubble.show_text(ensure_meow(f"{lead}\n{text}" if lead else text))
        self._bubble.reposition_above(self._window)
        self._line_clear_timer.start(LINE_BUBBLE_HOLD_MS + 2000)

    def _on_weather_err(self, msg: str) -> None:
        self._bubble.show_text(ensure_meow(msg))
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
            if mode in (MotionMode.wander, MotionMode.still) and self._line_cooldown.ready("idle_chatter") and self._proactive_gate():
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
