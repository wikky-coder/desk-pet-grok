"""Random chat lines for 桌宠grok (cute mild assistant tone).

Original lines — not DeepSeek / 大肥鱼 meme copies.
"""

from __future__ import annotations

import random
import time
from typing import Mapping, Sequence

CATEGORIES: tuple[str, ...] = ("idle_chatter", "click_reply", "after_drag")

IDLE_CHATTER: tuple[str, ...] = (
    "摸鱼中…需要我帮忙吗？",
    "今天也一起加油呀。",
    "我在这儿陪你。",
    "喝口水歇一下？",
    "有什么想聊的，双击我就好。",
    "尾巴摇摇，状态不错。",
    "记得多眨眼，屏幕很亮。",
    "哼哼，待机也很忙的。",
    "想听一句鼓励吗：你可以的。",
    "窗外天气怎样了？",
)

CLICK_REPLY: tuple[str, ...] = (
    "诶？叫我啦。",
    "在呢在呢。",
    "戳到啦～",
    "喵？…咳，我是桌宠grok。",
    "需要聊天的话，双击打开对话框。",
    "嘿嘿，被发现了。",
    "耳朵竖起来了。",
    "轻轻拍一下也好。",
    "我听着呢。",
    "有任务尽管说。",
)

AFTER_DRAG: tuple[str, ...] = (
    "到新位置啦。",
    "放这儿可以吗？",
    "视野换一换。",
    "谢谢挪窝～",
    "站稳了。",
    "这边风景不错。",
)

_LINES: Mapping[str, Sequence[str]] = {
    "idle_chatter": IDLE_CHATTER,
    "click_reply": CLICK_REPLY,
    "after_drag": AFTER_DRAG,
}

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
) -> str:
    """Pick a non-empty random line from ``category``."""
    pool = lines_for(category)
    if not pool:
        raise ValueError(f"empty line category: {category!r}")
    chooser = rng.choice if rng is not None else random.choice
    line = chooser(list(pool))
    if not isinstance(line, str) or not line.strip():
        raise ValueError(f"blank line in category: {category!r}")
    return line
