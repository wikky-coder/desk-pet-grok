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
