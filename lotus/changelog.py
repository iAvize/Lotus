"""Structured patch notes for Lotus releases.

One entry per release, newest first. `unseen()` drives the post-update
popup; the Patch Notes section renders the full history with local dates.
"""
from __future__ import annotations

from . import db

RELEASES = [
    {"version": "0.1.0-beta.39", "date": "2026-11-11",
     "notes": ["Orb menu mode: dead-center hover-scrub orbs, click focused orb to open its panel"]},
    {"version": "0.1.0-beta.38", "date": "2026-11-11",
     "notes": ["Orb carousel centered lower like reference, cleaner label spacing"]},
    {"version": "0.1.0-beta.37", "date": "2026-11-11",
     "notes": ["Hover-scrub orb carousel, dead-center, labels under every orb, panels removed"]},
    {"version": "0.1.0-beta.36", "date": "2026-11-11",
     "notes": ["Orb carousel centered full-width; reactor panel removed"]},
    {"version": "0.1.0-beta.35", "date": "2026-11-11",
     "notes": ["Orb carousel: drag-scrub with mouse, star-dot centers, reactor removed for space"]},
    {"version": "0.1.0-beta.34", "date": "2026-11-11",
     "notes": ["Orb carousel fixed - full-width strip across the top of the content area"]},
    {"version": "0.1.0-beta.33", "date": "2026-11-11",
     "notes": ["Orb-style scrollable nav replaces left panel (test - easily reverted)"]},
    {"version": "0.1.0-beta.32", "date": "2026-11-11",
     "notes": ["Animated Lotus logo splash on launch", "Console-window flash on startup removed"]},
    {"version": "0.1.0-beta.31", "date": "2026-11-10",
     "notes": ["Update check now trusts the binary's baked version over the sidecar version.json"]},
    {"version": "0.1.0-beta.30", "date": "2026-11-10",
     "notes": ["Update popup auto-shows on launch again; Check for updates stays as backup"]},
    {"version": "0.1.0-beta.29", "date": "2026-11-10",
     "notes": ["Update button is now manual 'Check for updates' with latest-version / update-available popups"]},
    {"version": "0.1.0-beta.28", "date": "2026-11-10",
     "notes": ["Feedback button now ships with the developer contact address"]},
    {"version": "0.1.0-beta.27", "date": "2026-11-10",
     "notes": ["Patch notes panel + post-update popup",
               "Settings: feedback button (emails the developer)",
               "Mobile app prepared for TestFlight"]},
    {"version": "0.1.0-beta.26", "date": "2026-11-10",
     "notes": ["Usage metering - tokens + Lotus-Lab VM minutes",
               "Logs 'View' dropdown: Activity / My usage / Global minutes (dev builds)"]},
    {"version": "0.1.0-beta.25", "date": "2026-11-09",
     "notes": ["Auto-scan dropdown moved under the scan target selector"]},
    {"version": "0.1.0-beta.24", "date": "2026-11-09",
     "notes": ["Adaptive personality system + Personality section",
               "Scheduled file scanning (30m/1h/2h)"]},
    {"version": "0.1.0-beta.23", "date": "2026-11-09",
     "notes": ["Crash logging + 'Copy error report' button",
               "Streaming chat replies", "Test suite + backend seam"]},
    {"version": "0.1.0-beta.22", "date": "2026-11-09",
     "notes": ["Beta.zip is now runtime-only (exe + docs);",
               "source moved to the trusted-developers package"]},
    {"version": "0.1.0-beta.21", "date": "2026-11-09",
     "notes": ["Reverted fullscreen to instant toggle"]},
    {"version": "0.1.0-beta.20", "date": "2026-11-09",
     "notes": ["Fullscreen snapshot transition"]},
    {"version": "0.1.0-beta.19", "date": "2026-11-09",
     "notes": ["Fullscreen crossfade (replaced in beta.20/21)"]},
    {"version": "0.1.0-beta.18", "date": "2026-11-09",
     "notes": ["Smooth fullscreen transition animation"]},
    {"version": "0.1.0-beta.17", "date": "2026-11-09",
     "notes": ["Version label bottom-right of window",
               "Devbox VM + themes + multiline chat shipped to GitHub"]},
    {"version": "0.1.0-beta.16", "date": "2026-11-09",
     "notes": ["Version label added top-right"]},
    {"version": "0.1.0-beta.15", "date": "2026-11-09",
     "notes": ["Auto-growing multi-line chat box",
               "5 instant UI themes (purple/blue/red/pink/green)",
               "Run-on-startup toggle", "Fullscreen button",
               "Updater rework - hidden until needed, restart/relaunch choice, progress bar"]},
    {"version": "0.1.0-beta.14", "date": "2026-11-09",
     "notes": ["Dedicated 'Lotus-Lab' VirtualBox devbox + Devbox panel",
               "Autonomous staging/test/promote loop with lessons memory"]},
    {"version": "0.1.0-beta.13", "date": "2026-11-09",
     "notes": ["Widened clickable section panels toward the center",
               "Kept reactor/Matrix visual on the right"]},
]


def for_version(version: str) -> dict | None:
    v = version.lstrip("v")
    for r in RELEASES:
        if r["version"].lstrip("v") == v:
            return r
    return None


def unseen() -> dict | None:
    """Return the current release's notes if the user hasn't seen them yet."""
    from . import __version__
    seen = db.get_setting("last_seen_version", "")
    cur = __version__.lstrip("v")
    if seen == cur:
        return None
    return for_version(cur)


def mark_seen() -> None:
    from . import __version__
    db.set_setting("last_seen_version", __version__.lstrip("v"))
