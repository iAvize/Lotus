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

## Devbox (Lotus-Lab VM)

Lotus has its own VirtualBox sandbox, the `Lotus-Lab` VM — separate from the
Herdr SOC's `Lotus-Workbench`. It is where Lotus experiments on itself:

- `lotus/devbox.py` — host↔VM bridge: `python -m lotus.devbox status|boot|sync|
  test|run|diff|promote|snapshot|revert`.
- Staging copy lives at `D:\Lotus-Lab\share\staging` (mirrored from the source
  by `devbox.sync()` — `config/`, `memory/`, `.venv/` are never synced). The
  guest pulls it to `C:\lotus-staging` and runs there.
- The agent edits staging via the `staging_*` / `devbox_*` Gemini tools,
  validates with `devbox_test`, then `promote_changes` copies the diff into the
  official source (with `.bak` backups). `config/devbox.json` holds the guest
  login — git-ignored, never commit.
- `experiments` and `lessons` (memories category) in `lotus_ai.db` are the
  learn-from-itself loop: every run/edit/promote is recorded, lessons are
  injected into the prompt via `memory_context`.
- Set `devbox_auto_promote=off` in settings/config to require manual promotion.

## Rules

1. Never commit `config/api_keys.json`, `config/devbox.json`, `.env`, or anything under `memory/`.
2. Windows is the only supported beta platform; do not break the code for other OSes, but do not claim support.
3. Scanner actions must quarantine rather than delete. Do not add silent deletion.
4. Read-only system info checks are allowed after install; OS-level changes still require explicit user permission in the UI flow.
5. Bump `version.json` and `lotus/__init__.py` together for beta changes.
6. After editing Python, run `python scripts/check.py`.
7. Releases are Windows zips built by `python scripts/build_beta_zip.py`.
8. New left-panel features must be registered with `_register_section` so each feature gets its own clickable panel.
