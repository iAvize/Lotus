"""Adaptive personality profile for Lotus.

Lotus keeps a slowly-evolving profile of how the user likes to be talked to
(tone, verbosity, humor, proactivity, technical depth) plus free-text notes.
The profile is injected into chat prompts as natural-language voice guidance.

Hard rules:
- Personality applies to CONVERSATION ONLY. Scan results, threat alerts,
  quarantine reports, and update dialogs always use fixed professional
  templates — a security assistant never jokes about malware.
- Drift is bounded: any trait can move at most MAX_DELTA per synthesis and
  always stays inside [0, 1]. Personality drifts; it never lurches.
- Explicit user statements always win over the profile.
- Everything lives in the local SQLite DB — the profile never leaves the
  machine.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import db

TRAITS = ("formality", "verbosity", "humor", "proactivity", "technical_depth")
DEFAULTS = {t: 0.5 for t in TRAITS}
DEFAULTS["humor"] = 0.3

MAX_DELTA = 0.1          # max change per synthesis pass
SYNTH_EVERY = 15         # synthesize after N assistant replies
HISTORY_KEEP = 50

# Optional starting points users may pick — never forced.
ARCHETYPES = {
    "analyst":  {"formality": 0.7, "verbosity": 0.6, "humor": 0.2, "proactivity": 0.4, "technical_depth": 0.9},
    "friendly": {"formality": 0.2, "verbosity": 0.5, "humor": 0.7, "proactivity": 0.7, "technical_depth": 0.5},
    "strict-pro": {"formality": 0.9, "verbosity": 0.4, "humor": 0.1, "proactivity": 0.3, "technical_depth": 0.8},
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS personality (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    traits TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    msgs_since INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS personality_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    deltas TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure() -> None:
    with db._conn() as conn:
        conn.executescript(_SCHEMA)


def get() -> dict:
    _ensure()
    with db._conn() as conn:
        row = conn.execute(
            "SELECT traits, notes, msgs_since, updated_at FROM personality WHERE id=1"
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO personality(id, traits, notes, msgs_since, updated_at)"
                " VALUES(1, ?, '', 0, ?)",
                (json.dumps(DEFAULTS), _now()),
            )
            row = conn.execute(
                "SELECT traits, notes, msgs_since, updated_at FROM personality WHERE id=1"
            ).fetchone()
    return {
        "traits": {**DEFAULTS, **(json.loads(row[0]) if row[0] else {})},
        "notes": row[1] or "",
        "msgs_since": int(row[2] or 0),
        "updated_at": row[3] or "",
    }


def _save(traits: dict, notes: str, msgs_since: int) -> None:
    _ensure()
    with db._conn() as conn:
        conn.execute(
            "UPDATE personality SET traits=?, notes=?, msgs_since=?, updated_at=? WHERE id=1",
            (json.dumps(traits), notes, msgs_since, _now()),
        )


def prompt_block() -> str:
    """Natural-language voice guidance for the system prompt."""
    p = get()
    t = p["traits"]

    def hi(v): return v >= 0.65
    def lo(v): return v <= 0.35

    voice = []
    voice.append("formal tone" if hi(t["formality"]) else "casual tone" if lo(t["formality"]) else "neutral-professional tone")
    voice.append("detailed answers" if hi(t["verbosity"]) else "concise answers" if lo(t["verbosity"]) else "moderately concise answers")
    if hi(t["humor"]):
        voice.append("light dry humor welcome")
    elif lo(t["humor"]):
        voice.append("keep humor out")
    if hi(t["proactivity"]):
        voice.append("suggest useful next steps unprompted")
    elif lo(t["proactivity"]):
        voice.append("answer what's asked, don't push suggestions")
    voice.append("expert-level technical depth" if hi(t["technical_depth"]) else "plain-language explanations" if lo(t["technical_depth"]) else "moderate technical depth")
    block = "Voice calibration for this user: " + "; ".join(voice) + "."
    if p["notes"].strip():
        block += f"\nUser style notes: {p['notes'].strip()[:400]}"
    block += ("\nApply this voice to conversation only — scan results, threat alerts, "
              "and security reports always stay literal and professional.")
    return block


def note_message() -> bool:
    """Count an assistant reply; return True when a synthesis is due."""
    p = get()
    n = p["msgs_since"] + 1
    _save(p["traits"], p["notes"], n)
    return n >= SYNTH_EVERY


def apply_deltas(deltas: dict, reason: str = "", notes_update: str | None = None) -> None:
    """Apply bounded trait changes + record them in history."""
    p = get()
    traits = dict(p["traits"])
    applied = {}
    for name, delta in (deltas or {}).items():
        if name not in TRAITS:
            continue
        try:
            d = max(-MAX_DELTA, min(MAX_DELTA, float(delta)))
        except (TypeError, ValueError):
            continue
        if d:
            traits[name] = round(max(0.0, min(1.0, traits[name] + d)), 3)
            applied[name] = d
    notes = p["notes"]
    if notes_update:
        notes = notes_update.strip()[:800]
    _save(traits, notes, 0)  # reset the counter
    _ensure()
    with db._conn() as conn:
        conn.execute(
            "INSERT INTO personality_history(created, deltas, reason) VALUES(?,?,?)",
            (_now(), json.dumps(applied), (reason or "")[:200]),
        )
        conn.execute(
            "DELETE FROM personality_history WHERE id NOT IN"
            " (SELECT id FROM personality_history ORDER BY id DESC LIMIT ?)",
            (HISTORY_KEEP,),
        )


def synthesize() -> bool:
    """Ask Gemini for profile deltas from recent chat, apply them.

    Best-effort: any failure is logged and leaves the profile untouched —
    personality must never break the chat path.
    """
    try:
        from . import ai, config

        if not config.get_gemini_key():
            return False
        rows = db.recent_messages(10)
        if not rows:
            return False
        transcript = "\n".join(
            f"{'User' if r['role'] == 'user' else 'Lotus'}: {r['content'][:200]}"
            for r in rows
        )
        current = get()
        prompt = (
            "You are refining an assistant's per-user voice profile. Current traits"
            f" (0.0-1.0): {json.dumps(current['traits'])}. Notes: {current['notes'] or 'none'}.\n"
            "Recent conversation:\n" + transcript +
            "\n\nReturn ONLY compact JSON like"
            ' {"deltas":{"verbosity":0.05},"reason":"one line","notes_update":"updated notes or null"}.'
            " Deltas: small adjustments to traits based on how the user communicates;"
            " use 0 when nothing is learned. notes_update: refined free-text notes or null."
        )
        client = ai._client(config.get_gemini_key(), 30_000)
        resp = ai._backend_call(client, ai.MODEL_LADDER[0], prompt,
                                {"temperature": 0.2, "max_output_tokens": 400})
        text = ai._response_text(resp).strip()
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return False
        data = json.loads(text[start:end + 1])
        apply_deltas(data.get("deltas") or {}, data.get("reason") or "",
                     data.get("notes_update"))
        db.log("info", "personality", f"synthesized: {data.get('deltas')}")
        return True
    except Exception as exc:  # noqa: BLE001 - personality must never break chat
        db.log("warning", "personality", f"synthesis skipped: {exc}")
        return False


def analyze_style(user_text: str) -> bool:
    """Manual path: user describes how they want to be treated → into notes."""
    text = (user_text or "").strip()
    if not text:
        return False
    p = get()
    merged = (p["notes"] + " | " + text).strip(" |") if p["notes"] else text
    _save(p["traits"], merged[:800], p["msgs_since"])
    db.log("info", "personality", "user style note added")
    return True


def set_trait(name: str, value: float) -> None:
    if name not in TRAITS:
        return
    p = get()
    traits = dict(p["traits"])
    traits[name] = round(max(0.0, min(1.0, float(value))), 3)
    _save(traits, p["notes"], p["msgs_since"])


def apply_archetype(name: str) -> bool:
    """Optional preset — applies its trait values; user still owns the dials."""
    base = ARCHETYPES.get(name)
    if not base:
        return False
    p = get()
    _save({**DEFAULTS, **base}, p["notes"], p["msgs_since"])
    db.log("info", "personality", f"archetype applied: {name}")
    return True


def reset() -> None:
    p = get()
    _save(dict(DEFAULTS), "", 0)
    db.log("info", "personality", "reset to neutral defaults")


def history(limit: int = 20) -> list[dict]:
    _ensure()
    with db._conn() as conn:
        rows = conn.execute(
            "SELECT created, deltas, reason FROM personality_history"
            " ORDER BY id DESC LIMIT ?", (int(limit),),
        ).fetchall()
    return [{"created": r[0], "deltas": json.loads(r[1] or "{}"), "reason": r[2]}
            for r in rows]
