"""F4: cross-session memory. Qt-free, local file ``memory.json`` in the config dir (mode 0600).

* facts   - stable things about the user (name they like, preferences, recurring topics), max ``MAX_FACTS``.
* recent  - one short summary per finished conversation chunk, max ``MAX_RECENT`` (oldest dropped first).
* The persona is fixed in the system prompt and is never changed by memory.
* ``prompt_block()`` is what gets appended to the system prompt, capped at ``BLOCK_MAX_CHARS``; oldest recent entries
  go first when it does not fit.
* Summaries cost one model call each: at most ``SUMMARY_PER_DAY`` per local day (counter persisted here).
* Privacy: anything that looks like an API key, or touches passwords / bank-card topics, is never stored; screen
  content is never passed in; ``clear()`` empties facts and recent."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

BLOCK_MAX_CHARS = 600
MAX_FACTS = 12
MAX_RECENT = 8
SUMMARY_PER_DAY = 5
ENTRY_MAX_CHARS = 120

_KEY_RE = re.compile(r"(xai-[A-Za-z0-9_\-]{8,}|sk-[A-Za-z0-9_\-]{8,}|[A-Za-z0-9_\-]{32,})")
_SENSITIVE_RE = re.compile(r"密码|口令|验证码|银行卡|信用卡|身份证|私钥|api[ _-]?key|password|passwd|token|cvv", re.I)

SUMMARY_PROMPT = (
    "下面是主人和桌宠小 Grok 的一段对话。请只输出一个 JSON 对象，不要多余文字：\n"
    '{"summary": "用一句话（不超过60字）概括聊了什么、主人的要点", "facts": ["主人长期稳定的信息或偏好，每条不超过30字，没有就给空数组"]}\n'
    "不要记录密码、Key、银行卡、身份证、验证码等敏感信息；不要编造。"
)


def is_storable(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and not _KEY_RE.search(t) and not _SENSITIVE_RE.search(t)


def _today(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(now))


class MemoryStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self.facts: list[str] = []
        self.recent: list[dict[str, Any]] = []  # {"t": epoch, "s": summary}
        self._usage: dict[str, Any] = {"day": "", "count": 0}
        self.load()

    @property
    def path(self) -> Path:
        if self._path is None:
            from desk_pet_grok import config

            self._path = config.config_dir() / "memory.json"
        return self._path

    # ---- persistence ----
    def load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(d, dict):
            return
        self.facts = [str(x) for x in d.get("facts", []) if isinstance(x, str) and is_storable(x)][-MAX_FACTS:]
        self.recent = [
            {"t": float(r.get("t", 0)), "s": str(r.get("s", ""))}
            for r in d.get("recent", [])
            if isinstance(r, dict) and is_storable(str(r.get("s", "")))
        ][-MAX_RECENT:]
        u = d.get("usage")
        if isinstance(u, dict):
            self._usage = {"day": str(u.get("day", "")), "count": int(u.get("count", 0) or 0)}

    def save(self) -> None:
        data = {"version": 1, "facts": self.facts, "recent": self.recent, "usage": self._usage}
        p = self.path
        tmp = p.with_suffix(".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)

    # ---- content ----
    @property
    def empty(self) -> bool:
        return not self.facts and not self.recent

    def add_fact(self, text: str) -> bool:
        t = (text or "").strip()[:ENTRY_MAX_CHARS]
        if not is_storable(t) or t in self.facts:
            return False
        self.facts.append(t)
        self.facts = self.facts[-MAX_FACTS:]
        return True

    def add_summary(self, text: str, now: float | None = None) -> bool:
        t = (text or "").strip()[:ENTRY_MAX_CHARS]
        if not is_storable(t):
            return False
        self.recent.append({"t": time.time() if now is None else now, "s": t})
        self.recent = self.recent[-MAX_RECENT:]
        return True

    def clear(self) -> None:
        self.facts, self.recent = [], []
        self.save()

    def prompt_block(self, limit: int = BLOCK_MAX_CHARS) -> str:
        """Text appended to the system prompt ('' when there is nothing to remember). Always <= ``limit`` chars."""
        if self.empty:
            return ""
        head = "\n以下是你对主人的记忆（只在相关时自然地用，不要逐条复述，不要说你在读记忆）：\n"
        parts: list[str] = []
        room = limit - len(head)
        facts = list(self.facts)
        recent = list(self.recent)
        lines: list[str] = []
        while facts or recent:
            # newest first within each group; facts are stable so they win the room before old summaries
            if facts:
                lines.append("· " + facts.pop())
            elif recent:
                r = recent.pop()
                lines.append("· 上次聊到：" + r["s"])
        out = ""
        for ln in lines:
            if len(out) + len(ln) + 1 > room:
                break
            out += ln + "\n"
        parts.append(head + out.rstrip("\n"))
        text = parts[0]
        return text[:limit] if out else ""

    # ---- summary budget ----
    def summaries_today(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        return int(self._usage["count"]) if self._usage.get("day") == _today(now) else 0

    def can_summarize(self, now: float | None = None) -> bool:
        return self.summaries_today(now) < SUMMARY_PER_DAY

    def note_summary_call(self, now: float | None = None) -> None:
        """Count one summary model call (call this when the request is sent, not when it succeeds)."""
        now = time.time() if now is None else now
        day = _today(now)
        if self._usage.get("day") != day:
            self._usage = {"day": day, "count": 0}
        self._usage["count"] = int(self._usage["count"]) + 1
        self.save()

    def apply_summary_reply(self, reply: str, now: float | None = None) -> bool:
        """Parse the model's JSON (tolerating wrapping text); falls back to the raw text as the summary."""
        reply = (reply or "").strip()
        summary, facts = "", []
        m = re.search(r"\{.*\}", reply, re.S)
        if m:
            try:
                d = json.loads(m.group(0))
                summary = str(d.get("summary", "") or "")
                facts = [str(x) for x in (d.get("facts") or []) if isinstance(x, (str, int, float))]
            except ValueError:
                summary = ""
        if not summary and not m:
            summary = reply
        ok = False
        for f in facts[:3]:
            ok |= self.add_fact(f)
        if summary:
            ok |= self.add_summary(summary, now)
        if ok:
            self.save()
        return ok


def transcript_for_summary(history: list[dict[str, Any]], max_chars: int = 3000) -> str:
    """Plain transcript of the given chat messages for the summary request (newest kept when too long)."""
    rows = []
    for m in history:
        who = "主人" if m.get("role") == "user" else "小Grok"
        rows.append(f"{who}：{str(m.get('content', '')).strip()}")
    text = "\n".join(rows)
    return text[-max_chars:]
