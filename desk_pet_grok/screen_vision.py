"""xAI vision call for the screen-awareness feature. Non-streaming; ``post`` is injectable for tests.
The screenshot is only ever base64-encoded in memory into the request body; window titles are never sent."""

from __future__ import annotations

import base64
import os
from typing import Any, Callable

from desk_pet_grok.api import API_URL, DEFAULT_MODEL, ApiError, AuthError, RateLimitError, TimeoutApiError
from desk_pet_grok.meow import MEOW

TIMEOUT_S = 30.0
MAX_REPLY_CHARS = 80

SYSTEM_PROMPT = (
    "你是桌宠「小 Grok」，一只软萌的猫娘女仆。自称「本喵」（偶尔自称 Wiki），称呼用户为「主人」。"
    "下面是主人当前屏幕的缩略截图。请用一到两句、总共不超过 40 个字的口吻，简短、温柔地评论主人正在做的事。"
    "每一句都必须以「喵」结尾。不要念出屏幕上的密码、账号、姓名、金额、聊天内容等任何私人信息，也不要逐字转述屏幕文字。"
)


def api_key_from_env() -> str | None:
    """The screen feature reads the key from the environment only (never from files)."""
    v = os.environ.get("XAI_API_KEY")
    return v.strip() if v and v.strip() else None


def build_body(jpeg: bytes, *, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
    return {
        "model": model,
        "stream": False,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "input_text", "text": "主人让你看看屏幕，说说你看到了什么。"},
                {"type": "input_image", "image_url": url},
            ]},
        ],
    }


def parse_response(data: dict[str, Any]) -> str:
    t = data.get("output_text")
    if isinstance(t, str) and t.strip():
        return t.strip()
    parts: list[str] = []
    for item in data.get("output") or []:
        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "output_text" and isinstance(c.get("text"), str):
                    parts.append(c["text"])
    return "".join(parts).strip()


def _clamp(text: str) -> str:
    if len(text) <= MAX_REPLY_CHARS:
        return text
    cut = text[:MAX_REPLY_CHARS]
    last = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"))
    if last >= 10:
        return cut[: last + 1]
    return cut.rstrip("，、 ") + MEOW + "。"


def _httpx_post(url: str, headers: dict, body: dict, timeout: float):
    import httpx
    with httpx.Client(timeout=httpx.Timeout(timeout)) as c:
        return c.post(url, headers=headers, json=body)


def describe(jpeg: bytes, api_key: str, *, model: str = DEFAULT_MODEL,
             post: Callable[[str, dict, dict, float], Any] | None = None) -> str:
    """Return a short catgirl remark. Raises ApiError subclasses with key-free messages."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    send = post or _httpx_post
    try:
        resp = send(API_URL, headers, build_body(jpeg, model=model), TIMEOUT_S)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        if "Timeout" in name:
            raise TimeoutApiError("Request timed out") from None
        raise ApiError("Request failed") from None
    code = resp.status_code
    if code == 401:
        raise AuthError("API key rejected")
    if code == 429:
        raise RateLimitError("Rate limited")
    if code >= 400:
        raise ApiError(f"HTTP {code}")
    text = parse_response(resp.json())
    if not text:
        raise ApiError("Empty reply")
    return _clamp(text)
