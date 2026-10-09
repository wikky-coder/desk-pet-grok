"""Pet asset loader / placeholder (offscreen Qt)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from desk_pet_grok.pet import PetWidget, list_frame_paths
from desk_pet_grok.state import PetState


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_state_dirs(root: Path) -> None:
    for state in PetState:
        (root / state.value).mkdir(parents=True, exist_ok=True)


def _write_tiny_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(8, 8, QImage.Format.Format_ARGB32)
    img.fill(0xFF4488FF)
    assert img.save(str(path)), f"failed to save {path}"


def test_list_frame_paths_empty(tmp_path: Path) -> None:
    _make_state_dirs(tmp_path)
    assert list_frame_paths(PetState.idle, tmp_path) == []


def test_empty_assets_missing_flag(qapp: QApplication, tmp_path: Path) -> None:
    _make_state_dirs(tmp_path)
    pet = PetWidget(assets_root=tmp_path)
    pet.resize(120, 120)
    pet.set_state(PetState.idle)
    assert pet.missing_assets is True
    assert list_frame_paths(PetState.idle, tmp_path) == []


def test_idle_png_clears_missing(qapp: QApplication, tmp_path: Path) -> None:
    _make_state_dirs(tmp_path)
    _write_tiny_png(tmp_path / "idle" / "01.png")
    pet = PetWidget(assets_root=tmp_path)
    pet.resize(120, 120)
    pet.set_state(PetState.idle)
    assert pet.missing_assets is False
    frames = list_frame_paths(PetState.idle, tmp_path)
    assert len(frames) == 1
    assert frames[0].name == "01.png"


def test_missing_state_falls_back_to_idle(qapp: QApplication, tmp_path: Path) -> None:
    _make_state_dirs(tmp_path)
    _write_tiny_png(tmp_path / "idle" / "01.png")
    pet = PetWidget(assets_root=tmp_path)
    pet.set_state(PetState.think)
    assert pet.missing_assets is True
    assert pet.using_idle_fallback is True
