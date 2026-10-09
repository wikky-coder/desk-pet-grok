# 桌宠grok v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a first-version macOS/Windows desktop pet that chats via xAI Responses API (`grok-4.7` streaming), with transparent always-on-top UI and slots ready for the blonde catgirl short-loop assets.

**Architecture:** PySide6 single-instance app: frameless translucent pet window + tray; finite state machine drives asset playback and bubbles; `httpx` streams `POST https://api.x.ai/v1/responses`; API key stored outside the repo. Assets are optional in v1 (colored circle placeholder). Local tools wait for v2.

**Tech Stack:** Python 3.11+, PySide6, httpx, pytest

**Specs:**
- Original: user-provided 桌宠助手实现规格 （桌宠grok）
- Audit design: `docs/superpowers/specs/2026-10-09-desk-pet-grok-avatar-audit-design.md`

## Global Constraints

- Dependencies only: `PySide6`, `httpx` (plus `pytest` for tests). No OpenAI SDK wrapper required for runtime.
- Model: `grok-4.7`. Endpoint: `POST https://api.x.ai/v1/responses` with `stream: true`.
- Do not log, echo, or commit API keys. Prefer `XAI_API_KEY`, else `0600` key file under app config dir.
- Product dir name `desk-pet-grok`; product/window title `桌宠grok`. About text: not DeepSeek, not official xAI product; chat is not the same session as grok.com / Grok App / Grok Bot. Decorative Grok/X marks on art ≠ official branding.
- No screen capture, no global hooks, no shell tools in v1.
- Platforms: Windows 10/11 x64 and macOS 12+ required; Linux best-effort.
- Character baseline (do not rewrite art): blonde chibi catgirl, X hair clip, Grok slash-ring necklace. Implementer must not regenerate or alter provided frames.
- After first visible stream token, leave `think` and use `idle` light loop + streaming bubble (no separate `reply` folder in v1).
- Asset canvas guidance 412×344 with ≥8% margin for ears/tail/clip; sequences target 6–8 frames (min 4); missing sequence falls back to `idle` + bubble hint.

## File map

```text
desk-pet-grok/
  README.md
  requirements.txt
  run.py
  desk_pet_grok/
    __init__.py
    app.py
    window.py
    pet.py
    bubble.py
    chat_panel.py
    menu.py
    state.py
    api.py
    config.py
    secrets.py
    about.py
  assets/
    README.md
    idle/ think/ work/ wait/ done/ error/ sleep/
  tests/
    test_state.py
    test_api_parse.py
    test_secrets.py
  docs/superpowers/specs/...
  docs/superpowers/plans/...
```

---

### Task 1: Scaffold + requirements + run entry

**Files:**
- Create: `requirements.txt`, `run.py`, `desk_pet_grok/__init__.py`, `README.md`
- Test: `tests/test_import.py`

**Interfaces:**
- Produces: package `desk_pet_grok` importable; `python run.py` starts later once `app.main()` exists (stub ok until Task 3).

- [ ] **Step 1: Write failing import test**

```python
# tests/test_import.py
def test_package_imports():
    import desk_pet_grok
    assert desk_pet_grok.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test — expect fail**

Run: `pytest tests/test_import.py -v`  
Expected: FAIL (no package / no `__version__`)

- [ ] **Step 3: Minimal scaffold**

```text
# requirements.txt
PySide6>=6.6
httpx>=0.27
pytest>=8.0
```

```python
# desk_pet_grok/__init__.py
__version__ = "0.1.0"
```

```python
# run.py
from desk_pet_grok.app import main

if __name__ == "__main__":
    raise SystemExit(main())
```

```markdown
# 桌宠grok
本机桌宠。对话走 xAI API，与 Grok 网页 / App / Grok Bot 不是同一会话。非官方产品。
```

- [ ] **Step 4: Pass import test, commit**

```bash
pytest tests/test_import.py -v
git add requirements.txt run.py desk_pet_grok/__init__.py README.md tests/test_import.py
git commit -m "chore: scaffold 桌宠grok package"
```

---

### Task 2: Config + secrets

**Files:**
- Create: `desk_pet_grok/config.py`, `desk_pet_grok/secrets.py`
- Test: `tests/test_secrets.py`

**Interfaces:**
- Produces:
  - `config_dir() -> Path`
  - `load_settings() -> dict` / `save_settings(data: dict) -> None` (window pos/size, quiet, penetrate, bubble visible)
  - `get_api_key() -> str | None`
  - `set_api_key(key: str) -> None` (writes key file mode 0o600 on Unix)
  - Env `XAI_API_KEY` wins over file.

- [ ] **Step 1: Failing tests for key precedence**

```python
# tests/test_secrets.py
import os
from pathlib import Path
import desk_pet_grok.secrets as secrets

def test_env_beats_file(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    secrets.set_api_key("file-key")
    monkeypatch.setenv("XAI_API_KEY", "env-key")
    assert secrets.get_api_key() == "env-key"

def test_file_key_when_no_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DESK_PET_GROK_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    secrets.set_api_key("file-key")
    assert secrets.get_api_key() == "file-key"
```

- [ ] **Step 2: Implement `config.py` / `secrets.py` using `DESK_PET_GROK_CONFIG_DIR` override for tests; default Windows `%APPDATA%/desk-pet-grok`, macOS `~/Library/Application Support/desk-pet-grok`**

- [ ] **Step 3: pytest pass + commit** `feat: add config and api key storage`

---

### Task 3: State machine

**Files:**
- Create: `desk_pet_grok/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `class PetState(Enum)` with `idle, think, work, wait, done, error, sleep`
- `class StateMachine` with `state`, `set(next)`, priority rule: `wait > error > work > think > done > sleep > idle`
- Events: `on_send`, `on_first_token`, `on_stream_end`, `on_error`, `on_tool_need_confirm` (v2 stub), `enter_quiet`, `leave_quiet`
- After `on_first_token`: leave `think` → `idle` (still streaming in bubble)

- [ ] **Step 1: Write failing transition tests** covering send→think, first token→idle, error, done→idle after timer hook (timer can be manual `tick_done_elapsed()` in tests)

- [ ] **Step 2: Implement minimal state machine**

- [ ] **Step 3: Pass tests + commit** `feat: pet state machine`

---

### Task 4: Asset player + placeholder

**Files:**
- Create: `desk_pet_grok/pet.py`, `assets/README.md`, empty `assets/{idle,think,work,wait,done,error,sleep}/`
- Test: `tests/test_pet_assets.py`

**Interfaces:**
- Produces: `class PetWidget(QWidget)` showing current frame; `set_state(PetState)`; loads sorted `*.webp|*.png` from folder; if empty, draw solid circle placeholder and expose `missing_assets: bool`
- Canvas display scales with window height; authoring guide 412×344, ≥8% safe margin documented in `assets/README.md`

- [ ] **Step 1: Test that empty folder yields placeholder path / flag**

- [ ] **Step 2: Implement loader + QPainter circle fallback**

- [ ] **Step 3: Commit** `feat: pet asset player with placeholder`

---

### Task 5: Frameless window, drag, tray, single instance

**Files:**
- Create: `desk_pet_grok/app.py`, `desk_pet_grok/window.py`, `desk_pet_grok/menu.py`
- Manual check listed below (GUI)

**Interfaces:**
- `main() -> int` creates `QApplication`, `QLocalServer`/`QSharedMemory` single-instance, system tray, `PetWindow`
- Flags: `FramelessWindowHint | WindowStaysOnTopHint | Tool`, `WA_TranslucentBackground`
- Default height 220 (clamp 140–360); persist geometry via `config`
- Left-drag moves; single-click play reaction; double-click opens chat panel (wired in Task 7); right-click shared menu

- [ ] **Step 1: Implement window + tray menus (size, quiet, penetrate, always-on-top, bubble toggle, set key dialog stub, clear chat, quit, about)**

- [ ] **Step 2: Manual** `python run.py` — drag, resize menu, quit from tray; second process focuses first

- [ ] **Step 3: Commit** `feat: transparent pet window and tray`

---

### Task 6: Streaming API client

**Files:**
- Create: `desk_pet_grok/api.py`
- Test: `tests/test_api_parse.py`

**Interfaces:**
- Produces: `async def stream_response(*, messages: list[dict], api_key: str, model: str = "grok-4.7") -> AsyncIterator[str]`
- POST `https://api.x.ai/v1/responses` JSON `{"model","input","stream": true}` (map chat history into Responses `input` per current xAI docs)
- Timeout 120s; cancel via `httpx` close
- Parse SSE/stream events for text deltas; ignore unknown events; never return headers/key on errors — map 401/429/timeout to typed errors: `AuthError`, `RateLimitError`, `TimeoutError`

- [ ] **Step 1: Unit-test parser against fixture byte chunks (no live network)**

- [ ] **Step 2: Implement client + parser**

- [ ] **Step 3: Commit** `feat: xAI responses streaming client`

---

### Task 7: Bubble + chat panel + wire chat loop

**Files:**
- Create: `desk_pet_grok/bubble.py`, `desk_pet_grok/chat_panel.py`, `desk_pet_grok/about.py`
- Modify: `desk_pet_grok/window.py`, `desk_pet_grok/app.py`, `desk_pet_grok/menu.py`

**Interfaces:**
- Bubble max ~80 Chinese chars preview; full text in panel scroll
- System prompt exactly as original spec (desktop assistant via xAI API; language match user; no false tool claims; no ask for key; not same session as Grok surfaces)
- History: last 20 messages in memory only
- Copy strings: `在想。` / Key missing / `Key 无效。` / `请求太密，稍后再试。` / `这一轮超时了。`
- Stop button cancels stream
- Key settings: password field; probe with short non-stream request before save; UI shows 已保存/未保存 only

- [ ] **Step 1: Implement bubble + panel UI**

- [ ] **Step 2: Wire send → state think → stream → first token idle → done/error**

- [ ] **Step 3: Manual acceptance from original spec §验收 1–7 (user supplies key)**

- [ ] **Step 4: Commit** `feat: chat bubble and streaming loop`

---

### Task 8: Fold audit design into README + assets README

**Files:**
- Modify: `README.md`, `assets/README.md`
- Optional: keep `docs/superpowers/specs/2026-10-09-desk-pet-grok-avatar-audit-design.md` as source of truth for art

- [ ] **Step 1: Document character baseline, sequence fps, safe margin, think→idle after first token, brand disclaimer**

- [ ] **Step 2: Commit** `docs: align README with avatar audit design`

---

### Task 9: Stop for user trial (v1 gate)

**Files:** none

- [ ] **Step 1: Run through acceptance checklist with user Key**
- [ ] **Step 2: Do not start v2 tools until user signs off**

---

## Out of scope (explicit)

- v2 tools: `read_clipboard`, `open_url`, `read_note`/`write_note`, `list_allowed_dir`
- Live2D, auto-update, accounts
- Generating final catgirl frame sequences (user/art pipeline); code only consumes folders

## Spec coverage self-check

| Spec / audit item | Task |
| --- | --- |
| Scaffold, deps, run | 1 |
| Config dirs + key storage | 2 |
| State machine + first-token leaves think | 3 |
| Assets / placeholder / margins docs | 4, 8 |
| Window, tray, single instance | 5 |
| Responses streaming API | 6 |
| Bubble, panel, prompts, errors, about | 7 |
| User trial gate before tools | 9 |
| No SuperGrok-as-API | 2, 6, 8 |

