"""Tests for weather bubble helpers (no live network)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from desk_pet_grok.weather import (
    WeatherError,
    display_city_name,
    fetch_weather,
    format_weather_message,
    parse_j1_payload,
    translate_desc,
    weather_url,
)

FIXTURE = Path(__file__).parent / "fixtures" / "wttr_j1_hongkong.json"


def test_display_city_hong_kong() -> None:
    assert display_city_name("Hong Kong") == "香港"
    assert display_city_name("hong kong") == "香港"
    assert display_city_name("HongKong") == "香港"
    assert display_city_name("") == "香港"
    assert display_city_name("Tokyo") == "Tokyo"


def test_format_weather_message() -> None:
    assert format_weather_message("Hong Kong", 26, "Partly cloudy") == "「香港今天 26°，多云」"
    assert format_weather_message("Hong Kong", "26.4", "Sunny") == "「香港今天 26°，晴」"


def test_translate_desc_passthrough_unknown() -> None:
    assert translate_desc("Weird Condition XYZ") == "Weird Condition XYZ"


def test_parse_j1_fixture_prefers_lang_zh() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    msg = parse_j1_payload(data, "Hong Kong")
    assert msg == "「香港今天 26°，多云」"


def test_parse_j1_falls_back_to_weather_desc() -> None:
    data = {
        "current_condition": [
            {
                "temp_C": "18",
                "weatherDesc": [{"value": "Light rain"}],
            }
        ]
    }
    assert parse_j1_payload(data, "Hong Kong") == "「香港今天 18°，小雨」"


def test_parse_j1_incomplete_raises() -> None:
    with pytest.raises(WeatherError):
        parse_j1_payload({}, "Hong Kong")
    with pytest.raises(WeatherError):
        parse_j1_payload({"current_condition": []}, "Hong Kong")


def test_weather_url_encodes_city() -> None:
    url = weather_url("Hong Kong")
    assert url.startswith("https://wttr.in/")
    assert "format=j1" in url
    assert "Hong" in url or "Hong%20Kong" in url or "Hong+Kong" in url


def test_fetch_weather_uses_mock_client() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload

    client = MagicMock(spec=httpx.Client)
    client.get.return_value = response

    msg = fetch_weather("Hong Kong", client=client)
    assert msg == "「香港今天 26°，多云」"
    client.get.assert_called_once()
    args, kwargs = client.get.call_args
    assert "wttr.in" in args[0]
    assert "User-Agent" in kwargs.get("headers", {})


def test_fetch_weather_timeout_raises() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = httpx.ReadTimeout("slow")
    with pytest.raises(WeatherError, match="超时"):
        fetch_weather("Hong Kong", client=client)


def test_fetch_weather_http_error_raises() -> None:
    client = MagicMock(spec=httpx.Client)
    client.get.side_effect = httpx.ConnectError("no net")
    with pytest.raises(WeatherError, match="网络"):
        fetch_weather("Hong Kong", client=client)


def test_fetch_weather_bad_status_raises() -> None:
    response = MagicMock()
    response.status_code = 500
    response.json.return_value = {}
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = response
    with pytest.raises(WeatherError):
        fetch_weather("Hong Kong", client=client)
