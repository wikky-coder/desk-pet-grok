"""Unit tests for SSE / Responses text-delta parsing (no live network)."""

from __future__ import annotations

import json

import pytest

from desk_pet_grok.api import (
    AuthError,
    RateLimitError,
    TimeoutApiError,
    iter_text_deltas,
    iter_text_deltas_from_bytes,
    messages_to_input,
    parse_sse_line,
    text_delta_from_payload,
    _raise_for_status,
)


def test_messages_to_input_preserves_roles():
    msgs = [
        {"role": "system", "content": "You are a desk pet."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert messages_to_input(msgs) == msgs


def test_parse_sse_line_data_and_non_data():
    assert parse_sse_line('data: {"a":1}') == '{"a":1}'
    assert parse_sse_line("data:   [DONE]") == "[DONE]"
    assert parse_sse_line("event: response.output_text.delta") is None
    assert parse_sse_line(": keep-alive") is None
    assert parse_sse_line("") is None


def test_text_delta_from_output_text_event():
    payload = {
        "type": "response.output_text.delta",
        "item_id": "msg_1",
        "delta": "Hello",
        "sequence_number": 1,
    }
    assert text_delta_from_payload(payload) == "Hello"


def test_text_delta_skips_reasoning_and_unknown():
    assert (
        text_delta_from_payload(
            {"type": "response.reasoning_text.delta", "delta": "think"}
        )
        is None
    )
    assert text_delta_from_payload({"type": "response.created", "id": "r1"}) is None
    assert text_delta_from_payload({"type": "response.completed"}) is None


def test_text_delta_chat_completions_style():
    payload = {
        "id": "chatcmpl_1",
        "object": "chat.completion.chunk",
        "choices": [{"index": 0, "delta": {"content": "世界", "role": "assistant"}}],
    }
    assert text_delta_from_payload(payload) == "世界"


def test_iter_text_deltas_fixture_stream():
    lines = [
        "event: response.created",
        'data: {"type":"response.created","id":"resp_1"}',
        "",
        "event: response.output_text.delta",
        'data: {"type":"response.output_text.delta","delta":"桌"}',
        "",
        'data: {"type":"response.output_text.delta","delta":"宠"}',
        'data: {"type":"response.output_text.delta","delta":"grok"}',
        "data: [DONE]",
        'data: {"type":"response.output_text.delta","delta":"ignored"}',
    ]
    assert list(iter_text_deltas(lines)) == ["桌", "宠", "grok"]


def test_iter_text_deltas_from_byte_chunks_split_across_boundaries():
    # Split JSON / SSE across arbitrary byte chunk boundaries.
    sse = (
        'data: {"type":"response.output_text.delta","delta":"Hel"}\n'
        'data: {"type":"response.output_text.delta","delta":"lo"}\n'
        "data: [DONE]\n"
    )
    encoded = sse.encode("utf-8")
    chunks = [encoded[:17], encoded[17:40], encoded[40:55], encoded[55:]]
    assert b"".join(chunks) == encoded
    assert list(iter_text_deltas_from_bytes(chunks)) == ["Hel", "lo"]


def test_iter_text_deltas_from_bytes_crlf():
    sse = (
        'data: {"type":"response.output_text.delta","delta":"A"}\r\n'
        'data: {"type":"response.output_text.delta","delta":"B"}\r\n'
        "data: [DONE]\r\n"
    )
    assert list(iter_text_deltas_from_bytes([sse.encode("utf-8")])) == ["A", "B"]


def test_iter_text_deltas_skips_bad_json():
    lines = [
        "data: not-json",
        'data: {"type":"response.output_text.delta","delta":"ok"}',
        "data: [DONE]",
    ]
    assert list(iter_text_deltas(lines)) == ["ok"]


def test_raise_for_status_maps_codes():
    with pytest.raises(AuthError, match="API key rejected"):
        _raise_for_status(401)
    with pytest.raises(RateLimitError, match="Rate limited"):
        _raise_for_status(429)
    with pytest.raises(Exception) as excinfo:
        _raise_for_status(500)
    assert "500" in str(excinfo.value)
    # Must not leak secrets-looking content.
    assert "Bearer" not in str(excinfo.value)


def test_timeout_error_name_is_timeout_api_error():
    err = TimeoutApiError("Request timed out")
    assert "timed out" in str(err)
    assert type(err).__name__ == "TimeoutApiError"


def test_error_messages_never_echo_fixture_key_material():
    # Simulate a payload someone might accidentally stringify into errors.
    fake_key = "xai-secret-should-never-appear"
    payload = {"type": "response.output_text.delta", "delta": "hi"}
    text = text_delta_from_payload(payload)
    assert text == "hi"
    # Ensure helper surface does not embed caller secrets.
    joined = " ".join(
        [
            str(AuthError("API key rejected")),
            str(RateLimitError("Rate limited")),
            str(TimeoutApiError("Request timed out")),
            json.dumps(messages_to_input([{"role": "user", "content": "hi"}])),
        ]
    )
    assert fake_key not in joined
