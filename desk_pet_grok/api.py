"""xAI Responses API streaming client for 桌宠grok."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable, Iterator
from typing import Any

import httpx

API_URL = "https://api.x.ai/v1/responses"
DEFAULT_MODEL = "grok-4.7"
DEFAULT_TIMEOUT_S = 120.0

_OUTPUT_TEXT_DELTA = "response.output_text.delta"


class ApiError(Exception):
    """Base error for xAI API failures (safe message; no secrets)."""


class AuthError(ApiError):
    """API key rejected (HTTP 401)."""


class RateLimitError(ApiError):
    """Too many requests (HTTP 429)."""


class TimeoutApiError(ApiError):
    """Request timed out (named to avoid shadowing builtin TimeoutError)."""


def messages_to_input(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Map chat-style messages to Responses API ``input`` items."""
    out: list[dict[str, str]] = []
    for msg in messages:
        role = str(msg.get("role", "user"))
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        out.append({"role": role, "content": content})
    return out


def parse_sse_line(line: str) -> str | None:
    """Return the SSE ``data:`` payload, or None if the line is not data."""
    if line.startswith("data:"):
        return line[5:].lstrip()
    return None


def text_delta_from_payload(payload: dict[str, Any]) -> str | None:
    """Extract a visible text delta from a Responses / chat-style SSE JSON object."""
    event_type = payload.get("type")
    if event_type == _OUTPUT_TEXT_DELTA:
        delta = payload.get("delta")
        return delta if isinstance(delta, str) and delta else None

    # Chat Completions-style chunks (compat / fixtures).
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            delta_obj = first.get("delta")
            if isinstance(delta_obj, dict):
                content = delta_obj.get("content")
                if isinstance(content, str) and content:
                    return content

    # Generic fallbacks used by some stream fixtures.
    if isinstance(payload.get("delta"), str) and payload["delta"]:
        if isinstance(event_type, str) and "reasoning" in event_type:
            return None
        if event_type is None or (
            isinstance(event_type, str) and event_type.endswith(".delta")
        ):
            # Only treat untyped / generic *.delta as text when not reasoning.
            if event_type is None:
                return payload["delta"]
            return None

    content = payload.get("content")
    if isinstance(content, str) and content and event_type is None:
        return content

    text = payload.get("text")
    if isinstance(text, str) and text and event_type is None:
        return text

    return None


def iter_text_deltas(lines: Iterable[str]) -> Iterator[str]:
    """Yield text deltas from SSE text lines; stop on ``data: [DONE]``."""
    for line in lines:
        stripped = line.rstrip("\r\n")
        if not stripped or stripped.startswith(":"):
            continue
        if stripped.startswith("event:"):
            continue
        data = parse_sse_line(stripped)
        if data is None:
            continue
        if data.strip() == "[DONE]":
            return
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        text = text_delta_from_payload(payload)
        if text:
            yield text


def iter_text_deltas_from_bytes(chunks: Iterable[bytes]) -> Iterator[str]:
    """Buffer SSE byte chunks into lines and yield text deltas (no network)."""
    buffer = ""
    for chunk in chunks:
        buffer += chunk.decode("utf-8", errors="replace")
        while True:
            nl = buffer.find("\n")
            if nl < 0:
                break
            line, buffer = buffer[:nl], buffer[nl + 1 :]
            data = parse_sse_line(line.rstrip("\r"))
            if data is not None and data.strip() == "[DONE]":
                return
            yield from iter_text_deltas([line])
    if buffer.strip():
        data = parse_sse_line(buffer.rstrip("\r"))
        if data is not None and data.strip() == "[DONE]":
            return
        yield from iter_text_deltas([buffer])


def _raise_for_status(status_code: int) -> None:
    if status_code == 401:
        raise AuthError("API key rejected")
    if status_code == 429:
        raise RateLimitError("Rate limited")
    if status_code >= 400:
        raise ApiError(f"HTTP {status_code}")


async def stream_response(
    *,
    messages: list[dict[str, Any]],
    api_key: str,
    model: str = DEFAULT_MODEL,
) -> AsyncIterator[str]:
    """Stream assistant text deltas from ``POST /v1/responses``.

    Closing / cancelling the async iterator closes the HTTP stream and client.
    Error messages never include the API key or response headers.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    body = {
        "model": model,
        "stream": True,
        "input": messages_to_input(messages),
    }
    timeout = httpx.Timeout(DEFAULT_TIMEOUT_S)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                API_URL,
                headers=headers,
                json=body,
            ) as resp:
                _raise_for_status(resp.status_code)
                buffer = ""
                async for chunk in resp.aiter_bytes():
                    buffer += chunk.decode("utf-8", errors="replace")
                    while True:
                        nl = buffer.find("\n")
                        if nl < 0:
                            break
                        line, buffer = buffer[:nl], buffer[nl + 1 :]
                        data = parse_sse_line(line.rstrip("\r"))
                        if data is not None and data.strip() == "[DONE]":
                            return
                        for text in iter_text_deltas([line]):
                            yield text
                if buffer.strip():
                    data = parse_sse_line(buffer.rstrip("\r"))
                    if data is not None and data.strip() == "[DONE]":
                        return
                    for text in iter_text_deltas([buffer]):
                        yield text
    except httpx.TimeoutException as exc:
        raise TimeoutApiError("Request timed out") from exc
    except (AuthError, RateLimitError, ApiError, TimeoutApiError):
        raise
    except httpx.HTTPError as exc:
        # Generic transport failure; never include request headers/key.
        raise ApiError("Request failed") from exc

def probe_api_key(api_key: str, *, model: str = DEFAULT_MODEL) -> None:
    """Short non-stream POST to validate a key before saving.

    Raises AuthError / RateLimitError / TimeoutApiError / ApiError.
    Never includes the key in exception messages.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "stream": False,
        "input": [{"role": "user", "content": "ping"}],
    }
    timeout = httpx.Timeout(30.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(API_URL, headers=headers, json=body)
            _raise_for_status(resp.status_code)
    except httpx.TimeoutException as exc:
        raise TimeoutApiError("Request timed out") from exc
    except (AuthError, RateLimitError, ApiError, TimeoutApiError):
        raise
    except httpx.HTTPError as exc:
        raise ApiError("Request failed") from exc

