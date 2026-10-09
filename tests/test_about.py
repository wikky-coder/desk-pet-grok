"""About copy checks."""

from desk_pet_grok.about import ABOUT_TEXT


def test_about_mentions_boundaries():
    assert "桌宠grok" in ABOUT_TEXT
    assert "非 DeepSeek" in ABOUT_TEXT
    assert "非 xAI 官方" in ABOUT_TEXT
    assert "不是同一个会话" in ABOUT_TEXT
    assert "装饰标识" in ABOUT_TEXT
