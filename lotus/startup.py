"""Run-on-startup toggle for Lotus.

Windows: a per-user HKCU\\...\\Run entry — no admin needed, no scheduled
task. Frozen builds point straight at the exe; source runs go through the
hidden PowerShell launcher so no console window appears at login.

macOS: a per-user LaunchAgent at ~/Library/LaunchAgents/com.avize.Lotus.plist
— runs `python -m lotus` from the source tree (or the bundled app binary)
at login, no admin needed.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import config

VALUE_NAME = "LotusBeta"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_LAUNCHAGENT_LABEL = "com.avize.Lotus"


def checkbox_label() -> str:
    if sys.platform == "win32":
        return "Run Lotus automatically when Windows starts"
    if sys.platform == "darwin":
        return "Run Lotus automatically when you log in"
    return "Run Lotus automatically at login"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    ps1 = config.BASE_DIR / "scripts" / "Run-Lotus.ps1"
    if ps1.exists():
        return ('powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass '
                f'-File "{ps1}"')
    return f'"{config.BASE_DIR / "Run-Lotus.bat"}"'


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{_LAUNCHAGENT_LABEL}.plist"


def _write_plist(path: Path) -> None:
    import plistlib
    if getattr(sys, "frozen", False):
        args = [str(Path(sys.executable).resolve())]
    else:
        args = [str(Path(sys.executable).resolve()), "-m", "lotus"]
    plist = {
        "Label": _LAUNCHAGENT_LABEL,
        "ProgramArguments": args,
        "WorkingDirectory": str(config.BASE_DIR),
        "RunAtLoad": True,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(plist))


def _mac_set_enabled(enabled: bool) -> bool:
    plist = _plist_path()
    uid = os.getuid()
    if enabled:
        try:
            _write_plist(plist)
        except OSError:
            return False
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(plist)],
            capture_output=True, timeout=15,
        )
        return plist.exists()
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}/{_LAUNCHAGENT_LABEL}"],
        capture_output=True, timeout=15,
    )
    try:
        plist.unlink(missing_ok=True)
    except OSError:
        pass
    return not plist.exists()


def is_enabled() -> bool:
    if sys.platform == "darwin":
        return _plist_path().exists()
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Install or remove the startup entry. Returns the new state."""
    if sys.platform == "darwin":
        return _mac_set_enabled(enabled)
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
