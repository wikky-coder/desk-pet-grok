"""Light CPU / RAM alerts for 桌宠grok (optional psutil)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

POLL_INTERVAL_MS = 10_000
CPU_THRESHOLD = 90.0
RAM_THRESHOLD = 95.0
ALERT_COOLDOWN_S = 120.0

MSG_CPU = "「CPU 有点高…」"
MSG_RAM = "「内存快满了…」"

try:
    import psutil as _psutil

    HAS_PSUTIL = True
except ImportError:  # pragma: no cover - exercised via no-op paths / mocks
    _psutil = None  # type: ignore[assignment]
    HAS_PSUTIL = False


def evaluate_alerts(
    cpu_percent: float,
    ram_percent: float,
    *,
    last_cpu_alert: float | None,
    last_ram_alert: float | None,
    now: float,
    quiet: bool = False,
    cpu_threshold: float = CPU_THRESHOLD,
    ram_threshold: float = RAM_THRESHOLD,
    cooldown_s: float = ALERT_COOLDOWN_S,
) -> tuple[str | None, float | None, float | None]:
    """Decide whether to alert.

    Returns ``(message_or_None, new_last_cpu, new_last_ram)``.
    Quiet mode suppresses all alerts. CPU is checked before RAM if both high.
    Cooldown is per alert type.
    """
    if quiet:
        return None, last_cpu_alert, last_ram_alert

    def cooled(last: float | None) -> bool:
        if last is None:
            return True
        return (now - last) >= cooldown_s

    if cpu_percent > cpu_threshold and cooled(last_cpu_alert):
        return MSG_CPU, now, last_ram_alert
    if ram_percent > ram_threshold and cooled(last_ram_alert):
        return MSG_RAM, last_cpu_alert, now
    return None, last_cpu_alert, last_ram_alert


class SysMon(QObject):
    """Poll CPU/RAM and emit short Chinese bubble lines when thresholds trip.

    If ``psutil`` is missing, ``start`` / ``stop`` are no-ops and no polling runs.
    """

    alert = Signal(str)

    def __init__(
        self,
        *,
        quiet_checker: Callable[[], bool] | None = None,
        poll_ms: int = POLL_INTERVAL_MS,
        cpu_threshold: float = CPU_THRESHOLD,
        ram_threshold: float = RAM_THRESHOLD,
        cooldown_s: float = ALERT_COOLDOWN_S,
        psutil_mod: Any | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._quiet_checker = quiet_checker or (lambda: False)
        self._poll_ms = int(poll_ms)
        self._cpu_threshold = float(cpu_threshold)
        self._ram_threshold = float(ram_threshold)
        self._cooldown_s = float(cooldown_s)
        if psutil_mod is not None:
            self._psutil = psutil_mod
            self._available = True
        else:
            self._psutil = _psutil
            self._available = bool(HAS_PSUTIL and self._psutil is not None)

        self._last_cpu_alert: float | None = None
        self._last_ram_alert: float | None = None
        self._primed = False
        self._timer = QTimer(self)
        self._timer.setInterval(self._poll_ms)
        self._timer.timeout.connect(self._on_tick)

    @property
    def available(self) -> bool:
        return self._available

    def start(self) -> None:
        """Begin polling; no-op without psutil."""
        if not self._available:
            return
        self._prime_cpu()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        """Stop polling; always safe to call."""
        self._timer.stop()

    def _prime_cpu(self) -> None:
        """Discard first cpu_percent(interval=None) sample (meaningless)."""
        if not self._available or self._psutil is None:
            return
        try:
            self._psutil.cpu_percent(interval=None)
        except Exception:  # noqa: BLE001
            pass
        self._primed = True

    def _read(self) -> tuple[float, float] | None:
        if not self._available or self._psutil is None:
            return None
        try:
            cpu = float(self._psutil.cpu_percent(interval=None))
            ram = float(self._psutil.virtual_memory().percent)
            return cpu, ram
        except Exception:  # noqa: BLE001
            return None

    def _on_tick(self) -> None:
        self.poll_once()

    def poll_once(self, *, now: float | None = None) -> str | None:
        """Read metrics and maybe emit ``alert``. Returns message if emitted.

        ``now`` is injectable for tests (monotonic seconds).
        """
        if not self._available:
            return None
        if not self._primed:
            self._prime_cpu()
        readings = self._read()
        if readings is None:
            return None
        cpu, ram = readings
        return self.apply_readings(cpu, ram, now=now)

    def apply_readings(
        self,
        cpu_percent: float,
        ram_percent: float,
        *,
        now: float | None = None,
        quiet: bool | None = None,
    ) -> str | None:
        """Apply thresholds/cooldown with explicit readings (testable)."""
        t = time.monotonic() if now is None else now
        is_quiet = self._quiet_checker() if quiet is None else quiet
        msg, self._last_cpu_alert, self._last_ram_alert = evaluate_alerts(
            cpu_percent,
            ram_percent,
            last_cpu_alert=self._last_cpu_alert,
            last_ram_alert=self._last_ram_alert,
            now=t,
            quiet=is_quiet,
            cpu_threshold=self._cpu_threshold,
            ram_threshold=self._ram_threshold,
            cooldown_s=self._cooldown_s,
        )
        if msg:
            self.alert.emit(msg)
        return msg
