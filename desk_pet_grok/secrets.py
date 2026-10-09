"""API key storage. Never log the key value."""

from __future__ import annotations

import os
from pathlib import Path

from desk_pet_grok.config import config_dir

_KEY_NAME = "xai_api_key"


def _key_path() -> Path:
    return config_dir() / _KEY_NAME


def get_api_key() -> str | None:
    """Return XAI API key: env XAI_API_KEY wins over file."""
    env = os.environ.get("XAI_API_KEY")
    if env is not None and env.strip():
        return env.strip()
    path = _key_path()
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def set_api_key(key: str) -> None:
    """Write API key to config dir; mode 0o600 on Unix."""
    path = _key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key.strip() + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        # Windows / unsupported chmod — ignore
        pass
