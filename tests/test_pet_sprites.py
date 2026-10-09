"""Sprite-preferring PetWidget tests (offscreen Qt)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from desk_pet_grok.pet import (
    PetWidget,
    list_sprite_paths,
    list_turn_frame_paths,
    list_walk_frame_paths,
)
from desk_pet_grok.state import PetState


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _write_tiny_png(path: Path, color: int = 0xFF4488FF) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = QImage(8, 8, QImage.Format.Format_ARGB32)
    img.fill(color)
    assert img.save(str(path)), f"failed to save {path}"


def test_list_sprite_paths(tmp_path: Path) -> None:
    assert list_sprite_paths(tmp_path) == {}
    _write_tiny_png(tmp_path / "sprites" / "front.png")
    _write_tiny_png(tmp_path / "sprites" / "side.png")
    _write_tiny_png(tmp_path / "sprites" / "quarter.png")
    found = list_sprite_paths(tmp_path)
    assert set(found) == {"front", "side", "quarter"}


def test_list_walk_frame_paths(tmp_path: Path) -> None:
    assert list_walk_frame_paths(tmp_path) == []
    walk = tmp_path / "sprites" / "walk"
    _write_tiny_png(walk / "02.png")
    _write_tiny_png(walk / "01.png")
    paths = list_walk_frame_paths(tmp_path)
    assert [p.name for p in paths] == ["01.png", "02.png"]


def test_list_turn_frame_paths(tmp_path: Path) -> None:
    assert list_turn_frame_paths(tmp_path) == []
    turn = tmp_path / "sprites" / "turn"
    _write_tiny_png(turn / "02.png")
    _write_tiny_png(turn / "01.png")
    paths = list_turn_frame_paths(tmp_path)
    assert [p.name for p in paths] == ["01.png", "02.png"]


def test_sprites_preferred_over_state_frames(qapp: QApplication, tmp_path: Path) -> None:
    for name in ("idle", "think"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    _write_tiny_png(tmp_path / "idle" / "01.png", 0xFFFF0000)
    _write_tiny_png(tmp_path / "sprites" / "front.png", 0xFF00FF00)
    _write_tiny_png(tmp_path / "sprites" / "side.png", 0xFF0000FF)

    pet = PetWidget(assets_root=tmp_path)
    pet.resize(120, 120)
    pet.set_state(PetState.idle)
    assert pet.using_sprites is True
    assert pet.missing_assets is False

    pet.set_motion(False, 0.0)
    assert pet._sprite_mode == "front"
    # No turn frames → go straight to side when moving
    pet.set_motion(True, 100.0)
    assert pet._sprite_mode == "side"


def test_walk_frames_used_when_moving(qapp: QApplication, tmp_path: Path) -> None:
    _write_tiny_png(tmp_path / "sprites" / "front.png")
    _write_tiny_png(tmp_path / "sprites" / "side.png")
    walk = tmp_path / "sprites" / "walk"
    _write_tiny_png(walk / "01.png", 0xFF111111)
    _write_tiny_png(walk / "02.png", 0xFF222222)
    _write_tiny_png(walk / "03.png", 0xFF333333)

    pet = PetWidget(assets_root=tmp_path)
    pet.resize(100, 100)
    assert pet.has_walk_frames is True
    pet.set_motion(False, 0.0)
    assert pet._sprite_mode == "front"
    # No turn frames → walk immediately
    pet.set_motion(True, 80.0)
    assert pet._sprite_mode == "walk"
    assert pet.anim.walk_frames_active is True
    pet.set_motion(False, 0.0)
    assert pet._sprite_mode == "front"
    assert pet.anim.walk_frames_active is False


def test_turn_sequence_before_walk(qapp: QApplication, tmp_path: Path) -> None:
    _write_tiny_png(tmp_path / "sprites" / "front.png")
    _write_tiny_png(tmp_path / "sprites" / "side.png")
    turn = tmp_path / "sprites" / "turn"
    for i in range(1, 5):
        _write_tiny_png(turn / f"0{i}.png", 0xFF000000 + i * 0x111111)
    walk = tmp_path / "sprites" / "walk"
    _write_tiny_png(walk / "01.png")
    _write_tiny_png(walk / "02.png")

    pet = PetWidget(assets_root=tmp_path)
    pet.resize(100, 100)
    assert pet.has_turn_frames is True
    pet.set_motion(False, 0.0)
    assert pet._sprite_mode == "front"

    pet.set_motion(True, 80.0)
    assert pet._sprite_mode == "turn"
    assert pet.turning is True
    assert pet.anim.walk_frames_active is False

    # Drain turn forward to completion
    for _ in range(20):
        pet._advance_turn()
        if pet._sprite_mode == "walk":
            break
    assert pet._sprite_mode == "walk"
    assert pet.anim.walk_frames_active is True

    # Stop → turn back toward front
    pet.set_motion(False, 0.0)
    assert pet._sprite_mode == "turn"
    for _ in range(20):
        pet._advance_turn()
        if pet._sprite_mode == "front":
            break
    assert pet._sprite_mode == "front"


def test_turn_reverses_if_motion_cancels(qapp: QApplication, tmp_path: Path) -> None:
    _write_tiny_png(tmp_path / "sprites" / "front.png")
    turn = tmp_path / "sprites" / "turn"
    for i in range(1, 6):
        _write_tiny_png(turn / f"0{i}.png")
    walk = tmp_path / "sprites" / "walk"
    _write_tiny_png(walk / "01.png")

    pet = PetWidget(assets_root=tmp_path)
    pet.set_motion(True, 50.0)
    assert pet._sprite_mode == "turn"
    pet._advance_turn()
    pet._advance_turn()
    mid = pet._turn_index
    pet.set_motion(False, 0.0)
    assert pet._turn_dir == -1
    assert pet._turn_index == mid


def test_no_sprites_falls_back_to_frames(qapp: QApplication, tmp_path: Path) -> None:
    (tmp_path / "idle").mkdir(parents=True, exist_ok=True)
    _write_tiny_png(tmp_path / "idle" / "01.png")
    pet = PetWidget(assets_root=tmp_path)
    pet.set_state(PetState.idle)
    assert pet.using_sprites is False
    assert pet.missing_assets is False


def test_set_motion_and_jump(qapp: QApplication, tmp_path: Path) -> None:
    _write_tiny_png(tmp_path / "sprites" / "front.png")
    pet = PetWidget(assets_root=tmp_path)
    pet.set_motion(True, 80.0)
    assert pet.anim.moving is True
    pet.play_jump()
    assert pet.anim.jumping()


def test_paint_clears_previous_pose(qapp: QApplication, tmp_path: Path) -> None:
    """Front→walk must not leave uncleared pixels from the previous pose."""
    # Distinct solid colors so leftover front pixels are obvious.
    _write_tiny_png(tmp_path / "sprites" / "front.png", 0xFFFF0000)  # opaque red
    _write_tiny_png(tmp_path / "sprites" / "side.png", 0xFF00FF00)
    walk = tmp_path / "sprites" / "walk"
    # Narrower walk sprite (still 8x8 but we draw after mode switch)
    _write_tiny_png(walk / "01.png", 0xFF0000FF)  # opaque blue

    pet = PetWidget(assets_root=tmp_path)
    pet.resize(64, 64)
    pet.set_motion(False, 0.0)
    assert pet._sprite_mode == "front"

    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    # Force a second paint in walk mode onto a fresh grab (widget clears itself).
    pet.set_motion(True, 80.0)
    assert pet._sprite_mode == "walk"
    pet.repaint()
    img2 = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)

    red_left = 0
    blue = 0
    for y in range(img2.height()):
        for x in range(img2.width()):
            c = img2.pixelColor(x, y)
            if c.alpha() < 200:
                continue
            if c.red() > 200 and c.green() < 80 and c.blue() < 80:
                red_left += 1
            if c.blue() > 200 and c.red() < 80 and c.green() < 80:
                blue += 1
    assert blue > 0, "walk (blue) sprite should be visible"
    assert red_left == 0, f"front (red) ghost pixels remained: {red_left}"

def test_paint_source_blit_no_wide_front_ghost(qapp: QApplication, tmp_path: Path) -> None:
    """Wider front then narrower walk must leave no opaque front pixels.

    Reproduces the macOS white-silhouette bug: front pose is wider than walk,
    so uncleared translucent buffers keep a front-shaped ghost around the walk
    sprite. Offscreen Source blit must zero those margin pixels.
    """
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtCore import Qt

    def write_rect_png(path: Path, w: int, h: int, rgba: tuple[int, int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.fillRect(0, 0, w, h, QColor(*rgba))
        p.end()
        assert img.save(str(path))

    write_rect_png(tmp_path / "sprites" / "front.png", 40, 40, (255, 0, 0, 255))
    write_rect_png(tmp_path / "sprites" / "side.png", 20, 40, (0, 255, 0, 255))
    write_rect_png(tmp_path / "sprites" / "walk" / "01.png", 16, 40, (0, 0, 255, 255))

    pet = PetWidget(assets_root=tmp_path)
    pet.resize(80, 80)
    pet.set_motion(False, 0.0)
    assert pet._sprite_mode == "front"
    pet.grab()  # force paint on offscreen platform

    pet.set_motion(True, 80.0)
    assert pet._sprite_mode == "walk"
    img = pet.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)

    red = blue = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() < 128:
                continue
            if c.red() > 200 and c.green() < 80 and c.blue() < 80:
                red += 1
            if c.blue() > 200 and c.red() < 80 and c.green() < 80:
                blue += 1
    assert blue > 0, "walk sprite missing"
    assert red == 0, f"front ghost pixels in margin: {red}"
    # Mask key must track the walk pose (actual QWidget.setMask is a no-op offscreen).
    assert pet._mask_key is not None
    assert pet._mask_key[0] == "walk"


def test_window_mask_key_tracks_pose(qapp: QApplication, tmp_path: Path) -> None:
    """Mask sync key must move front → walk even when the platform ignores setMask."""
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtCore import Qt

    def write_rect_png(path: Path, w: int, h: int, rgba: tuple[int, int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.fillRect(0, 0, w, h, QColor(*rgba))
        p.end()
        assert img.save(str(path))

    write_rect_png(tmp_path / "sprites" / "front.png", 48, 48, (255, 0, 0, 255))
    write_rect_png(tmp_path / "sprites" / "side.png", 24, 48, (0, 255, 0, 255))
    write_rect_png(tmp_path / "sprites" / "walk" / "01.png", 16, 48, (0, 0, 255, 255))

    pet = PetWidget(assets_root=tmp_path)
    pet.resize(100, 100)
    pet.set_motion(False, 0.0)
    pet.grab()  # force paint on offscreen platform
    assert pet._mask_key is not None
    assert pet._mask_key[0] == "front"
    front_key = pet._mask_key

    pet.set_motion(True, 80.0)
    pet.grab()
    assert pet._sprite_mode == "walk"
    assert pet._mask_key is not None
    assert pet._mask_key[0] == "walk"
    assert pet._mask_key != front_key
