"""Report + feedback mailto helpers for Lotus.

Reports are quick crash/error submissions — the email body carries the
diagnostics (version, install, system, error-log tail) so users never
have to describe anything. Feedback is for detailed write-ups; media
is attached by the user in their mail app (mailto can't attach files).

There is no SMTP backend — both flows open the user's own mail client
pre-filled and addressed; they only press Send.
"""
from __future__ import annotations

import platform
from urllib.parse import quote

from . import __version__, crashlog, db

DEFAULT_FEEDBACK_EMAIL = "bizwithavize@outlook.com"


def feedback_email() -> str:
    try:
        from .feedback_email import FEEDBACK_EMAIL as _baked
    except Exception:
        _baked = DEFAULT_FEEDBACK_EMAIL
    return db.get_setting("feedback_email", "") or _baked


def _mailto(subject: str, body: str) -> str:
    return f"mailto:{feedback_email()}?subject={quote(subject)}&body={quote(body)}"


def _install_id() -> str:
    try:
        from . import usage
        return usage.install_id()
    except Exception:
        return "unknown"


def report_mailto(error_text: str = "") -> str:
    """One-tap crash/error report — diagnostics fill the email for the user."""
    body = crashlog.build_report()
    if error_text.strip():
        body += f"\n\n---- pasted error/code ----\n{error_text.strip()}\n"
    return _mailto(f"Lotus Beta crash report (v{__version__})", body)


def feedback_mailto(message: str = "") -> str:
    body = (
        f"Version: {__version__}\nInstall: {_install_id()}\n"
        f"Platform: {platform.system()} {platform.release()}\n\n"
        f"{message.strip() or 'What happened?'}\n\n"
        "Screenshots/videos: optional — attach them in your mail app before sending.\n"
    )
    return _mailto(f"Lotus Beta feedback (v{__version__})", body)
