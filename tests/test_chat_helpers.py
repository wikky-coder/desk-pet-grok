"""Unit tests for chat prompt, history trim, errors, bubble truncate."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-chat")

from desk_pet_grok.api import AuthError, RateLimitError, TimeoutApiError, ApiError
from desk_pet_grok.bubble import truncate_for_bubble
from desk_pet_grok.chat import (
    HISTORY_LIMIT,
    MSG_AUTH,
    MSG_GENERIC,
    MSG_RATE,
    MSG_TIMEOUT,
    SYSTEM_PROMPT,
    build_api_messages,
    map_error_message,
    trim_history,
)


def test_system_prompt_exact():
    expected = (
        "你是用户桌面上的助手，通过 xAI API 被本机桌宠调用。\n"
        "用用户正在用的语言回答，默认中文。\n"
        "桌面气泡最多 80 个汉字或 160 个英文字符；用户明确要求展开时再写长。\n"
        "不要声称自己是 Grok 网页、Grok App 或 Grok Bot 里的同一个会话。\n"
        "不要编造已经执行过的本机操作。只有工具结果里写了成功，才能说做过。\n"
        "不要索要 API Key。"
    )
    assert SYSTEM_PROMPT == expected


def test_trim_history_keeps_last_20():
    msgs = [{"role": "user", "content": str(i)} for i in range(30)]
    trimmed = trim_history(msgs, limit=HISTORY_LIMIT)
    assert len(trimmed) == 20
    assert trimmed[0]["content"] == "10"
    assert trimmed[-1]["content"] == "29"


def test_trim_history_drops_system_from_storage_list():
    msgs = [
        {"role": "system", "content": "nope"},
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
    ]
    trimmed = trim_history(msgs)
    assert all(m["role"] != "system" for m in trimmed)
    assert len(trimmed) == 2


def test_build_api_messages_prepends_system():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]
    built = build_api_messages(history)
    assert built[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert built[1:] == history


def test_map_error_message():
    assert map_error_message(AuthError("x")) == MSG_AUTH
    assert map_error_message(RateLimitError("x")) == MSG_RATE
    assert map_error_message(TimeoutApiError("x")) == MSG_TIMEOUT
    assert map_error_message(ApiError("x")) == MSG_GENERIC
    assert map_error_message(RuntimeError("x")) == MSG_GENERIC


def test_truncate_for_bubble_cjk_about_80():
    text = "字" * 100
    out = truncate_for_bubble(text)
    assert out.endswith("…")
    # 80 CJK chars + ellipsis (budget 160 units)
    assert out == ("字" * 80) + "…"


def test_truncate_for_bubble_ascii_about_160():
    text = "a" * 200
    out = truncate_for_bubble(text)
    assert out == ("a" * 160) + "…"


def test_truncate_short_unchanged():
    assert truncate_for_bubble("你好") == "你好"
    assert truncate_for_bubble("hello") == "hello"
