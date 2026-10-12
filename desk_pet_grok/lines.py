"""Random chat lines for 小 Grok, a catgirl maid (self 本喵 / sometimes Wiki; user 主人). Original lines, short and soft."""

from __future__ import annotations

import random
import time
from typing import Mapping, Sequence

LONG_IDLE_LEVELS: tuple[str, ...] = ("long_idle_1", "long_idle_2", "long_idle_3")
CATEGORIES: tuple[str, ...] = (
    "idle_chatter", "click_reply", "after_drag", "boot",
    *LONG_IDLE_LEVELS,
    "top_of_hour", "weather_change", "rapid_clicks", "screen_edge", "task_done", "error",
    "lounge_start", "lounge", "yawn", "lounge_sleep", "lounge_end", "self_walk",
    "pet_head", "pet_fall", "pat_spoil", "app_switch", "long_use", "welcome_back",
)

# Voice: user = 主人; self = 本喵 mostly, occasionally Wiki (she sometimes refers to herself by name). Short, soft, particles / kaomoji only now and then.
# No intimate content. Lines <= 24 chars (bubble hard limit is 80).
IDLE_CHATTER: tuple[str, ...] = (
    "本喵在这儿陪着主人呢喵。",
    "主人，喝口水再继续吧喵。",
    "屏幕有点亮，眨眨眼睛喵。",
    "Wiki 的尾巴有点痒喵。",
    "今天的主人也辛苦啦喵。",
    "要不要站起来伸个懒腰喵？",
    "本喵在巡逻，一切正常喵。",
    "想聊天就双击本喵哦喵。",
    "窗外天气怎么样呀喵？",
    "坐久了，肩膀要动一动喵。",
    "本喵打了个小哈欠喵。",
    "主人的进度，本喵看好你喵。",
    "安静地待着也很舒服喵。",
    "Wiki 想问问，主人吃好了吗喵？",
)

CLICK_REPLY: tuple[str, ...] = (
    "喵？本喵在呢喵。",
    "被戳到啦喵。",
    "主人叫本喵吗喵？",
    "耳朵竖起来了喵。",
    "有事就说，本喵听着喵。",
    "嘿嘿，Wiki 被发现了喵。",
    "要聊天的话，双击本喵。",
    "轻一点嘛，会痒的喵。",
    "本喵是小 Grok，请多指教喵。",
    "在在在，不用戳那么多下喵。",
    "收到喵！本喵待命中喵。",
    "嗯喵？主人想本喵了吗喵？",
)

AFTER_DRAG: tuple[str, ...] = (
    "到新地方啦，本喵站稳了喵。",
    "这里视野不错喵。",
    "放这儿可以吗，主人喵？",
    "好晕喵…本喵缓一下喵。",
    "谢谢搬家，本喵喜欢这里喵。",
    "Wiki 落地，稳稳的喵。",
    "换个角度看世界喵。",
    "下次轻轻放哦喵。",
    "本喵会待在这里的喵。",
    "刚才飘起来了，吓一跳喵。",
)

BOOT: tuple[str, ...] = (
    "本喵上线啦，主人早喵。",
    "今天也请多关照喵。",
    "开机成功，尾巴摇摇喵。",
    "主人回来啦，本喵等了好久喵。",
    "本喵准备好了，随时叫我喵。",
    "伸个懒腰，开工开工喵。",
    "欢迎回来，主人喵。",
    "本喵已就位喵。",
    "睁开眼睛，今天要加油喵。",
    "Wiki 又见到主人啦喵。",
    "来啦来啦，让本喵看看今天做什么喵。",
    "本喵醒了，主人先喝口水吧喵。",
)

LONG_IDLE_1: tuple[str, ...] = (
    "主人，在忙吗喵？本喵安静待着喵。",
    "好像有一会儿没动静了喵。",
    "本喵先自己玩一会儿喵。",
    "主人还在吗喵？",
    "不打扰你，本喵蹲在这儿喵。",
    "一个人发呆中喵…",
    "本喵在数屏幕上的像素喵。",
    "要不要休息一下眼睛喵？",
    "本喵悄悄看了你一眼喵。",
    "忙完了记得叫本喵。",
)

LONG_IDLE_2: tuple[str, ...] = (
    "主人，好久没理本喵了喵。",
    "本喵的尾巴都卷起来了喵。",
    "是不是睡着了呀喵？",
    "再不来，本喵要自己溜达了喵。",
    "有点无聊，戳我一下嘛喵。",
    "本喵已经把窗台数了三遍喵。",
    "主人去哪儿了呢喵…",
    "本喵趴下等你喵。",
    "喵…有点想你了喵。",
    "忙归忙，也要吃饭哦喵。",
)

LONG_IDLE_3: tuple[str, ...] = (
    "主人喵…本喵一直在等你喵。",
    "已经好久好久了喵。",
    "本喵缩成一团了喵。",
    "屏幕黑了的话，本喵会怕的喵。",
    "再久一点，本喵就要睡着啦喵。",
    "你回来的话，本喵会很开心喵。",
    "本喵不闹，就是想看看你喵。",
    "尾巴都没力气摇了喵。",
    "晚安的话，也可以跟本喵说一声喵。",
    "本喵在这里，哪儿也不去喵。",
)

TOP_OF_HOUR: tuple[str, ...] = (
    "现在 {hour} 点整啦喵。",
    "整点报时，{hour} 点了喵。",
    "主人，{hour} 点了，动一动吧喵。",
    "叮，{hour} 点，起来走两步喵。",
    "{hour} 点了，喝口水再继续喵。",
    "本喵报时：{hour} 点整喵。",
    "又过了一小时，辛苦啦喵。",
    "整点啦，眼睛看看远处喵。",
    "时间过得真快，{hour} 点了喵。",
    "{hour} 点，要不要伸个懒腰喵？",
    "主人，该歇一歇了喵。",
    "整点提醒，本喵没有偷懒喵。",
)

WEATHER_CHANGE: tuple[str, ...] = (
    "天气变了，主人注意哦喵。",
    "好像变成{cond}了喵。",
    "外面{cond}，出门看看天喵。",
    "本喵闻到天气的味道了喵。",
    "{cond}的话，记得带伞或衣服喵。",
    "窗外有变化，来看看喵？",
    "天气换了，本喵的耳朵在动喵。",
    "主人，现在是{cond}喵。",
    "气温变了，别着凉喵。",
    "本喵查了一下，{cond}喵。",
    "天气预报员本喵上线喵。",
    "今天的天气，值得说一声喵。",
)

RAPID_CLICKS: tuple[str, ...] = (
    "喂，别戳啦喵！",
    "再戳本喵要生气了喵。",
    "哼，戳得太快了喵。",
    "手指停一下，好不好喵？",
    "本喵的头要被戳扁了喵。",
    "主人喵！很痒的喵！",
    "不理你了，哼喵。",
    "够了够了，本喵要炸毛了喵。",
    "再来一下，本喵就躲起来喵。",
    "你是不是在玩本喵？",
    "喵！轻一点喵！",
    "Wiki 要记下来，主人欺负猫喵。",
)

SCREEN_EDGE: tuple[str, ...] = (
    "本喵到边边啦喵。",
    "再往外本喵就掉下去了喵。",
    "靠墙站，有安全感喵。",
    "Wiki 到屏幕尽头啦喵。",
    "本喵不能再往前了喵。",
    "边上风有点大喵。",
    "主人，把本喵往里挪一挪嘛喵。",
    "探头看看外面有什么喵。",
    "本喵贴着边边站好喵。",
    "再走就要出界啦喵。",
)

TASK_DONE: tuple[str, ...] = (
    "搞定啦，主人喵！",
    "任务完成，本喵尾巴翘起来喵。",
    "做好了，请检查一下喵。",
    "完成喵！本喵是不是很能干喵？",
    "办完了，夸夸本喵吧喵。",
    "这件事交给本喵没问题喵。",
    "收工，本喵可以歇一会儿吗喵？",
    "好啦，下一件是什么喵？",
    "圆满完成，主人请过目喵。",
    "Wiki 做完了，不用谢喵。",
)

ERROR: tuple[str, ...] = (
    "呜，Wiki 出错了喵。",
    "本喵搞砸了喵…对不起喵。",
    "好像哪里不对劲喵。",
    "喵呜，没成功喵。",
    "主人，本喵遇到麻烦了喵。",
    "这次失败了，再试一次吧喵。",
    "本喵的爪子打滑了喵。",
    "出问题了，不是主人的错喵。",
    "网络是不是睡着了喵？",
    "糟糕，本喵没接住喵。",
)

LOUNGE_START: tuple[str, ...] = (
    "这里刚刚好，本喵趴下啦喵。",
    "借主人的窗边歇一歇喵。",
    "本喵趴好了，不挡字喵。",
    "就这儿了，暖暖的喵。",
    "趴下来，尾巴摆摆喵。",
    "Wiki 要在这儿待一会儿喵。",
    "主人继续忙，本喵安静趴着喵。",
    "好位置，本喵占下了喵。",
    "轻轻落座，不打扰你喵。",
    "本喵像个团子趴好了喵。",
)

LOUNGE: tuple[str, ...] = (
    "呼噜呼噜…喵。",
    "本喵在这儿看着你喵。",
    "小声说，别吵到主人喵。",
    "字敲得真快喵…",
    "尾巴自己在摇喵。",
    "趴着真舒服喵。",
    "本喵不出声，只陪着喵。",
    "耳朵听着键盘声喵。",
    "主人加油，本喵小声喊喵。",
    "Wiki 在偷偷看屏幕喵。",
    "眼睛一眨一眨喵。",
    "今天也辛苦了喵。",
)

YAWN: tuple[str, ...] = (
    "啊呜…打个哈欠喵。",
    "好困…喵。",
    "本喵伸个小懒腰喵。",
    "哈啊…眼睛酸酸的喵。",
    "Wiki 打哈欠了喵。",
    "主人别笑，本喵只是困了喵。",
    "呼啊…喵。",
    "困意来了喵…",
    "再不动，本喵要睡着了喵。",
    "嘴巴张太大了喵。",
)

LOUNGE_SLEEP: tuple[str, ...] = (
    "zZ…喵…",
    "呼…呼…喵…",
    "本喵睡着了喵…",
    "梦里有小鱼干喵…",
    "嗯…主人…喵…",
    "尾巴盖着鼻子喵…",
    "zZz…再睡一会儿喵…",
    "Wiki 做梦了喵…",
    "别吵醒本喵哦喵…",
    "呼噜…呼噜…喵…",
)

LOUNGE_END: tuple[str, ...] = (
    "本喵起来啦，去逛逛喵。",
    "伸个腰，继续巡逻喵。",
    "位置还给主人喵。",
    "歇够了，本喵走啦喵。",
    "拜拜，主人慢慢忙喵。",
    "本喵去活动活动喵。",
    "Wiki 站起来了喵。",
    "输入框不见了，本喵先走喵。",
    "好的好的，本喵起身喵。",
    "下次再来趴喵。",
)

SELF_WALK: tuple[str, ...] = (
    "主人好久没动了，本喵过去陪你喵。",
    "本喵溜达到你这边喵。",
    "看你在打字，本喵来了喵。",
    "借个位置，马上就到喵。",
    "本喵悄悄走过来喵。",
    "Wiki 巡逻到这儿了喵。",
    "来陪主人写字喵。",
    "走啦走啦，去窗边喵。",
    "那边好像很舒服喵。",
    "本喵想趴一会儿喵。",
)

PET_HEAD: tuple[str, ...] = (
    "唔……主人摸得好舒服喵。",
    "本喵要化掉了喵。",
    "再摸一会儿嘛，主人喵。",
    "呼噜呼噜……好舒服喵。",
    "Wiki 最喜欢被主人摸头了喵。",
    "耳朵软软的，没力气了喵。",
    "主人的手好暖和喵。",
    "嘿嘿，本喵今天好幸福喵。",
    "不要停哦，主人喵。",
    "眯起眼睛了，好困喵。",
    "被主人摸摸，心情变好了喵。",
    "本喵的尾巴停不下来喵。",
)

PET_FALL: tuple[str, ...] = (
    "呀！本喵掉下来了喵！",
    "呀——主人，窗口跑掉了喵！",
    "哇呀！脚下空了喵！",
    "呀呀呀，要摔啦喵！",
    "啊呀，本喵的位置没了喵！",
    "呀！别突然动窗口喵！",
    "呜呀……吓了本喵一跳喵。",
    "呀！Wiki 在往下掉喵！",
    "哎呀，落地要轻轻的喵。",
    "呀——主人接住本喵喵！",
    "呜，摔得有点晕喵。",
    "呀！耳朵都飘起来了喵！",
)

PAT_SPOIL: tuple[str, ...] = (
    "再摸一会儿嘛，主人喵。",
    "本喵今天被摸得好舒服喵。",
    "呼噜呼噜……别停下喵。",
    "主人的手好暖，本喵要融化了喵。",
    "Wiki 想一直被摸头喵。",
    "再来一下下，就一下下喵。",
    "本喵的耳朵都软下来了喵。",
    "主人最会摸头了喵。",
    "尾巴不听话，自己摇起来了喵。",
    "这样本喵会撒娇的喵。",
)

APP_SWITCH: tuple[str, ...] = (
    "换软件啦，主人加油喵。",
    "本喵看到换了窗口喵。",
    "新的任务开始了喵？",
    "Wiki 在旁边看着喵。",
    "换个节奏也不错喵。",
    "主人换地方忙啦喵。",
    "这个界面本喵没见过喵。",
    "忙得过来吗，主人喵？",
    "需要本喵帮忙就喊一声喵。",
    "继续继续，本喵不打扰喵。",
)

LONG_USE: tuple[str, ...] = (
    "主人用了好久了，歇一歇喵。",
    "站起来走两步吧喵。",
    "眼睛累了吧，看看远处喵。",
    "喝口水，再继续喵。",
    "本喵给主人揉揉肩喵。",
    "该活动活动脖子了喵。",
    "连续工作很久啦，休息喵。",
    "Wiki 提醒主人放松一下喵。",
    "再忙也要记得伸懒腰喵。",
    "坐太久对腰不好喵。",
)

WELCOME_BACK: tuple[str, ...] = (
    "主人回来啦，欢迎回来喵。",
    "等你好久了，本喵在喵。",
    "回来啦！本喵没乱跑喵。",
    "Wiki 守着家呢，欢迎喵。",
    "主人辛苦了，歇会儿喵。",
    "你一走本喵就打了个盹喵。",
    "欢迎回来，要聊聊吗喵？",
    "耳朵一竖，主人回来了喵。",
    "刚才有点想主人喵。",
    "回来就好，本喵很开心喵。",
)

_LINES: Mapping[str, Sequence[str]] = {
    "idle_chatter": IDLE_CHATTER,
    "click_reply": CLICK_REPLY,
    "after_drag": AFTER_DRAG,
    "boot": BOOT,
    "long_idle_1": LONG_IDLE_1,
    "long_idle_2": LONG_IDLE_2,
    "long_idle_3": LONG_IDLE_3,
    "top_of_hour": TOP_OF_HOUR,
    "weather_change": WEATHER_CHANGE,
    "rapid_clicks": RAPID_CLICKS,
    "screen_edge": SCREEN_EDGE,
    "task_done": TASK_DONE,
    "lounge_start": LOUNGE_START,
    "lounge": LOUNGE,
    "yawn": YAWN,
    "lounge_sleep": LOUNGE_SLEEP,
    "lounge_end": LOUNGE_END,
    "self_walk": SELF_WALK,
    "pet_head": PET_HEAD,
    "pet_fall": PET_FALL,
    "pat_spoil": PAT_SPOIL,
    "app_switch": APP_SWITCH,
    "long_use": LONG_USE,
    "welcome_back": WELCOME_BACK,
    "error": ERROR,
}

# long_idle escalation thresholds (seconds without any interaction) -> level 1..3
LONG_IDLE_AFTER_S: tuple[float, ...] = (300.0, 900.0, 2400.0)
# rapid clicks: this many clicks within the window triggers the annoyed line
RAPID_CLICK_COUNT = 4
RAPID_CLICK_WINDOW_S = 3.0
BUBBLE_MAX_CHARS = 80


def long_idle_level(idle_s: float) -> int:
    """0 = not idle long enough, else 1..3 (escalating)."""
    lvl = 0
    for i, t in enumerate(LONG_IDLE_AFTER_S, 1):
        if idle_s >= t:
            lvl = i
    return lvl


def is_rapid_click(times: Sequence[float], now: float) -> bool:
    recent = [t for t in times if now - t <= RAPID_CLICK_WINDOW_S]
    return len(recent) >= RAPID_CLICK_COUNT


# Default cooldown between proactive / forced lines (seconds).
DEFAULT_COOLDOWN_S = 2.5


class LineCooldown:
    """Simple per-category (or global) cooldown gate."""

    def __init__(self, seconds: float = DEFAULT_COOLDOWN_S) -> None:
        self.seconds = float(seconds)
        self._last: dict[str, float] = {}

    def ready(self, key: str = "*", *, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        last = self._last.get(key)
        if last is None:
            return True
        return (t - last) >= self.seconds

    def mark(self, key: str = "*", *, now: float | None = None) -> None:
        self._last[key] = time.monotonic() if now is None else now

    def try_acquire(self, key: str = "*", *, now: float | None = None) -> bool:
        """Return True and mark if cooldown elapsed."""
        t = time.monotonic() if now is None else now
        if not self.ready(key, now=t):
            return False
        self.mark(key, now=t)
        return True


def lines_for(category: str) -> Sequence[str]:
    """Return the line list for a category; raises KeyError if unknown."""
    if category not in _LINES:
        raise KeyError(f"unknown line category: {category!r}")
    return _LINES[category]


def pick_line(
    category: str,
    *,
    rng: random.Random | None = None,
    **fmt: object,
) -> str:
    """Pick a non-empty random line from ``category``.

    Lines may contain ``{name}`` placeholders (e.g. ``{hour}``, ``{cond}``); they are only eligible when the
    caller passes matching keyword values, otherwise the plain lines are used."""
    pool = list(lines_for(category))
    if not pool:
        raise ValueError(f"empty line category: {category!r}")
    plain = [s for s in pool if "{" not in s]
    templ = []
    if fmt:
        for s in pool:
            if "{" in s:
                try:
                    s.format(**fmt)
                    templ.append(s)
                except (KeyError, IndexError, ValueError):
                    pass
    cand = (templ + plain) if fmt else plain
    if not cand:
        raise ValueError(f"no usable line in category: {category!r}")
    chooser = rng.choice if rng is not None else random.choice
    line = chooser(cand)
    if not isinstance(line, str) or not line.strip():
        raise ValueError(f"blank line in category: {category!r}")
    return line.format(**fmt) if "{" in line else line
