"""Display-only "喵" rule: every sentence of what the pet says ends with 喵 (before the closing punctuation).

``ensure_meow`` never touches code blocks, inline code, links, shell-like lines or pure numbers, and is idempotent.
It is applied to bubble text only; the chat history keeps the model's original reply."""

from __future__ import annotations

import re

MEOW = "喵"
_CLOSERS = "」』）)\"”’】》"
_END = "。！？!?…~～"
_TRAIL_RE = re.compile(r"[" + re.escape(_END + _CLOSERS) + r"\s]*$")
_SENT_RE = re.compile(
    r"([^" + re.escape(_END) + r"\n]+?)((?:[" + re.escape(_END) + r"]+|(?<!\d)\.(?=\s|$))[" + re.escape(_CLOSERS) + r"]*|$)"
)
_PROTECT_RE = re.compile(r"`[^`\n]*`|https?://\S+|www\.\S+")
_PH = "\x00"
_HAS_TEXT = re.compile(r"[A-Za-z\u4e00-\u9fff]")


def ends_with_meow(text: str) -> bool:
    body = _TRAIL_RE.sub("", text.rstrip())
    return body.endswith(MEOW)


def _fix_segment(body: str, tail: str) -> str:
    stripped = body.rstrip()
    if not stripped or not _HAS_TEXT.search(stripped.replace(_PH, "")):
        return body + tail
    if stripped.endswith(_PH) or stripped.endswith(MEOW):
        return body + tail
    lead = len(body) - len(body.lstrip())
    if not stripped[lead:].strip(" -*•0123456789.、)"):  # only a list marker
        return body + tail
    return stripped + MEOW + body[len(stripped):] + tail


def _fix_line(line: str) -> str:
    if line.lstrip().startswith(("$ ", ">", "#!", "```")):
        return line
    colon = re.search(r"[：:]\s*$", line)
    if colon and not line.rstrip().endswith("://"):
        return _fix_line(line[: colon.start()]) + line[colon.start():]
    saved: list[str] = []

    def hide(m: re.Match) -> str:
        saved.append(m.group(0))
        return _PH + str(len(saved) - 1) + _PH

    work = _PROTECT_RE.sub(hide, line)
    out = _SENT_RE.sub(lambda m: _fix_segment(m.group(1), m.group(2)), work)
    return re.sub(_PH + r"(\d+)" + _PH, lambda m: saved[int(m.group(1))], out)


def ensure_meow(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    res: list[str] = []
    fenced = False
    for ln in lines:
        if ln.lstrip().startswith("```"):
            fenced = not fenced
            res.append(ln)
        elif fenced:
            res.append(ln)
        else:
            res.append(_fix_line(ln))
    return "\n".join(res)
