# 桌宠grok v2 Feature Plan (dafeiyu-inspired)

> **For agentic workers:** Use subagent-driven-development or executing-plans. Checkbox steps.

**Goal:** Add wander / follow-mouse / drag facing, random lines + click interact, weather bubble, light CPU/RAM alerts, autostart + packaging — modular, without collapsing into one mega-file.

**Architecture:** Keep `desk_pet_grok` modules. New: `motion.py` (modes + physics), `lines.py` (台词), `weather.py`, `sysmon.py`, `autostart.py`; wire via menu/window. Optional `psutil` only for sysmon.

**Tech:** Python 3.11+, PySide6, httpx; add `psutil` for monitor; packaging via PyInstaller later.

## Global Constraints

- Product 桌宠grok; package `desk_pet_grok`; no DeepSeek keys/copy; xAI chat stays as-is.
- Modular files; do not merge into single 桌宠.py.
- Chat open → pause wander/follow but keep breath animation.
- Persist mode, size, penetrate, topmost, city in settings.json.
- MIT-friendly original code; inspire from dafeiyu-pet, do not paste their proprietary lines.

---

### Task A: Motion modes + drag facing

**Files:** Create `desk_pet_grok/motion.py`; modify `window.py`, `menu.py`, `config.py`, `pet.py` (optional flip).

**Produces:** Mode enum `wander|follow|still`; tick moves window with inertia; follow cursor; drag sets facing (mirror pixmap); menu mode group.

- [ ] Unit-test motion step math without GUI
- [ ] Wire timer on PetWindow
- [ ] Commit `feat: wander follow and drag facing`

### Task B: Random lines + click interact

**Files:** `desk_pet_grok/lines.py`; wire click→bubble say; optional jump scale anim.

- [ ] Lines lists (original, mild cute Grok tone, not DS memes)
- [ ] Click shows bubble line; double-click remains chat
- [ ] Commit `feat: random lines and click interact`

### Task C: Weather bubble

**Files:** `desk_pet_grok/weather.py`; menu「查看天气」; city in settings (default Hong Kong / 香港).

- [ ] Fetch wttr.in JSON via httpx; bubble short Chinese line
- [ ] Commit `feat: weather bubble`

### Task D: CPU/RAM alerts

**Files:** `desk_pet_grok/sysmon.py`; optional dependency psutil.

- [x] Poll every 10s; bubble if CPU>90% or RAM>95%; cooldown
- [x] Commit `feat: light cpu ram alerts`

### Task E: Autostart + packaging

**Files:** `desk_pet_grok/autostart.py`; menu toggle; `scripts/build_mac.sh` / notes in README; optional Windows later.

- [ ] macOS Login Items or LaunchAgent plist user-level
- [ ] Document PyInstaller one-file windowed with assets
- [ ] Commit `feat: autostart and packaging docs`

### Task F: Sync to user Desktop + brief trial notes

