# Lotus — Cybersecurity AI (Windows Beta)

Lotus is a Windows-first cybersecurity assistant built for SOC analysis, AppSec, DevSecOps, secure coding, malware awareness, and general research/help. It is currently in **public beta**.
## Beta features

- Purple reactor + Matrix-rain desktop UI
- Gemini-powered chat with local conversation memory
- SQLite memory/request/activity logs (browsable in DB tools)
- `remember:` / `forget` memory commands
- Read-only OS info checks only after you approve the specific question
- Folder virus scan with quarantine instead of deletion
- GitHub repository code scan for risky patterns
- GitHub release update check and Windows self-update staging
- Local-only secrets in `config/api_keys.json` (never committed)

## Install on Windows

1. Download `Lotus-Beta-<version>-Windows.zip` from GitHub Releases.
2. Extract it.
3. Run `scripts\setup_windows.bat` once. It creates `.venv` and installs dependencies.
4. Run `Run-Lotus.bat`.
5. On first launch, paste your Gemini API key or choose **Import from Jarvis**.

Python 3.11–3.14 is preferred. The setup script chooses the newest supported `py` launcher version it finds.

## Scanner safety

Lotus beta does **not** delete files. Suspicious files are moved to:

```text
memory\quarantine\
```

The scanner is a first-pass static guard, not a replacement for Windows Defender or a full antivirus. It flags double-extension lures, dangerous script patterns, suspicious archives, unsigned executables, and common insecure code patterns.

## GitHub scans

The scanner can read a public GitHub repo as `github.com/owner/repo` or `owner/repo`. Add a GitHub token in **Settings** only if you need private repositories. Beta scans are read-only; automatic pull requests and vulnerability rewrites are roadmap items.

## Updates

Lotus checks GitHub Releases on launch. When a newer Windows beta zip is published, an **Update** button appears in the top-right. The updater downloads the release asset, stages it, and restarts Lotus.

## Developer / source access

The public repository contains the full source. `Lotus-Source-<version>.zip` is also attached to releases for developers who want a clean snapshot. Beta users do not get developer-only controls.

## Roadmap / intentionally skipped for beta

- iOS, Android, Mac, Linux, and app-store builds
- Paid personal/enterprise tiers, quotas, and billing
- Multi-AI fallback providers (retracted for now; Lotus uses Gemini directly)
- VirtualBox/VM sandbox for untrusted code execution
- Automatic GitHub pull requests or vulnerability rewrites
- Voice interface, plugins, remote dashboard, enterprise SSO/audit exports

See `docs/ROADMAP.md` for the full backlog and reasons.

## License

All rights reserved. The public beta is free for personal and nonprofit testing. Commercial use requires a separate license.
