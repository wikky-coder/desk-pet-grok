"""F1: tunable thresholds + opt-in calibration log (numeric-only, default off, no disk writes when off)."""

from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DESK_PET_GROK_CONFIG_DIR", "/tmp/desk-pet-grok-test-config")

from desk_pet_grok import dbglog, petting
from desk_pet_grok.focus_probe import FieldGeom
from desk_pet_grok.lounge import Lounge


def test_log_is_off_by_default_and_writes_nothing(tmp_path):
    log = dbglog.CalibrationLog(tmp_path / "cal.jsonl")
    assert not log.enabled
    log.log("pat_fold", leg=30.0)
    assert not (tmp_path / "cal.jsonl").exists()


def test_log_keeps_numbers_only(tmp_path):
    p = tmp_path / "cal.jsonl"
    log = dbglog.CalibrationLog(p)
    log.enabled = True
    log.log("pat_fold", leg=30.5, ok=True, title="secret window title", text=["x"], n=3)
    row = json.loads(p.read_text().splitlines()[0])
    assert row["kind"] == "pat_fold" and row["leg"] == 30.5 and row["ok"] is True and row["n"] == 3
    assert "title" not in row and "text" not in row and "t" in row
    assert oct(p.stat().st_mode & 0o777) == "0o600"


def test_log_is_size_capped(tmp_path):
    p = tmp_path / "cal.jsonl"
    log = dbglog.CalibrationLog(p, max_bytes=2000)
    log.enabled = True
    for i in range(500):
        log.log("x", i=i)
    assert p.stat().st_size <= 2000 + 200


def test_petting_events_reported():
    ev = []
    det = petting.PettingDetector("mid", on_event=lambda kind, **kw: ev.append((kind, kw)))
    t = 0.0
    for i in range(40):
        t += 0.05
        x = 200 + (40 if (i // 4) % 2 else -40)
        det.feed(t, x, 100, True)
    kinds = [k for k, _ in ev]
    assert "pat_fold" in kinds and "pat_trigger" in kinds
    fold = next(kw for k, kw in ev if k == "pat_fold")
    assert {"leg", "speed", "ok"} <= set(fold)


def test_petting_param_overrides():
    p = petting.params_for("mid", {"mid": {"reversals": 5, "min_swing": 50}})
    assert p.reversals == 5 and p.min_swing == 50.0 and p.min_speed == petting.PARAMS["mid"].min_speed
    assert petting.params_for("mid", {"mid": {"reversals": "bad"}}).reversals == petting.PARAMS["mid"].reversals
    assert petting.params_for("low", None) == petting.PARAMS["low"]


def test_lounge_fall_thresholds_configurable_and_logged():
    ev = []
    lg = Lounge(enabled=True, selfwalk=False, on_event=lambda kind, **kw: ev.append((kind, kw)))
    lg.fall_gap, lg.fall_follow = 100.0, 70.0
    g = FieldGeom(0, 300, 800, 500)
    lg.on_drop(g, 400)
    lg.tick(0.1, g)
    lg.tick(0.1, FieldGeom(0, 360, 800, 500))  # 60 px drop: below the 100 px gap
    assert lg.state != "fall"
    assert any(k == "edge_drop" for k, _ in ev)
    lg.tick(0.1, FieldGeom(0, 420, 800, 500))  # 120 px: falls
    assert lg.state == "fall" and any(k == "fall" for k, _ in ev)


def test_window_applies_settings(tmp_path):
    from PySide6.QtWidgets import QApplication
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    QApplication.instance() or QApplication([])
    os.environ["DESK_PET_GROK_CONFIG_DIR"] = str(tmp_path)
    w = PetWindow(state_machine=StateMachine(), settings={
        "puppet25d": True, "lounge_fall_gap": 90, "lounge_fall_follow": 40,
        "petting_params": {"mid": {"reversals": 6}}, "calibration_log": True})
    assert w._lounge.lounge.fall_gap == 90.0 and w._lounge.lounge.fall_follow == 40.0
    assert w._pat_det.params.reversals == 6
    assert w.calibration_log is True
    w2 = PetWindow(state_machine=StateMachine(), settings={"puppet25d": True})
    assert w2.calibration_log is False and w2._lounge.lounge.fall_gap == 48.0
