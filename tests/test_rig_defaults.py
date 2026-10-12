"""F2: eye geometry from rig.json (D7) and rig on by default when assets are complete, with graceful fallback."""

from __future__ import annotations

import json
import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from desk_pet_grok import eyefx


@pytest.fixture
def restore_eyes():
    saved = (eyefx.EYES, eyefx.CLIP, eyefx.MAX_SHIFT)
    yield
    eyefx.EYES, eyefx.CLIP, eyefx.MAX_SHIFT = saved


def test_shipped_rig_json_matches_builtin_eye_constants():
    d = json.load(open(eyefx.Path(eyefx.__file__).resolve().parents[1] / "assets" / "rig25d" / "rig.json"))
    assert tuple(map(tuple, d["eyes"]["centres"])) == ((156.0, 210.0), (231.0, 210.0))
    assert eyefx.EYES == ((156.0, 210.0), (231.0, 210.0)) and eyefx.CLIP == (21.0, 17.0)


def test_load_rig_eyes_overrides(tmp_path, restore_eyes):
    p = tmp_path / "rig.json"
    p.write_text(json.dumps({"eyes": {"centres": [[100, 150], [180, 150]], "clip": [10, 8]}}))
    assert eyefx.load_rig_eyes(p)
    assert eyefx.EYES == ((100.0, 150.0), (180.0, 150.0)) and eyefx.CLIP == (10.0, 8.0)
    assert eyefx.MAX_SHIFT == (4.5, 2.6)


def test_load_rig_eyes_bad_or_missing_keeps_defaults(tmp_path, restore_eyes):
    before = eyefx.EYES
    assert not eyefx.load_rig_eyes(tmp_path / "nope.json")
    (tmp_path / "bad.json").write_text("{not json")
    assert not eyefx.load_rig_eyes(tmp_path / "bad.json")
    (tmp_path / "noeyes.json").write_text("{}")
    assert not eyefx.load_rig_eyes(tmp_path / "noeyes.json")
    assert eyefx.EYES == before


def _win(settings):
    from PySide6.QtWidgets import QApplication
    from desk_pet_grok.state import StateMachine
    from desk_pet_grok.window import PetWindow
    QApplication.instance() or QApplication([])
    return PetWindow(state_machine=StateMachine(), settings={"puppet25d": True, **settings})


def test_rig_default_unchanged_unless_rig_auto():
    assert _win({}).part_rig is False  # defaults stay as before
    assert _win({"part_rig": False, "rig_auto": True}).part_rig is False  # explicit user choice wins


def test_rig_auto_turns_rig_and_turn_on_when_assets_complete():
    w = _win({"rig_auto": True})
    assert w.part_rig is True and w.part_turn in (True, False)


def test_rig_auto_falls_back_and_logs_once(monkeypatch, caplog):
    from desk_pet_grok import partrig
    monkeypatch.setattr(partrig, "available", lambda root=None: False)
    with caplog.at_level(logging.WARNING, logger="desk_pet_grok"):
        w = _win({"rig_auto": True})
    assert w.part_rig is False
    msgs = [r for r in caplog.records if "part rig" in r.getMessage()]
    assert len(msgs) == 1
