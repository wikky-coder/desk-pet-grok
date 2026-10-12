"""Persistent app settings for 桌宠grok."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

_SETTINGS_NAME = "settings.json"

_DEFAULTS: dict[str, Any] = {
    "window_x": None,
    "window_y": None,
    "window_width": None,
    "window_height": None,
    "quiet": False,
    "penetrate": False,
    "bubble_visible": True,
    "motion_mode": "wander",
    "city": "Hong Kong",
    "autostart": False,
    "lounge": False,  # lie on the top edge of the front window (needs part rig assets)
    "lounge_selfwalk": True,  # occasionally walk over by herself after >=10 min idle (only when lounge is on)
    "lounge_ax": False,  # lounge on the focused input field via Accessibility (falls back to window edge)
    # "part_rig" / "part_turn" are intentionally absent: an absent key means "never chosen", so ``rig_auto`` may decide.
    "rig_auto": False,  # when part_rig/part_turn were never chosen: turn them on if the rig assets are complete
    "look_at_mouse": True,  # passive: only the eyes (irises) follow the cursor; head/body never turn
    "petting": True,  # head-pat reaction when the cursor is stroked back and forth over her head
    "petting_level": "mid",  # low | mid | high
    "memory": False,  # cross-session memory (summaries via the API, <=5/day; local memory.json 0600)
    "proactive_talk": True,  # False: she only speaks when you click / pat / drop her (no unprompted lines at all)
    "proactive_v2": False,  # True: every unprompted line goes through the limiter (<=3/h, >=5 min apart) + local events
    "proactive_max_per_hour": 3,
    "proactive_min_gap_s": 300.0,
    "onboarded": False,  # first-run guide shown (only ever shown on a fresh install)
    "power_save": False,  # v4-5 省电模式（默认关）
    "time_greeting": True,  # v4-4 时段问候（默认开）
    "holiday_outfit": True,  # v4-4 节日小饰品（默认开）
    "greeted": {},  # {period: "YYYY-MM-DD"} periods already greeted today
    "holiday_greeted": "",
    "work_along": False,  # v4-6 陪你做事（只读前台软件名）
    "cling_edge": False,  # v4-3 贴边扒着
    "shake_anger": False,  # v4-2 甩她会红温（需部件骨架素材）
    "fullscreen_hide": False,  # v4-1 全屏应用时自动隐藏
    "hotkey_hide": False,  # v4-1 全局快捷键
    "hotkey_combo": "ctrl+alt+p",
    "tail_boost": True,  # F8 「尾巴摆动增强」
    "lounge_variant_interval": [40, 120],  # seconds: each pose change waits a fresh uniform random time in [min, max] (clamped 10..900)
    "lounge_variants": False,  # F7: random lying poses (side / chin-on-hand / stretch / curled-up sleep); off = the one loaf pose
    "mood": False,  # F6: mood layer (happy / sleepy / annoyed / surprised / pouty faces); off = unchanged behaviour
    "calibration_log": False,  # advanced: numeric-only gesture/edge log for threshold tuning (off = no disk writes)
    "petting_params": None,  # optional {level: {reversals,min_swing,min_speed,window_s,hold_s}} overrides
    "lounge_fall_gap": None,  # optional px override of lounge.FALL_GAP
    "lounge_fall_follow": None,  # optional px/s override of lounge.FALL_FOLLOW
    "screen_aware": False,  # tier 1: read front app name / window title (free)
    "screen_vision": False,  # tier 2: allow screenshots + vision API remarks (costs quota)
    "screen_proactive": False,  # low-frequency unprompted remarks (needs screen_vision)
    "screen_pause_until": 0,  # epoch seconds; focus / pause button
    "screen_quiet_hours": False,  # 22:00-08:00 no screenshots
    "screen_limit_hour": 3,
    "screen_limit_day": 20,
    "screen_blacklist": None,  # None = built-in default list; a list replaces it
    "screen_model": None,
    "screen_usage": {},  # {"day","count","stamps"} persisted usage counter
}


def config_dir() -> Path:
    """Return the app config directory, creating it if needed."""
    override = os.environ.get("DESK_PET_GROK_CONFIG_DIR")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / "desk-pet-grok"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "desk-pet-grok"
    else:
        path = Path.home() / ".config" / "desk-pet-grok"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_path() -> Path:
    return config_dir() / _SETTINGS_NAME


def load_settings() -> dict[str, Any]:
    """Load settings JSON; missing keys fall back to defaults."""
    path = _settings_path()
    data: dict[str, Any] = dict(_DEFAULTS)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return data
        if isinstance(raw, dict):
            for key in _DEFAULTS:
                if key in raw:
                    data[key] = raw[key]
    return data


def save_settings(data: dict[str, Any]) -> None:
    """Persist known settings keys to disk."""
    merged = load_settings()
    for key in _DEFAULTS:
        if key in data:
            merged[key] = data[key]
    path = _settings_path()
    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
