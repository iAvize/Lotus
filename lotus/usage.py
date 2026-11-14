"""Usage metering — Gemini tokens + Lotus-Lab VM minutes.

Beta goal: measure real consumption to inform launch pricing. Nothing ever
blocks or runs out — this is a display gauge only. Rows are immutable events;
"this month" and "all time" are read windows, so usage resets naturally each
month while lifetime totals stay visible.

Dev builds (running from source, not frozen) additionally get a "global"
rollup that aggregates every Lotus install DB reachable on this machine —
the future seam for real per-download telemetry through LotusCloud.
"""
from __future__ import annotations

import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config, db

_KINDS = ("tokens", "vm_minutes")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    kind    TEXT NOT NULL,
    amount  REAL NOT NULL,
    detail  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS usage_events_created ON usage_events(created);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure() -> None:
    with db._conn() as conn:
        conn.executescript(_SCHEMA)


def install_id() -> str:
    """Persistent per-install id — set once, preserved across updates."""
    iid = db.get_setting("install_id", "")
    if not iid:
        iid = uuid.uuid4().hex[:12]
        db.set_setting("install_id", iid)
    return iid


def is_dev_build() -> bool:
    """Running from source = developer build → sees global usage."""
    return not getattr(sys, "frozen", False)


def record(kind: str, amount: float, detail: str = "") -> None:
    if amount <= 0:
        return
    try:
        _ensure()
        with db._conn() as conn:
            conn.execute(
                "INSERT INTO usage_events(created, kind, amount, detail) VALUES(?,?,?,?)",
                (_now(), kind, float(amount), (detail or "")[:200]),
            )
    except Exception:
        pass  # metering must never break the app


def record_tokens(n: int, model: str = "") -> None:
    record("tokens", float(n), model)


def record_vm_seconds(secs: float, detail: str = "lotus-lab") -> None:
    record("vm_minutes", secs / 60.0, detail)


def vm_boot() -> None:
    db.set_setting("vm_boot_at", _now())


def vm_shutdown() -> None:
    ts = db.get_setting("vm_boot_at", "")
    if not ts:
        return
    db.set_setting("vm_boot_at", "")
    try:
        start = datetime.fromisoformat(ts)
        secs = (datetime.now(timezone.utc) - start).total_seconds()
        if secs > 5:
            record_vm_seconds(secs)
    except Exception:
        pass


def _totals(where: str = "", params: tuple = ()) -> dict:
    _ensure()
    with db._conn() as conn:
        rows = conn.execute(
            f"SELECT kind, SUM(amount) FROM usage_events {where} GROUP BY kind",
            params,
        ).fetchall()
    out = {k: 0.0 for k in _KINDS}
    for k, v in rows:
        if k in out:
            out[k] = round(float(v or 0), 2)
    return out


def summary() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "install_id": install_id(),
        "today": _totals("WHERE created >= ?", (now.strftime("%Y-%m-%d"),)),
        "month": _totals("WHERE created >= ?", (now.strftime("%Y-%m-01"),)),
        "all_time": _totals(),
    }


def reset() -> None:
    _ensure()
    with db._conn() as conn:
        conn.execute("DELETE FROM usage_events")


def _candidate_dbs() -> list[Path]:
    """Every reachable Lotus install DB on this machine."""
    home = Path.home()
    cands = [
        config.memory_dir() / "lotus_ai.db",
        Path(config.BASE_DIR) / "memory" / "lotus.db",
        home / "Library" / "Application Support" / "Lotus" / "memory" / "lotus_ai.db",
        home / "Lotus Beta" / "memory" / "lotus.db",
        home / "Downloads" / "Lotus Beta" / "memory" / "lotus.db",
        home / "Downloads" / "Lotus Source" / "memory" / "lotus.db",
        home / "Lotus Source" / "memory" / "lotus.db",
    ]
    seen, out = set(), []
    for p in cands:
        key = str(p).lower()
        if p.exists() and key not in seen:
            seen.add(key)
            out.append(p)
    return out


def global_rollup() -> list[dict]:
    """Per-install usage across all reachable copies (dev builds only)."""
    results = []
    for dbp in _candidate_dbs():
        try:
            conn = sqlite3.connect(f"file:{dbp.as_posix()}?mode=ro", uri=True)
            try:
                iid = "—"
                try:
                    row = conn.execute(
                        "SELECT value FROM settings WHERE key='install_id'"
                    ).fetchone()
                    if row:
                        iid = row[0]
                except Exception:
                    pass
                rows = conn.execute(
                    "SELECT kind, SUM(amount) FROM usage_events GROUP BY kind"
                ).fetchall()
            finally:
                conn.close()
            tot = {k: 0.0 for k in _KINDS}
            for k, v in rows:
                if k in tot:
                    tot[k] = round(float(v or 0), 2)
            results.append({"install": dbp.parent.parent.name,
                            "path": str(dbp.parent.parent),
                            "id": iid, **tot})
        except Exception:
            continue
    return results


def report_payload() -> dict:
    """Anonymized usage summary — the future telemetry seam for LotusCloud."""
    s = summary()
    return {"install_id": s["install_id"], "build": "dev" if is_dev_build() else "beta",
            "month": s["month"], "all_time": s["all_time"]}
