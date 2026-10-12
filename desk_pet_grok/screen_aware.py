"""Screen awareness decision logic (pure, no Qt / no platform calls; every dependency is injected).

Tier 1 reads the front app name / window title (free). Tier 2 takes a downsized screenshot and asks the vision API for a
short catgirl remark (costs quota). Nothing here logs, stores or transmits screenshots or window titles."""

from __future__ import annotations

import io
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from desk_pet_grok.meow import ensure_meow

DEFAULT_LIMIT_HOUR = 3
DEFAULT_LIMIT_DAY = 20
PROACTIVE_GAP_S = 20 * 60
PROACTIVE_DWELL_S = 15 * 60
CONTEXT_GAP_S = 10 * 60
CONTEXT_CAT_GAP_S = 30 * 60
SAME_FRAME_DIFF = 6.0

DEFAULT_BLACKLIST: tuple[str, ...] = (
    # password managers / keychains
    "1password", "bitwarden", "keepass", "lastpass", "dashlane", "keychain", "钥匙串", "密码",
    # banking / payment
    "银行", "bank", "支付宝", "alipay", "paypal", "支付", "网银", "证券", "wallet",
    # chat / private messaging
    "微信", "wechat", "weixin", "qq", "telegram", "whatsapp", "signal", "slack", "钉钉", "dingtalk",
    "飞书", "lark", "messages", "信息", "discord", "line", "imessage",
)

_VIDEO_APPS = ("iina", "vlc", "quicktime", "infuse", "potplayer", "mpv", "netflix", "bilibili", "哔哩", "tv", "电视")
_VIDEO_TITLES = ("youtube", "netflix", "bilibili", "哔哩哔哩", "twitch", "disney+", "爱奇艺", "腾讯视频", "优酷")
_CODE_APPS = ("code", "cursor", "xcode", "pycharm", "intellij", "webstorm", "sublime", "vim", "zed", "android studio", "nova", "textmate")
_TERM_APPS = ("terminal", "iterm", "warp", "ghostty", "kitty", "alacritty", "终端")
_BROWSER_APPS = ("safari", "chrome", "firefox", "edge", "arc", "brave", "opera", "浏览器")
_CHAT_APPS = ("微信", "wechat", "qq", "telegram", "whatsapp", "slack", "钉钉", "飞书", "discord", "messages", "信息", "line")
_DOC_APPS = ("pages", "word", "notion", "obsidian", "notes", "备忘录", "typora", "numbers", "excel", "keynote", "powerpoint", "preview", "预览", "bear", "wps")
_DESIGN_APPS = ("figma", "sketch", "photoshop", "illustrator", "blender", "procreate", "affinity", "final cut", "premiere")
_GAME_APPS = ("steam", "minecraft", "genshin", "原神", "league", "battle.net", "epic games")


def _has(hay: str, needles: Sequence[str]) -> bool:
    h = hay.lower()
    return any(n and n.lower() in h for n in needles)


def classify_app(app: str, title: str = "") -> str:
    """Return code / terminal / video / browser / chat / doc / design / game / other."""
    if _has(app, _VIDEO_APPS):
        return "video"
    if _has(app, _CODE_APPS):
        return "code"
    if _has(app, _TERM_APPS):
        return "terminal"
    if _has(app, _CHAT_APPS):
        return "chat"
    if _has(app, _BROWSER_APPS):
        return "video" if _has(title, _VIDEO_TITLES) else "browser"
    if _has(app, _DESIGN_APPS):
        return "design"
    if _has(app, _GAME_APPS):
        return "game"
    if _has(app, _DOC_APPS):
        return "doc"
    return "other"


def is_blacklisted(app: str, title: str, blacklist: Optional[Sequence[str]]) -> bool:
    """A custom list replaces the default one. Matches are case-insensitive substrings of app name or window title."""
    words = DEFAULT_BLACKLIST if blacklist is None else tuple(blacklist)
    return _has(app, words) or _has(title, words)


def _day_key(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


class UsageLimiter:
    """Per-hour (sliding) and per-day (local calendar) call budget; state lives in the given dict (persisted by caller)."""

    def __init__(self, store: dict, hour: int = DEFAULT_LIMIT_HOUR, day: int = DEFAULT_LIMIT_DAY,
                 on_change: Callable[[], None] | None = None) -> None:
        self.store = store
        self.hour = max(0, int(hour))
        self.day = max(0, int(day))
        self._on_change = on_change

    def _roll(self, now: float) -> None:
        dk = _day_key(now)
        if self.store.get("day") != dk:
            self.store["day"] = dk
            self.store["count"] = 0
        self.store["stamps"] = [t for t in self.store.get("stamps", []) if now - t < 3600 and t <= now + 60]

    def today_count(self, now: float) -> int:
        self._roll(now)
        return int(self.store.get("count", 0))

    def hour_count(self, now: float) -> int:
        self._roll(now)
        return len(self.store["stamps"])

    def check(self, now: float) -> str:
        self._roll(now)
        if self.store["count"] >= self.day:
            return "day_limit"
        if len(self.store["stamps"]) >= self.hour:
            return "hour_limit"
        return "ok"

    def record(self, now: float) -> None:
        self._roll(now)
        self.store["count"] = int(self.store.get("count", 0)) + 1
        self.store["stamps"].append(now)
        if self._on_change:
            self._on_change()


def is_quiet_hours(now: float, enabled: bool, start_h: int = 22, end_h: int = 8) -> bool:
    if not enabled:
        return False
    h = time.localtime(now).tm_hour
    if start_h == end_h:
        return False
    return (h >= start_h or h < end_h) if start_h > end_h else (start_h <= h < end_h)


def is_paused(now: float, pause_until: float) -> bool:
    return now < float(pause_until or 0)


def frame_signature(jpeg: bytes) -> Optional[tuple[int, ...]]:
    """16x16 grayscale thumbnail, or None if Pillow is missing / bytes are not an image."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(jpeg)) as im:
            return tuple(im.convert("L").resize((16, 16)).tobytes())
    except Exception:  # noqa: BLE001
        return None


def similar(a: Optional[Sequence[int]], b: Optional[Sequence[int]], thresh: float = SAME_FRAME_DIFF) -> bool:
    if a is None or b is None or len(a) != len(b) or not a:
        return False
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a) < thresh


_LOOK_RE = re.compile(
    r"(你|帮我|给我|替我)?.{0,2}看(一下|一眼|看|下)?.{0,3}(我的?)?(屏幕|桌面)"
    r"|看看?我在(干嘛|干什么|做什么|忙什么)|你看我在(干嘛|干什么|做什么)"
)


def is_look_request(text: str) -> bool:
    return bool(_LOOK_RE.search(text.strip()))


# --- lines (original, short, every sentence ends with 喵; self = 本喵 / sometimes Wiki; user = 主人) ---
CONTEXT_LINES: dict[str, tuple[str, ...]] = {
    "code": ("主人写代码辛苦啦，本喵安静陪着喵。", "代码要加油哦，Wiki 不吵你喵。"),
    "browser": ("主人在逛网页呀，别看太久喵。", "本喵也想看看网页上有什么喵。", "网页开太多标签会累喵。"),
    "chat": ("主人在聊天呀，本喵不偷看喵。", "和朋友聊天要开心哦喵。"),
    "doc": ("主人在写东西呀，本喵给你加油喵。", "文档慢慢写，Wiki 陪着你喵。"),
}
CONTEXT_PROB: dict[str, float] = {"code": 0.05, "browser": 0.5, "chat": 0.4, "doc": 0.4}

STATUS_LINES: dict[str, str] = {
    "disabled": "主人，先在菜单里打开「屏幕感知」本喵才能看喵。",
    "vision_off": "主人，要本喵截屏看的话，请在菜单里打开「允许截屏看」喵。",
    "no_permission": "本喵还没有屏幕录制权限，请主人在系统设置里点一下授权喵。",
    "no_key": "本喵没找到 API Key，请主人设置环境变量 XAI_API_KEY 喵。",
    "hour_limit": "这个小时本喵已经看够啦，等一会儿再看喵。",
    "day_limit": "今天本喵看屏幕的次数用完啦，明天再看喵。",
    "blacklisted": "这个软件本喵不看的，保护主人的隐私喵。",
    "secure": "主人在输入密码呢，本喵不看喵。",
    "fullscreen": "主人在全屏呢，本喵不打扰也不偷看喵。",
    "video": "主人在看视频，本喵安静陪着不截屏喵。",
    "paused": "本喵正在专注暂停中，先不看屏幕喵。",
    "quiet": "现在是安静时段，本喵不看屏幕喵。",
    "capture_failed": "本喵没截到屏幕，等下再试试喵。",
    "no_context": "本喵现在看不出主人在用什么软件喵。",
    "error": "本喵这次没看清，晚点再试喵。",
}


@dataclass
class FrontContext:
    app: str
    title: str = ""
    fullscreen: bool = False
    secure: bool = False  # focus is in a password field


@dataclass
class LookResult:
    status: str
    text: str = ""


class ScreenAwareness:
    def __init__(
        self,
        *,
        settings: dict,
        save: Callable[[dict], None],
        get_context: Callable[[], Optional[FrontContext]],
        capture: Callable[[], Optional[bytes]],
        describe: Callable[[bytes], str],
        has_permission: Callable[[], bool],
        has_key: Callable[[], bool],
        signature: Callable[[bytes], Any] = frame_signature,
        clock: Callable[[], float] = time.time,
        rng: random.Random | None = None,
    ) -> None:
        self.settings = settings
        self._save = save
        self._get_context = get_context
        self._capture = capture
        self._describe = describe
        self._has_permission = has_permission
        self._has_key = has_key
        self._signature = signature
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_look = 0.0
        self._last_sig: Any = None
        self._last_look_app: Optional[str] = None
        self._cur_app: Optional[str] = None
        self._cur_since = 0.0
        self._ctx_app: Optional[str] = None
        self._ctx_last_any = -1e18
        self._ctx_last_cat: dict[str, float] = {}

    # --- settings helpers ---
    def _flag(self, key: str) -> bool:
        return bool(self.settings.get(key))

    def _limiter(self) -> UsageLimiter:
        usage = self.settings.get("screen_usage")
        if not isinstance(usage, dict):
            usage = {}
            self.settings["screen_usage"] = usage
        return UsageLimiter(
            usage,
            hour=self.settings.get("screen_limit_hour", DEFAULT_LIMIT_HOUR),
            day=self.settings.get("screen_limit_day", DEFAULT_LIMIT_DAY),
            on_change=lambda: self._save({"screen_usage": self.settings["screen_usage"]}),
        )

    def usage_label(self) -> str:
        lim = self._limiter()
        now = self._clock()
        return f"今日已用 {lim.today_count(now)}/{lim.day} 次 · 本小时 {lim.hour_count(now)}/{lim.hour}"

    def _blocked(self, now: float) -> Optional[str]:
        if is_paused(now, self.settings.get("screen_pause_until", 0)):
            return "paused"
        if is_quiet_hours(now, self._flag("screen_quiet_hours")):
            return "quiet"
        return None

    # --- tier 1 ---
    def context_line(self) -> Optional[str]:
        """Called periodically. Speaks only when the front app changed; code/video/terminal/design/game stay (almost) silent."""
        if not self._flag("screen_aware"):
            return None
        now = self._clock()
        ctx = self._get_context()
        if ctx is None:
            return None
        changed = ctx.app != self._ctx_app
        self._ctx_app = ctx.app
        if not changed or self._blocked(now):
            return None
        if is_blacklisted(ctx.app, ctx.title, self.settings.get("screen_blacklist")) or ctx.secure or ctx.fullscreen:
            return None
        cat = classify_app(ctx.app, ctx.title)
        lines = CONTEXT_LINES.get(cat)
        if not lines:
            return None
        if now - self._ctx_last_any < CONTEXT_GAP_S or now - self._ctx_last_cat.get(cat, -1e18) < CONTEXT_CAT_GAP_S:
            return None
        if self._rng.random() >= CONTEXT_PROB.get(cat, 0.0):
            return None
        self._ctx_last_any = now
        self._ctx_last_cat[cat] = now
        return ensure_meow(self._rng.choice(lines))

    # --- tier 2 ---
    def _enabled_proactive(self) -> bool:
        return self._flag("screen_aware") and self._flag("screen_vision") and self._flag("screen_proactive")

    def proactive_due(self) -> bool:
        if not self._enabled_proactive():
            return False
        now = self._clock()
        ctx = self._get_context()
        if ctx is None:
            return False
        if ctx.app != self._cur_app:
            self._cur_app, self._cur_since = ctx.app, now
        if self._blocked(now) or now - self._last_look < PROACTIVE_GAP_S:
            return False
        if self._limiter().check(now) != "ok":
            return False
        return ctx.app != self._last_look_app or now - self._cur_since >= PROACTIVE_DWELL_S

    def look(self, *, manual: bool) -> LookResult:
        def stop(status: str) -> LookResult:
            return LookResult(status, STATUS_LINES.get(status, ""))

        if not self._flag("screen_aware"):
            return stop("disabled")
        if not self._flag("screen_vision"):
            return stop("vision_off")
        if not manual and not self._flag("screen_proactive"):
            return LookResult("proactive_off", "")
        ctx = self._get_context()
        if ctx is None:
            return stop("no_context")
        now = self._clock()
        why = self._blocked(now)
        if why:
            return stop(why)
        if is_blacklisted(ctx.app, ctx.title, self.settings.get("screen_blacklist")):
            return stop("blacklisted")
        if ctx.secure:
            return stop("secure")
        if ctx.fullscreen:
            return stop("fullscreen")
        if classify_app(ctx.app, ctx.title) == "video":
            return stop("video")
        if not self._has_permission():
            return stop("no_permission")
        if not self._has_key():
            return stop("no_key")
        lim = self._limiter()
        lim_status = lim.check(now)
        if lim_status != "ok":
            return stop(lim_status)
        jpeg = self._capture()
        if not jpeg:
            return stop("capture_failed")
        sig = self._signature(jpeg)
        if not manual and similar(sig, self._last_sig):
            return LookResult("same_frame", "")
        lim.record(now)
        self._last_look = now
        self._last_look_app = ctx.app
        self._last_sig = sig
        try:
            text = self._describe(jpeg)
        except Exception:  # noqa: BLE001 - never leak details (could contain secrets)
            return stop("error")
        finally:
            del jpeg  # in-memory only
        text = ensure_meow((text or "").strip())
        return LookResult("ok", text) if text else stop("error")
