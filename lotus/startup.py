"""Run-on-startup toggle for Lotus (Windows).

Writes a per-user HKCU\\...\\Run entry — no admin needed, no scheduled task.
Frozen builds point straight at the exe; source runs go through the hidden
PowerShell launcher so no console window appears at login.
"""
from __future__ import annotations

import sys

from . import config

VALUE_NAME = "LotusBeta"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    ps1 = config.BASE_DIR / "scripts" / "Run-Lotus.ps1"
    if ps1.exists():
        return ('powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass '
                f'-File "{ps1}"')
    return f'"{config.BASE_DIR / "Run-Lotus.bat"}"'


def is_enabled() -> bool:
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
