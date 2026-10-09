"""Tests for light CPU/RAM alerts (mocked psutil; no flake)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from desk_pet_grok.sysmon import (
    ALERT_COOLDOWN_S,
    MSG_CPU,
    MSG_RAM,
    SysMon,
    evaluate_alerts,
)


@pytest.fixture
def qapp() -> QApplication:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_evaluate_cpu_over_threshold() -> None:
    msg, last_cpu, last_ram = evaluate_alerts(
        91.0,
        50.0,
        last_cpu_alert=None,
        last_ram_alert=None,
        now=1000.0,
    )
    assert msg == MSG_CPU
    assert last_cpu == 1000.0
    assert last_ram is None


def test_evaluate_ram_over_threshold() -> None:
    msg, last_cpu, last_ram = evaluate_alerts(
        10.0,
        96.0,
        last_cpu_alert=None,
        last_ram_alert=None,
        now=1000.0,
    )
    assert msg == MSG_RAM
    assert last_cpu is None
    assert last_ram == 1000.0


def test_evaluate_cpu_wins_when_both_high() -> None:
    msg, last_cpu, last_ram = evaluate_alerts(
        95.0,
        99.0,
        last_cpu_alert=None,
        last_ram_alert=None,
        now=50.0,
    )
    assert msg == MSG_CPU
    assert last_cpu == 50.0
    assert last_ram is None


def test_evaluate_below_threshold_no_alert() -> None:
    msg, last_cpu, last_ram = evaluate_alerts(
        90.0,
        95.0,
        last_cpu_alert=None,
        last_ram_alert=None,
        now=1.0,
    )
    assert msg is None
    assert last_cpu is None
    assert last_ram is None


def test_evaluate_quiet_suppresses() -> None:
    msg, last_cpu, last_ram = evaluate_alerts(
        99.0,
        99.0,
        last_cpu_alert=None,
        last_ram_alert=None,
        now=1.0,
        quiet=True,
    )
    assert msg is None
    assert last_cpu is None
    assert last_ram is None


def test_evaluate_cpu_cooldown() -> None:
    msg1, last_cpu, last_ram = evaluate_alerts(
        99.0,
        10.0,
        last_cpu_alert=None,
        last_ram_alert=None,
        now=100.0,
    )
    assert msg1 == MSG_CPU
    msg2, last_cpu2, last_ram2 = evaluate_alerts(
        99.0,
        10.0,
        last_cpu_alert=last_cpu,
        last_ram_alert=last_ram,
        now=100.0 + ALERT_COOLDOWN_S - 1,
    )
    assert msg2 is None
    assert last_cpu2 == last_cpu
    msg3, last_cpu3, _ = evaluate_alerts(
        99.0,
        10.0,
        last_cpu_alert=last_cpu2,
        last_ram_alert=last_ram2,
        now=100.0 + ALERT_COOLDOWN_S,
    )
    assert msg3 == MSG_CPU
    assert last_cpu3 == 100.0 + ALERT_COOLDOWN_S


def test_evaluate_ram_cooldown_independent() -> None:
    """RAM can still fire while CPU is in cooldown."""
    _, last_cpu, _ = evaluate_alerts(
        99.0,
        10.0,
        last_cpu_alert=None,
        last_ram_alert=None,
        now=0.0,
    )
    msg, last_cpu2, last_ram = evaluate_alerts(
        99.0,
        96.0,
        last_cpu_alert=last_cpu,
        last_ram_alert=None,
        now=10.0,
    )
    assert msg == MSG_RAM
    assert last_cpu2 == last_cpu
    assert last_ram == 10.0


def test_sysmon_no_psutil_noop(qapp: QApplication) -> None:
    mon = SysMon(psutil_mod=None, parent=qapp)
    # Force unavailable path: construct with sentinel then override
    mon._available = False
    mon._psutil = None
    mon.start()
    assert not mon._timer.isActive()
    assert mon.poll_once() is None
    mon.stop()


def test_sysmon_apply_readings_emits(qapp: QApplication) -> None:
    fake = MagicMock()
    fake.cpu_percent.return_value = 0.0
    fake.virtual_memory.return_value = SimpleNamespace(percent=10.0)
    mon = SysMon(psutil_mod=fake, parent=qapp, cooldown_s=60.0)
    received: list[str] = []
    mon.alert.connect(received.append)

    assert mon.apply_readings(91.0, 10.0, now=1.0) == MSG_CPU
    assert received == [MSG_CPU]
    assert mon.apply_readings(91.0, 10.0, now=30.0) is None
    assert received == [MSG_CPU]
    assert mon.apply_readings(10.0, 96.0, now=30.0) == MSG_RAM
    assert received == [MSG_CPU, MSG_RAM]


def test_sysmon_respects_quiet_checker(qapp: QApplication) -> None:
    quiet = {"on": True}
    mon = SysMon(
        quiet_checker=lambda: quiet["on"],
        psutil_mod=MagicMock(),
        parent=qapp,
    )
    received: list[str] = []
    mon.alert.connect(received.append)
    assert mon.apply_readings(99.0, 99.0, now=1.0) is None
    assert received == []
    quiet["on"] = False
    assert mon.apply_readings(99.0, 50.0, now=2.0) == MSG_CPU
    assert received == [MSG_CPU]


def test_sysmon_poll_once_uses_psutil(qapp: QApplication) -> None:
    fake = MagicMock()
    fake.cpu_percent.return_value = 92.5
    fake.virtual_memory.return_value = SimpleNamespace(percent=40.0)
    mon = SysMon(psutil_mod=fake, parent=qapp)
    received: list[str] = []
    mon.alert.connect(received.append)
    # prime then poll
    mon._prime_cpu()
    fake.cpu_percent.return_value = 92.5
    assert mon.poll_once(now=5.0) == MSG_CPU
    assert received == [MSG_CPU]
    assert fake.cpu_percent.call_count >= 2


def test_sysmon_start_stop_with_fake(qapp: QApplication) -> None:
    fake = MagicMock()
    fake.cpu_percent.return_value = 1.0
    fake.virtual_memory.return_value = SimpleNamespace(percent=1.0)
    mon = SysMon(psutil_mod=fake, poll_ms=50_000, parent=qapp)
    mon.start()
    assert mon._timer.isActive()
    mon.stop()
    assert not mon._timer.isActive()
