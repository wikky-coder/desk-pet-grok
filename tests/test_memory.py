"""F4: cross-session memory store (local, 0600, capped, rate-limited, privacy filters)."""

from __future__ import annotations

import json
import os
import stat

from desk_pet_grok import memory
from desk_pet_grok.memory import MemoryStore


def test_roundtrip_and_permissions(tmp_path):
    p = tmp_path / "memory.json"
    m = MemoryStore(p)
    assert m.empty and m.prompt_block() == ""
    m.add_fact("主人喜欢被叫 Wiki 的主人")
    m.add_summary("聊了论文的第三章结构")
    m.save()
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    m2 = MemoryStore(p)
    assert m2.facts == m.facts and m2.recent[0]["s"] == "聊了论文的第三章结构"


def test_prompt_block_cap_and_oldest_dropped(tmp_path):
    m = MemoryStore(tmp_path / "m.json")
    for i in range(12):
        m.add_fact(f"事实{i}：" + "字" * 60)
    for i in range(8):
        m.add_summary(f"摘要{i}：" + "话" * 60)
    b = m.prompt_block()
    assert 0 < len(b) <= memory.BLOCK_MAX_CHARS
    assert "事实11" in b  # newest facts survive
    assert "摘要0" not in b  # oldest summary is evicted first


def test_caps_on_entries(tmp_path):
    m = MemoryStore(tmp_path / "m.json")
    for i in range(30):
        m.add_fact(f"fact number {i}")
        m.add_summary(f"summary {i}")
    assert len(m.facts) == memory.MAX_FACTS and len(m.recent) == memory.MAX_RECENT
    assert m.facts[-1] == "fact number 29"


def test_privacy_filter_blocks_keys_and_secrets(tmp_path):
    m = MemoryStore(tmp_path / "m.json")
    assert not m.add_fact("我的 key 是 xai-AbCdEf1234567890")
    assert not m.add_fact("银行卡号 6222 0000 0000")
    assert not m.add_summary("主人的密码是 hunter2")
    assert not m.add_fact("sk-abcdefghijklmnop")
    assert not m.add_fact("a" * 40)  # long opaque token-like string
    assert m.add_fact("主人在写毕业论文")
    m.save()
    assert "xai-" not in (tmp_path / "m.json").read_text()


def test_loading_drops_sensitive_entries_from_a_tampered_file(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"facts": ["正常", "xai-ZZZZZZZZZZZZZZ"], "recent": [{"t": 1, "s": "密码是1"}]}))
    m = MemoryStore(p)
    assert m.facts == ["正常"] and m.recent == []


def test_clear_empties_file_and_block(tmp_path):
    p = tmp_path / "m.json"
    m = MemoryStore(p)
    m.add_fact("喜欢猫")
    m.add_summary("聊了猫")
    m.save()
    m.clear()
    d = json.loads(p.read_text())
    assert d["facts"] == [] and d["recent"] == []
    assert MemoryStore(p).prompt_block() == ""


def test_daily_summary_limit_persisted(tmp_path):
    p = tmp_path / "m.json"
    m = MemoryStore(p)
    t = 1_800_000_000.0
    for _ in range(memory.SUMMARY_PER_DAY):
        assert m.can_summarize(t)
        m.note_summary_call(t)
    assert not m.can_summarize(t)
    assert not MemoryStore(p).can_summarize(t + 60)  # survives a restart
    assert MemoryStore(p).can_summarize(t + 86400 * 1.5)  # next day


def test_apply_summary_reply_variants(tmp_path):
    m = MemoryStore(tmp_path / "m.json")
    assert m.apply_summary_reply('好的：{"summary":"聊了周报","facts":["主人是前端工程师","xai-LEAKLEAKLEAK1"]} 谢谢')
    assert m.recent[-1]["s"] == "聊了周报" and m.facts == ["主人是前端工程师"]
    assert m.apply_summary_reply("主人今天在聊猫粮")  # plain text fallback
    assert not m.apply_summary_reply("")
    assert not m.apply_summary_reply('{"summary": "", "facts": []}')


def test_transcript_keeps_tail():
    h = [{"role": "user", "content": "你好" * 2000}, {"role": "assistant", "content": "结尾喵"}]
    t = memory.transcript_for_summary(h, 100)
    assert len(t) == 100 and t.endswith("结尾喵")


# ---- controller wiring ----
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def ctl(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    QApplication.instance() or QApplication([])
    from desk_pet_grok import chat as chat_mod
    from desk_pet_grok.bubble import BubbleWidget
    from desk_pet_grok.chat_panel import ChatPanel
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow

    started = []

    class FakeWorker:
        def __init__(self, messages, key, **kw):
            self.messages, self.key = messages, key
            self.completed = type("S", (), {"connect": lambda s, f: setattr(self, "cb", f)})()
            self.failed = self.cancelled = self.finished = self.token = self.completed
            started.append(self)

        def start(self): pass
        def isRunning(self): return False
        def wait(self, ms=0): return True
        def request_stop(self): pass

    monkeypatch.setattr(chat_mod, "StreamWorker", FakeWorker)
    monkeypatch.setattr(chat_mod.secrets, "get_api_key", lambda: "xai-testkeytestkey")

    def make(**st):
        sm = StateMachine()
        w = PetWindow(state_machine=sm, settings={"puppet25d": True, **st})
        c = chat_mod.ChatController(w, state_machine=sm, bubble=BubbleWidget(), panel=ChatPanel())
        c._idle_chatter_timer.stop()
        c._slow_timer.stop()
        return c, started

    return make


def test_memory_off_by_default_no_injection_no_calls(ctl):
    c, started = ctl()
    assert not c.memory_on and c._system_prompt() == __import__("desk_pet_grok.chat", fromlist=["x"]).SYSTEM_PROMPT
    c.send_user_text("你好")
    c._on_completed("你好喵")
    c.clear_chat()
    assert len(started) == 1  # only the chat request itself, no summary
    assert not (c.memory.path.exists())


def test_memory_injected_into_system_prompt_and_chat_request(ctl):
    c, started = ctl(memory=True)
    c.memory.add_fact("主人在写毕业论文")
    c.memory.add_summary("上次聊了第三章")
    c.send_user_text("我刚才在聊什么")
    sysmsg = started[-1].messages[0]["content"]
    assert "主人在写毕业论文" in sysmsg and "上次聊到：上次聊了第三章" in sysmsg
    assert len(sysmsg) <= len(__import__("desk_pet_grok.chat", fromlist=["x"]).SYSTEM_PROMPT) + 600


def test_summary_on_clear_chat_and_budget(ctl):
    c, started = ctl(memory=True)
    c.send_user_text("我在备考雅思")
    c._on_completed("加油喵")
    c.clear_chat()
    summ = [w for w in started if "JSON" in w.messages[0]["content"]]
    assert len(summ) == 1 and "我在备考雅思" in summ[0].messages[1]["content"]
    summ[0].cb('{"summary":"主人在备考雅思","facts":["主人在备考雅思"]}')
    assert c.memory.facts == ["主人在备考雅思"]
    # daily limit: 5 calls total per day
    for i in range(10):
        c.send_user_text(f"问题{i}")
        c._on_completed("嗯喵")
        c.clear_chat()
    assert len([w for w in started if "JSON" in w.messages[0]["content"]]) == memory.SUMMARY_PER_DAY


def test_periodic_summary_after_eight_messages(ctl):
    c, started = ctl(memory=True)
    for i in range(4):
        c.send_user_text(f"话{i}")
        c._on_completed("好喵")
    assert len([w for w in started if "JSON" in w.messages[0]["content"]]) == 1


def test_clear_memory_stops_quoting(ctl):
    c, started = ctl(memory=True)
    c.memory.add_fact("主人喜欢猫")
    assert "主人喜欢猫" in c._system_prompt()
    c.clear_memory()
    assert "主人喜欢猫" not in c._system_prompt()
    assert json.loads(c.memory.path.read_text())["facts"] == []


def test_toggle_off_discards_pending(ctl):
    c, started = ctl(memory=True)
    c.send_user_text("秘密话题")
    c.set_memory_on(False, persist=False)
    c._on_completed("嗯喵")
    c.clear_chat()
    assert not [w for w in started if "JSON" in w.messages[0]["content"]]
