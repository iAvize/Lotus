"""Report + feedback delivery for Lotus.

Reports are quick crash/error submissions — posted silently to the
developer inbox (FormSubmit relay, no SMTP creds in the repo) so users
just paste and tap Send. Feedback is for detailed write-ups and opens
the user's mail app pre-filled (screenshots/videos attach there).
"""
from __future__ import annotations

import json
import platform
import urllib.request
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


def _report_body(error_text: str = "") -> str:
    body = crashlog.build_report()
    if error_text.strip():
        body += f"\n\n---- pasted error/code ----\n{error_text.strip()}\n"
    return body


def report_mailto(error_text: str = "") -> str:
    """One-tap crash/error report — diagnostics fill the email for the user."""
    return _mailto(f"Lotus Beta crash report (v{__version__})",
                   _report_body(error_text))


def send_report(error_text: str = "", timeout: int = 15) -> bool:
    """POST the crash report silently to the developer inbox.

    Uses the FormSubmit relay — no mail app, no SMTP creds. Returns True
    when the report was accepted; callers fall back to mailto on False.
    """
    try:
        req = urllib.request.Request(
            f"https://formsubmit.co/ajax/{feedback_email()}",
            data=json.dumps({
                "_subject": f"Lotus Beta crash report (v{__version__})",
                "_captcha": "false",
                "message": _report_body(error_text),
            }).encode(),
            headers={"Content-Type": "application/json",
                     "Accept": "application/json",
                     "Origin": "https://github.com",
                     "Referer": "https://github.com/iAvize/Lotus"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read() or b"{}")
            return str(data.get("success")).lower() == "true"
    except Exception:
        return False


def feedback_mailto(message: str = "") -> str:
    body = (
        f"Version: {__version__}\nInstall: {_install_id()}\n"
        f"Platform: {platform.system()} {platform.release()}\n\n"
        f"{message.strip() or 'What happened?'}\n\n"
        "Screenshots/videos: optional — attach them in your mail app before sending.\n"
    )
    return _mailto(f"Lotus Beta feedback (v{__version__})", body)
