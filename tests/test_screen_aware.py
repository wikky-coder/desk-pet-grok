import random
import time

import pytest

from desk_pet_grok import screen_aware as sa
from desk_pet_grok.meow import ends_with_meow


def test_classify():
    assert sa.classify_app("Code", "main.py") == "code"
    assert sa.classify_app("Cursor", "") == "code"
    assert sa.classify_app("Terminal", "") == "terminal"
    assert sa.classify_app("IINA", "movie.mkv") == "video"
    assert sa.classify_app("Safari", "YouTube - Safari") == "video"
    assert sa.classify_app("Safari", "Apple") == "browser"
    assert sa.classify_app("Google Chrome", "x") == "browser"
    assert sa.classify_app("微信", "") == "chat"
    assert sa.classify_app("Pages", "") == "doc"
    assert sa.classify_app("Figma", "") == "design"
    assert sa.classify_app("SomethingElse", "") == "other"


def test_blacklist_defaults_and_custom():
    assert sa.is_blacklisted("1Password 7", "", None)
    assert sa.is_blacklisted("微信", "", None)
    assert sa.is_blacklisted("Safari", "中国银行网上银行", None)
    assert sa.is_blacklisted("Keychain Access", "", None)
    assert not sa.is_blacklisted("Safari", "Apple", None)
    assert sa.is_blacklisted("Foo", "", ["foo"])
    assert not sa.is_blacklisted("微信", "", ["foo"])  # custom list replaces default


def test_limiter_hour_day_and_persist():
    store = {}
    lim = sa.UsageLimiter(store, hour=3, day=5)
    t = 1_000_000.0
    for i in range(3):
        assert lim.check(t + i) == "ok"
        lim.record(t + i)
    assert lim.check(t + 10) == "hour_limit"
    assert lim.check(t + 3601) == "ok"  # window slid
    lim.record(t + 3601); lim.record(t + 3602)
    assert lim.today_count(t + 3602) == 5
    assert lim.check(t + 7300) in ("day_limit",)
    assert store["count"] == 5  # persisted into the dict
    lim2 = sa.UsageLimiter(store, hour=3, day=5)
    assert lim2.today_count(t + 3602) == 5


def test_limiter_day_rollover():
    store = {}
    lim = sa.UsageLimiter(store, hour=99, day=2)
    t = time.mktime((2026, 10, 11, 23, 0, 0, 0, 0, -1))
    lim.record(t); lim.record(t + 1)
    assert lim.check(t + 2) == "day_limit"
    assert lim.check(t + 3 * 3600) == "ok"  # next day
    assert lim.today_count(t + 3 * 3600) == 0


def test_quiet_and_pause():
    t = time.mktime((2026, 10, 11, 23, 30, 0, 0, 0, -1))
    assert sa.is_quiet_hours(t, True, 22, 8)
    assert not sa.is_quiet_hours(t, False, 22, 8)
    noon = time.mktime((2026, 10, 11, 12, 0, 0, 0, 0, -1))
    assert not sa.is_quiet_hours(noon, True, 22, 8)
    assert sa.is_paused(100.0, 200.0) and not sa.is_paused(300.0, 200.0)


def test_signature_similarity():
    from PIL import Image
    import io
    def jpg(color, box=None):
        im = Image.new("RGB", (400, 300), color)
        if box:
            im.paste((0, 0, 0), box)
        b = io.BytesIO(); im.save(b, "JPEG"); return b.getvalue()
    a = sa.frame_signature(jpg((200, 200, 200)))
    b = sa.frame_signature(jpg((200, 200, 200), (0, 0, 8, 8)))
    c = sa.frame_signature(jpg((20, 20, 20)))
    assert sa.similar(a, b)
    assert not sa.similar(a, c)
    assert sa.frame_signature(b"not an image") is None
    assert not sa.similar(None, a)


def test_context_lines_end_with_meow():
    for cat, lines in sa.CONTEXT_LINES.items():
        assert lines, cat
        for s in lines:
            assert ends_with_meow(s), s
            assert len(s) <= 24, s
    for s in sa.STATUS_LINES.values():
        assert ends_with_meow(s), s
    assert sa.CONTEXT_PROB.get("code", 0) <= 0.1
    assert "video" not in sa.CONTEXT_LINES


class Env:
    def __init__(self, **kw):
        self.now = 1_700_000_000.0
        self.ctx = sa.FrontContext("Code", "main.py", False, False)
        self.frame = b"JPEGDATA"
        self.sig = (1, 2)
        self.replies = []
        self.calls = 0
        self.settings = {"screen_aware": True, "screen_vision": True, "screen_proactive": False,
                         "screen_pause_until": 0, "screen_quiet_hours": False, "screen_limit_hour": 3,
                         "screen_limit_day": 20, "screen_blacklist": None, "screen_usage": {}}
        self.settings.update(kw)
        self.perm = True
        self.key = "k"
        self.saved = 0

    def build(self):
        def describe(jpeg):
            self.calls += 1
            return "主人在写代码喵。"
        return sa.ScreenAwareness(
            settings=self.settings, save=lambda d: setattr(self, "saved", self.saved + 1),
            get_context=lambda: self.ctx, capture=lambda: self.frame, describe=describe,
            has_permission=lambda: self.perm, has_key=lambda: self.key is not None,
            signature=lambda b: self.sig, clock=lambda: self.now, rng=random.Random(1))


def test_manual_ok_counts_usage_and_returns_text():
    e = Env(); s = e.build()
    r = s.look(manual=True)
    assert r.status == "ok" and r.text.endswith("喵。") and e.calls == 1
    assert "今日" in s.usage_label() and "1/20" in s.usage_label()
    assert e.settings["screen_usage"]["count"] == 1


@pytest.mark.parametrize("mut,status", [
    (lambda e: e.settings.update(screen_vision=False), "vision_off"),
    (lambda e: e.settings.update(screen_aware=False), "disabled"),
    (lambda e: setattr(e, "perm", False), "no_permission"),
    (lambda e: setattr(e, "key", None), "no_key"),
    (lambda e: setattr(e, "ctx", sa.FrontContext("微信", "", False, False)), "blacklisted"),
    (lambda e: setattr(e, "ctx", sa.FrontContext("Safari", "x", False, True)), "secure"),
    (lambda e: setattr(e, "ctx", sa.FrontContext("Safari", "x", True, False)), "fullscreen"),
    (lambda e: setattr(e, "ctx", sa.FrontContext("IINA", "m", False, False)), "video"),
    (lambda e: e.settings.update(screen_pause_until=e.now + 100), "paused"),
    (lambda e: setattr(e, "frame", None), "capture_failed"),
    (lambda e: setattr(e, "ctx", None), "no_context"),
])
def test_skips_do_not_call_or_count(mut, status):
    e = Env(); mut(e); s = e.build()
    r = s.look(manual=True)
    assert r.status == status
    assert e.calls == 0 and not e.settings["screen_usage"].get("count")


def test_quiet_hours_skip():
    e = Env(screen_quiet_hours=True)
    e.now = time.mktime((2026, 10, 11, 23, 30, 0, 0, 0, -1))
    r = e.build().look(manual=True)
    assert r.status == "quiet" and e.calls == 0


def test_limit_stops_and_message_has_meow():
    e = Env(screen_limit_hour=2); s = e.build()
    assert s.look(manual=True).status == "ok"
    e.now += 5
    assert s.look(manual=True).status == "ok"
    e.now += 5
    r = s.look(manual=True)
    assert r.status == "hour_limit" and e.calls == 2 and ends_with_meow(r.text)


def test_describe_error_counts_but_reports():
    e = Env()
    def boom(j): e.calls += 1; raise RuntimeError("secret-key-xyz")
    s = e.build(); s._describe = boom
    r = s.look(manual=True)
    assert r.status == "error" and "secret" not in r.text and ends_with_meow(r.text)
    assert e.settings["screen_usage"]["count"] == 1


def test_proactive_rules():
    e = Env(screen_proactive=True); s = e.build()
    assert s.proactive_due() is True          # first time, new app
    assert s.look(manual=False).status == "ok"
    e.now += 60
    assert s.proactive_due() is False          # < 20 min since last
    e.now += 25 * 60
    assert s.proactive_due() is True           # same app but dwelled >= 15 min
    assert s.look(manual=False).status == "same_frame"
    e.sig = (200, 200)
    e.now += 60
    assert s.look(manual=False).status == "ok"


def test_proactive_off_by_default():
    e = Env(screen_proactive=False); s = e.build()
    assert s.proactive_due() is False
    assert s.look(manual=False).status == "proactive_off"


def test_manual_ignores_same_frame():
    e = Env(); s = e.build()
    s.look(manual=True); e.now += 5
    assert s.look(manual=True).status == "ok"


def test_context_tick_chatty_and_cooldown():
    got = None
    for i in range(50):
        e = Env(); s = e.build(); s._rng = random.Random(i)
        e.ctx = sa.FrontContext("Safari", "Apple", False, False)
        got = s.context_line()
        if got:
            break
    assert got and ends_with_meow(got)
    assert s.context_line() is None            # same app, no change
    e.ctx = sa.FrontContext("Pages", "", False, False)
    e.now += 5
    assert s.context_line() is None            # global 10-min gap
    e.ctx = sa.FrontContext("IINA", "m", False, False)
    for i in range(30):
        e.now += 1000
        e.ctx = sa.FrontContext("IINA" if i % 2 else "Figma", "m", False, False)
        assert s.context_line() is None        # video / design never speak


def test_context_line_disabled_or_blacklisted_silent():
    e = Env(screen_aware=False); s = e.build()
    e.ctx = sa.FrontContext("Safari", "Apple", False, False)
    assert s.context_line() is None
    e2 = Env(); s2 = e2.build()
    e2.ctx = sa.FrontContext("微信", "", False, False)
    for i in range(30):
        e2.now += 1000
        assert s2.context_line() is None


def test_is_look_request():
    for t in ("你看我屏幕", "看看我屏幕上有什么", "看一下我的屏幕", "你看看我在干嘛", "帮我看看屏幕"):
        assert sa.is_look_request(t), t
    for t in ("今天天气", "屏幕好亮", "你好"):
        assert not sa.is_look_request(t), t
