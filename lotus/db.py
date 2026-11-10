"""SQLite storage for Lotus memory, requests, logs, scans, and settings.

Modeled on Jarvis's database approach: one local file, browsable in DB tools,
with soft-delete columns for memories so forgetting does not erase history.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from . import config

_lock = Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    category   TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated    TEXT NOT NULL DEFAULT '',
    deleted    INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (category, key)
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created    TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created     TEXT NOT NULL,
    prompt      TEXT NOT NULL,
    response    TEXT NOT NULL DEFAULT '',
    model       TEXT NOT NULL DEFAULT '',
    used_search INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created    TEXT NOT NULL,
    level      TEXT NOT NULL DEFAULT 'info',
    source     TEXT NOT NULL DEFAULT 'lotus',
    message    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS logs_created ON logs(created DESC);
CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    created      TEXT NOT NULL,
    target       TEXT NOT NULL,
    kind         TEXT NOT NULL,
    files_scanned INTEGER NOT NULL DEFAULT 0,
    threats      INTEGER NOT NULL DEFAULT 0,
    cleaned      INTEGER NOT NULL DEFAULT 0,
    report       TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS experiments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created    TEXT NOT NULL,
    kind       TEXT NOT NULL,
    goal       TEXT NOT NULL DEFAULT '',
    detail     TEXT NOT NULL DEFAULT '{}',
    ok         INTEGER NOT NULL DEFAULT 0,
    duration_s REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS experiments_created ON experiments(created DESC);
"""

_SEED_MEMORIES = (
    ("profile", "name", "Lotus"),
    ("profile", "role", "Cybersecurity AI assistant focused on SOC analysis, AppSec, DevSecOps, defense, and safe automation."),
    ("notes", "mission", "Prioritize cybersecurity tasks while remaining useful for research, writing, coding, testing, and maintenance."),
    ("notes", "beta_scope", "Windows-first beta. App stores, mobile apps, billing, and multi-AI fallback are roadmap items, not beta features."),
    ("profile", "devbox", "Has its own VirtualBox lab VM (Lotus-Lab): edits a staging copy of its source, tests inside the VM, and promotes only after in-guest checks pass."),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    for category, key, value in _SEED_MEMORIES:
        conn.execute(
            "INSERT OR IGNORE INTO memories(category,key,value,updated,deleted,deleted_at) "
            "VALUES(?,?,?, '', 0, '')",
            (category, key, value),
        )
    conn.execute(
        "UPDATE memories SET value=? WHERE category='notes' AND key='beta_scope' "
        "AND value LIKE '%VM sandboxing%'",
        ("Windows-first beta. App stores, mobile apps, billing, and multi-AI fallback "
         "are roadmap items, not beta features.",),
    )
    conn.commit()
    return conn


def log(level: str, source: str, message: str) -> None:
    try:
        with _lock, _conn() as conn:
            conn.execute(
                "INSERT INTO logs(created, level, source, message) VALUES(?,?,?,?)",
                (_now(), level, source, str(message)[:4000]),
            )
            conn.commit()
    except Exception:
        pass


def recent_logs(limit: int = 300) -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT id, created, level, source, message FROM logs ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_logs() -> None:
    with _lock, _conn() as conn:
        conn.execute("DELETE FROM logs")
        conn.commit()
    log("info", "db", "log history cleared by user")


def add_message(role: str, content: str) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO messages(created, role, content) VALUES(?,?,?)",
            (_now(), role, str(content)),
        )
        conn.commit()


def recent_messages(limit: int = 16) -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created FROM messages ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def remember_request(prompt: str, response: str = "", model: str = "", used_search: bool = False) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO requests(created, prompt, response, model, used_search) VALUES(?,?,?,?,?)",
            (_now(), str(prompt), str(response)[:8000], model, 1 if used_search else 0),
        )
        conn.commit()


def recent_requests(limit: int = 200) -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT id, created, prompt, response, model, used_search FROM requests ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def add_memory(category: str, key: str, value: str) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO memories(category,key,value,updated,deleted,deleted_at) VALUES(?,?,?, ?, 0, '') "
            "ON CONFLICT(category,key) DO UPDATE SET value=excluded.value, updated=excluded.updated, deleted=0, deleted_at=''",
            (category, key, str(value), _now()),
        )
        conn.commit()
    log("info", "memory", f"remembered {category}/{key}")


def delete_memory(category: str, key: str) -> bool:
    with _lock, _conn() as conn:
        cur = conn.execute(
            "UPDATE memories SET deleted=1, deleted_at=? WHERE category=? AND key=? AND deleted=0",
            (_now(), category, key),
        )
        conn.commit()
        return cur.rowcount > 0


def list_memories(include_deleted: bool = False, limit: int = 500) -> list[dict]:
    sql = "SELECT category, key, value, updated, deleted FROM memories"
    if not include_deleted:
        sql += " WHERE deleted=0"
    sql += " ORDER BY category, key LIMIT ?"
    with _lock, _conn() as conn:
        rows = conn.execute(sql, (int(limit),)).fetchall()
    return [dict(r) for r in rows]


def memory_context(max_chars: int = 5000) -> str:
    rows = [r for r in list_memories(limit=300)
            if r["category"] in {"profile", "preferences", "user_facts", "notes", "lessons"}]
    lines = []
    total = 0
    for row in rows:
        line = f"- {row['category']}/{row['key']}: {row['value']}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines)


def add_lesson(lesson: str) -> None:
    """Store a lesson learned from a dev session. Lessons surface in every
    future prompt via memory_context — this is how Lotus improves itself."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    add_memory("lessons", f"lesson-{stamp}", str(lesson)[:1000])


def record_experiment(kind: str, goal: str, detail: dict, ok: bool,
                      duration_s: float = 0.0) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO experiments(created, kind, goal, detail, ok, duration_s) "
            "VALUES(?,?,?,?,?,?)",
            (_now(), str(kind), str(goal)[:500],
             json.dumps(detail, ensure_ascii=False)[:30000],
             1 if ok else 0, float(duration_s or 0)),
        )
        conn.commit()


def recent_experiments(limit: int = 100) -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT id, created, kind, goal, ok, duration_s, detail FROM experiments "
            "ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]


def get_setting(key: str, default: str = "") -> str:
    with _lock, _conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return str(row["value"]) if row else default


def set_setting(key: str, value: str) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
        conn.commit()


def record_scan(target: str, kind: str, files_scanned: int, threats: int, cleaned: int, report: dict) -> None:
    with _lock, _conn() as conn:
        conn.execute(
            "INSERT INTO scans(created,target,kind,files_scanned,threats,cleaned,report) VALUES(?,?,?,?,?,?,?)",
            (_now(), str(target), kind, int(files_scanned), int(threats), int(cleaned),
             json.dumps(report, ensure_ascii=False)[:20000]),
        )
        conn.commit()


def recent_scans(limit: int = 100) -> list[dict]:
    with _lock, _conn() as conn:
        rows = conn.execute(
            "SELECT id, created, target, kind, files_scanned, threats, cleaned FROM scans ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return [dict(r) for r in rows]
