from desk_pet_grok.meow import MEOW, ends_with_meow, ensure_meow


def test_ends_with_meow_ignores_closing_punctuation():
    assert ends_with_meow("好的喵。")
    assert ends_with_meow("好的喵")
    assert ends_with_meow("真的吗喵？！")
    assert ends_with_meow("嗯喵…")
    assert ends_with_meow("「好的喵」")
    assert not ends_with_meow("好的。")
    assert not ends_with_meow("")


def test_adds_meow_before_final_punctuation_per_sentence():
    assert ensure_meow("好的。") == "好的喵。"
    assert ensure_meow("好的！你呢？") == "好的喵！你呢喵？"
    assert ensure_meow("等一下…") == "等一下喵…"
    assert ensure_meow("没标点") == "没标点喵"


def test_idempotent_and_keeps_existing():
    s = "已经有了喵。再来一句喵！"
    assert ensure_meow(s) == s
    once = ensure_meow("天气不错。出去走走吧")
    assert ensure_meow(once) == once


def test_skips_code_links_commands_numbers():
    assert ensure_meow("```\nprint(1)\n```") == "```\nprint(1)\n```"
    assert ensure_meow("运行 `ls -la` 看看。") == "运行 `ls -la` 看看喵。"
    assert ensure_meow("见 https://x.ai/docs") == "见 https://x.ai/docs"
    assert ensure_meow("$ pip install x") == "$ pip install x"
    assert ensure_meow("3.14") == "3.14"
    assert ensure_meow("`code`") == "`code`"


def test_multiline_and_lists():
    out = ensure_meow("要点：\n- 第一项\n- 第二项。\n\n结束")
    assert out == "要点喵：\n- 第一项喵\n- 第二项喵。\n\n结束喵"


def test_english_and_mixed():
    assert ensure_meow("Hello world.") == "Hello world喵."
    assert ensure_meow("用 Python 写。") == "用 Python 写喵。"


def test_meow_constant():
    assert MEOW == "喵"
