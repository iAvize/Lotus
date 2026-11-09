# Lotus agent guide

Lotus is a standalone Windows-first cybersecurity AI beta. Keep it separate from Jarvis and the Herdr SOC unless the user explicitly asks to bridge them.

## Layout

- `lotus/app.py` — QApplication entry point.
- `lotus/ui/` — PyQt6 interface, Matrix rain, reactor, setup/settings dialogs.
- `lotus/ai.py` — Gemini chat, memory commands, web-search intent.
- `lotus/db.py` — SQLite memories, messages, requests, logs, scans, settings.
- `lotus/scanner.py` — file triage/quarantine and code-pattern scanning.
- `lotus/github.py` — GitHub repo snapshot scanning.
- `lotus/updater.py` — GitHub release checks and Windows self-update staging.
- `scripts/` — setup, launch, compile check, beta zip builder.

## Rules

1. Never commit `config/api_keys.json`, `.env`, or anything under `memory/`.
2. Windows is the only supported beta platform; do not break the code for other OSes, but do not claim support.
3. Scanner actions must quarantine rather than delete. Do not add silent deletion.
4. Read-only system info checks are allowed after install; OS-level changes still require explicit user permission in the UI flow.
5. Bump `version.json` and `lotus/__init__.py` together for beta changes.
6. After editing Python, run `python scripts/check.py`.
7. Releases are Windows zips built by `python scripts/build_beta_zip.py`.
