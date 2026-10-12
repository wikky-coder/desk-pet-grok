"""Opt-in calibration log (settings ``calibration_log``, default OFF; nothing is written while off).

Records only numbers / booleans about gestures and window-edge motion (leg length, speed, edge displacement ...), never
window titles, text, or screen content: any non-numeric field is dropped. Local file in the config dir, mode 0600,
size-capped (the oldest half is dropped when the cap is hit)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

MAX_BYTES = 512 * 1024


class CalibrationLog:
    def __init__(self, path: Path | str | None = None, max_bytes: int = MAX_BYTES) -> None:
        self._path = Path(path) if path is not None else None
        self.max_bytes = max_bytes
        self.enabled = False

    @property
    def path(self) -> Path:
        if self._path is None:
            from desk_pet_grok import config

            self._path = config.config_dir() / "calibration.jsonl"
        return self._path

    def log(self, kind: str, **fields) -> None:
        if not self.enabled:
            return
        row = {"kind": str(kind), "t": round(time.time(), 3)}
        for k, v in fields.items():
            if isinstance(v, bool) or isinstance(v, int):
                row[k] = v
            elif isinstance(v, float):
                row[k] = round(v, 3)
        try:
            p = self.path
            fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
            os.chmod(p, 0o600)
            if p.stat().st_size > self.max_bytes:
                data = p.read_bytes()
                p.write_bytes(data[len(data) // 2:].split(b"\n", 1)[-1])
        except OSError:
            pass
