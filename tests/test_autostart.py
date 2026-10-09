"""Tests for open-at-login helpers (temp HOME; no real LaunchAgents)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

import pytest

from desk_pet_grok import autostart


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()

    def _home() -> Path:
        return home

    monkeypatch.setattr(Path, "home", staticmethod(_home))
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "desk-pet-grok"
    root.mkdir()
    (root / "run.py").write_text("# stub\n", encoding="utf-8")
    venv_bin = root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    py = venv_bin / "python"
    py.write_text("#!/bin/sh\n", encoding="utf-8")
    py.chmod(0o755)
    return root


def test_resolve_python_prefers_venv(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    resolved = autostart.resolve_python(project)
    assert resolved == (project / ".venv" / "bin" / "python").resolve()


def test_resolve_python_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    root = tmp_path / "bare"
    root.mkdir()
    (root / "run.py").write_text("#\n", encoding="utf-8")
    resolved = autostart.resolve_python(root)
    assert resolved == Path(sys.executable).resolve()


def test_macos_enable_writes_plist(
    fake_home: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert autostart.is_enabled() is False
    autostart.enable(project)
    plist_path = fake_home / "Library" / "LaunchAgents" / autostart.PLIST_NAME
    assert plist_path.is_file()
    assert autostart.is_enabled() is True
    with plist_path.open("rb") as fh:
        data = plistlib.load(fh)
    assert data["Label"] == autostart.PLIST_LABEL
    assert data["RunAtLoad"] is True
    args = data["ProgramArguments"]
    assert args[0].endswith("/.venv/bin/python")
    assert args[1].endswith("/run.py")
    assert data["EnvironmentVariables"]["PYTHONPATH"] == str(project.resolve())
    assert data["WorkingDirectory"] == str(project.resolve())


def test_macos_disable_removes_plist(
    fake_home: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    autostart.enable(project)
    autostart.disable()
    plist_path = fake_home / "Library" / "LaunchAgents" / autostart.PLIST_NAME
    assert not plist_path.exists()
    assert autostart.is_enabled() is False


def test_linux_enable_writes_desktop(
    fake_home: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    autostart.enable(project)
    desk = fake_home / ".config" / "autostart" / autostart.LINUX_DESKTOP_NAME
    assert desk.is_file()
    text = desk.read_text(encoding="utf-8")
    assert "Name=桌宠grok" in text
    assert "PYTHONPATH=" in text
    assert "run.py" in text
    assert autostart.is_enabled() is True
    autostart.disable()
    assert not desk.exists()
    assert autostart.is_enabled() is False


def test_enable_missing_run_py(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        autostart.enable(empty)
