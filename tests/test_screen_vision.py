import json

import pytest

from desk_pet_grok import screen_vision as sv
from desk_pet_grok.api import ApiError, AuthError, RateLimitError


def test_build_body_has_image_no_title():
    body = sv.build_body(b"\xff\xd8abc", model="m")
    s = json.dumps(body, ensure_ascii=False)
    assert body["model"] == "m" and body["stream"] is False
    content = body["input"][-1]["content"]
    img = [c for c in content if c["type"] == "input_image"][0]
    assert img["image_url"].startswith("data:image/jpeg;base64,")
    assert "本喵" in s and "主人" in s and "喵" in s


def test_parse_output_text_variants():
    assert sv.parse_response({"output_text": "你好喵。"}) == "你好喵。"
    data = {"output": [{"type": "reasoning"}, {"type": "message", "content": [{"type": "output_text", "text": "嗨"}, {"type": "output_text", "text": "喵"}]}]}
    assert sv.parse_response(data) == "嗨喵"
    assert sv.parse_response({}) == ""


class R:
    def __init__(self, code, data=None):
        self.status_code = code
        self._d = data or {}
    def json(self):
        return self._d


def test_describe_uses_injected_post_and_clamps():
    seen = {}
    def post(url, headers, body, timeout):
        seen.update(url=url, headers=headers, body=body, timeout=timeout)
        return R(200, {"output_text": "主人在看网页呢，本喵也想看喵。" * 10})
    out = sv.describe(b"img", "KEY123", post=post)
    assert seen["headers"]["Authorization"] == "Bearer KEY123"
    assert seen["url"].endswith("/v1/responses")
    assert out.endswith("喵。") and len(out) <= sv.MAX_REPLY_CHARS + 1


@pytest.mark.parametrize("code,exc", [(401, AuthError), (429, RateLimitError), (500, ApiError)])
def test_errors_mapped_without_key(code, exc):
    with pytest.raises(exc) as ei:
        sv.describe(b"img", "SECRETKEY", post=lambda u, h, b, t: R(code))
    assert "SECRETKEY" not in str(ei.value)


def test_empty_reply_is_error():
    with pytest.raises(ApiError):
        sv.describe(b"img", "k", post=lambda u, h, b, t: R(200, {}))


def test_key_from_env_only(monkeypatch, tmp_path):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert sv.api_key_from_env() is None
    monkeypatch.setenv("XAI_API_KEY", " abc ")
    assert sv.api_key_from_env() == "abc"
