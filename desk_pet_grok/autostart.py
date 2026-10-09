"""Open-at-login helpers for 桌宠grok (LaunchAgent / Run key / .desktop)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

PLIST_LABEL = "com.desk-pet-grok"
PLIST_NAME = "com.desk-pet-grok.plist"
WINDOWS_RUN_VALUE = "DeskPetGrok"
LINUX_DESKTOP_NAME = "desk-pet-grok.desktop"


def resolve_python(project_root: Path) -> Path:
    """Prefer project .venv Python; else current interpreter."""
    root = project_root.resolve()
    if sys.platform == "win32":
        venv_py = root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_py = root / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return venv_py
    return Path(sys.executable).resolve()


def run_script(project_root: Path) -> Path:
    """Absolute path to run.py under the project root."""
    return (project_root.resolve() / "run.py")


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / PLIST_NAME


def _linux_desktop_path() -> Path:
    return Path.home() / ".config" / "autostart" / LINUX_DESKTOP_NAME


def _launch_command(project_root: Path) -> tuple[str, str, str]:
    """Return (python, run.py, working_directory) absolute strings."""
    root = project_root.resolve()
    py = str(resolve_python(root))
    script = str(run_script(root))
    return py, script, str(root)


def _write_macos_plist(project_root: Path) -> None:
    py, script, cwd = _launch_command(project_root)
    path = _plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": PLIST_LABEL,
        "ProgramArguments": [py, script],
        "WorkingDirectory": cwd,
        "EnvironmentVariables": {"PYTHONPATH": cwd},
        "RunAtLoad": True,
    }
    with path.open("wb") as fh:
        plistlib.dump(payload, fh)


def _write_linux_desktop(project_root: Path) -> None:
    py, script, cwd = _launch_command(project_root)
    path = _linux_desktop_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exec uses env so PYTHONPATH is set without a wrapper script.
    exec_line = f'env PYTHONPATH="{cwd}" "{py}" "{script}"'
    body = "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Version=1.0",
            "Name=桌宠grok",
            "Comment=Desk pet powered by xAI API (unofficial)",
            f"Exec={exec_line}",
            f"Path={cwd}",
            "Terminal=false",
            "X-GNOME-Autostart-enabled=true",
            "",
        ]
    )
    path.write_text(body, encoding="utf-8")


def _windows_run_command(project_root: Path) -> str:
    py, script, cwd = _launch_command(project_root)
    # Quote paths for cmd; set PYTHONPATH for the child.
    return f'cmd /c "set PYTHONPATH={cwd}&& "{py}" "{script}""'


def _enable_windows(project_root: Path) -> None:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        # Non-Windows interpreter: no-op (tests may monkeypatch this path).
        return
    cmd = _windows_run_command(project_root)
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    )
    try:
        winreg.SetValueEx(key, WINDOWS_RUN_VALUE, 0, winreg.REG_SZ, cmd)
    finally:
        winreg.CloseKey(key)


def _disable_windows() -> None:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        )
    except OSError:
        return
    try:
        try:
            winreg.DeleteValue(key, WINDOWS_RUN_VALUE)
        except FileNotFoundError:
            pass
    finally:
        winreg.CloseKey(key)


def _windows_is_enabled() -> bool:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        )
    except OSError:
        return False
    try:
        try:
            winreg.QueryValueEx(key, WINDOWS_RUN_VALUE)
            return True
        except FileNotFoundError:
            return False
    finally:
        winreg.CloseKey(key)


def is_enabled() -> bool:
    """Return True if an autostart entry appears present for this platform."""
    if sys.platform == "darwin":
        return _plist_path().is_file()
    if sys.platform == "win32":
        return _windows_is_enabled()
    # Linux and other Unix: XDG autostart desktop file.
    return _linux_desktop_path().is_file()


def enable(project_root: Path) -> None:
    """Install platform autostart so 桌宠grok launches at login."""
    root = project_root.resolve()
    if not run_script(root).is_file():
        raise FileNotFoundError(f"run.py not found under {root}")
    if sys.platform == "darwin":
        _write_macos_plist(root)
        return
    if sys.platform == "win32":
        _enable_windows(root)
        return
    _write_linux_desktop(root)


def disable() -> None:
    """Remove platform autostart entry if present."""
    if sys.platform == "darwin":
        path = _plist_path()
        if path.is_file():
            path.unlink()
        return
    if sys.platform == "win32":
        _disable_windows()
        return
    path = _linux_desktop_path()
    if path.is_file():
        path.unlink()
