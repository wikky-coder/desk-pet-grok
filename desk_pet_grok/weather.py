"""Weather fetch for 桌宠grok bubbles (wttr.in, no API key)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

DEFAULT_CITY = "Hong Kong"
DEFAULT_TIMEOUT_S = 8.0
USER_AGENT = "desk-pet-grok/1.0 (+https://github.com/local/desk-pet-grok)"

# Common English wttr.in weatherDesc → short Chinese for the bubble.
_DESC_ZH: dict[str, str] = {
    "clear": "晴",
    "sunny": "晴",
    "partly cloudy": "多云",
    "cloudy": "阴",
    "overcast": "阴",
    "mist": "薄雾",
    "fog": "雾",
    "patchy rain nearby": "局部有雨",
    "patchy rain possible": "可能有雨",
    "light rain": "小雨",
    "moderate rain": "中雨",
    "heavy rain": "大雨",
    "light rain shower": "小阵雨",
    "moderate or heavy rain shower": "阵雨",
    "thundery outbreaks possible": "可能有雷暴",
    "thundery outbreaks in nearby": "附近有雷暴",
    "light snow": "小雪",
    "moderate snow": "中雪",
    "heavy snow": "大雪",
    "blizzard": "暴雪",
    "ice pellets": "冰粒",
    "light drizzle": "毛毛雨",
    "freezing fog": "冻雾",
}


class WeatherError(Exception):
    """User-facing weather failure (safe message; never includes secrets)."""


def display_city_name(city: str) -> str:
    """Human label for bubble; Hong Kong → 香港."""
    cleaned = (city or "").strip()
    if not cleaned:
        return "香港"
    key = cleaned.lower().replace(" ", "")
    if key in ("hongkong", "hk"):
        return "香港"
    if cleaned.lower() == "hong kong":
        return "香港"
    return cleaned


def translate_desc(desc: str) -> str:
    """Map English wttr description to a short Chinese phrase when known."""
    raw = (desc or "").strip()
    if not raw:
        return "未知"
    mapped = _DESC_ZH.get(raw.lower())
    return mapped if mapped else raw


def format_weather_message(city: str, temp_c: str | int | float, desc: str) -> str:
    """Build 「香港今天 26°，多云」 style bubble text."""
    name = display_city_name(city)
    try:
        temp_num = int(round(float(temp_c)))
        temp_s = str(temp_num)
    except (TypeError, ValueError):
        temp_s = str(temp_c).strip() or "?"
    condition = translate_desc(desc)
    return f"「{name}今天 {temp_s}°，{condition}」"


def parse_j1_payload(data: dict[str, Any], city: str) -> str:
    """Extract temp + description from wttr.in ``format=j1`` JSON."""
    try:
        current_list = data["current_condition"]
        if not isinstance(current_list, list) or not current_list:
            raise KeyError("current_condition")
        current = current_list[0]
        if not isinstance(current, dict):
            raise KeyError("current_condition[0]")
        temp = current.get("temp_C")
        if temp is None:
            raise KeyError("temp_C")

        desc = ""
        lang_zh = current.get("lang_zh")
        if isinstance(lang_zh, list) and lang_zh:
            first = lang_zh[0]
            if isinstance(first, dict):
                desc = str(first.get("value") or "").strip()
        if not desc:
            weather_desc = current.get("weatherDesc")
            if isinstance(weather_desc, list) and weather_desc:
                first = weather_desc[0]
                if isinstance(first, dict):
                    desc = str(first.get("value") or "").strip()
        if not desc:
            desc = "未知"
    except (KeyError, TypeError, IndexError) as exc:
        raise WeatherError("天气数据不完整。") from exc

    return format_weather_message(city, temp, desc)


def weather_url(city: str) -> str:
    """Build wttr.in j1 URL for ``city``."""
    place = (city or DEFAULT_CITY).strip() or DEFAULT_CITY
    return f"https://wttr.in/{quote(place)}?format=j1"


def fetch_weather(
    city: str = DEFAULT_CITY,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    client: httpx.Client | None = None,
) -> str:
    """Fetch current weather and return a short Chinese bubble string.

    Uses wttr.in JSON (``format=j1``). Raises ``WeatherError`` on network /
    parse failures. Never logs secrets (wttr.in needs none).
    """
    place = (city or DEFAULT_CITY).strip() or DEFAULT_CITY
    url = weather_url(place)
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    owns_client = client is None
    http = client or httpx.Client(timeout=timeout_s, headers=headers)
    try:
        try:
            response = http.get(url, headers=headers, timeout=timeout_s)
        except httpx.TimeoutException as exc:
            raise WeatherError("查天气超时了。") from exc
        except httpx.HTTPError as exc:
            raise WeatherError("查天气失败，请检查网络。") from exc

        if response.status_code >= 400:
            raise WeatherError("查天气失败，请稍后再试。")

        try:
            data = response.json()
        except ValueError as exc:
            raise WeatherError("天气数据解析失败。") from exc

        if not isinstance(data, dict):
            raise WeatherError("天气数据不完整。")

        return parse_j1_payload(data, place)
    finally:
        if owns_client:
            http.close()
