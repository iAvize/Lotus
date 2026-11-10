"""Crash logging + report helpers for Lotus.

Installs a global excepthook so unhandled errors land in
``memory/lotus-error.log`` (plus a hard-crash faulthandler dump), and builds a
compact report the user can copy to share.
"""
from __future__ import annotations

import faulthandler
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import config

LOG_NAME = "lotus-error.log"
_LOG_PATH: Path | None = None


def log_path() -> Path:
    global _LOG_PATH
    if _LOG_PATH is None:
        mem = Path(config.BASE_DIR) / "memory"
        mem.mkdir(parents=True, exist_ok=True)
        _LOG_PATH = mem / LOG_NAME
    return _LOG_PATH


def _write(text: str) -> None:
    try:
        with log_path().open("a", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
    except Exception:
        pass


def _excepthook(exc_type, exc, tb):
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _write(f"\n=== {stamp} ===\n{''.join(traceback.format_exception(exc_type, exc, tb))}")
    sys.__excepthook__(exc_type, exc, tb)


def install() -> None:
    """Hook uncaught exceptions + native faults into the error log."""
    try:
        fh = log_path().open("a", encoding="utf-8")
        fh.write(f"\n--- session {datetime.now(timezone.utc).isoformat(timespec='seconds')} ---\n")
        faulthandler.enable(fh)
    except Exception:
        faulthandler.enable()
    sys.excepthook = _excepthook


def tail_bytes(limit: int = 200_000) -> bytes:
    try:
        return log_path().read_bytes()[-limit:]
    except Exception:
        return b""


def build_report() -> str:
    """Compact text report for bug reports: version, system, log tail."""
    try:
        from . import __version__
    except Exception:
        __version__ = "unknown"
    tail = tail_bytes(20_000).decode("utf-8", errors="replace") or "(no errors logged)"
    return (
        f"Lotus {__version__}\n"
        f"Python {platform.python_version()} | {platform.system()} {platform.release()}\n"
        f"---- lotus-error.log (tail) ----\n{tail}"
    )
