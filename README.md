# Lotus — Cybersecurity AI (Windows + macOS Beta)

Lotus is a Windows-first cybersecurity assistant built for SOC analysis, AppSec, DevSecOps, secure coding, malware awareness, and general research/help. It is currently in **public beta** and also runs from source on macOS.
## Beta features

- Purple reactor + Matrix-rain desktop UI
- Gemini-powered chat with local conversation memory
- SQLite memory/request/activity logs (browsable in DB tools)
- `remember:` / `forget` memory commands
- Read-only OS info checks
- Folder virus scan with quarantine instead of deletion
- Scan target dropdown for Downloads and detected local/external drives
- GitHub repository code scan for risky patterns
- GitHub release update check and self-update staging (Windows + macOS)

## Install on Windows

1. Download `Lotus.Beta.exe` from GitHub Releases.
2. Run `Lotus.Beta.exe`.
3. First run creates a `Lotus Beta` desktop shortcut with the app icon.
4. On first launch, Lotus prompts for your own Gemini API key and links to Google AI Studio where you can create one.

`Lotus.Beta.zip` is the scriptable beta package for users who prefer running from source/scripts. After extracting `Lotus Beta`, run `Lotus Beta.bat` only if you are not using the exe.

`Lotus.Source.Trusted.Developers.zip` is trusted developer access only and is password-protected. It includes the source code and the Windows app.

Python 3.11–3.14 is preferred when running from source.

## Install on macOS

1. Download `Lotus.Beta.Mac.dmg` from GitHub Releases.
2. Open the dmg and drag `Lotus Beta.app` onto the Applications folder.
3. First launch only: macOS may block the app since it is not notarized — right-click `Lotus Beta` → **Open** → **Open** (or System Settings → Privacy & Security → **Open Anyway**).
4. On first launch, Lotus prompts for your own Gemini API key and links to Google AI Studio where you can create one.

`Lotus.Beta.Mac.zip` holds the same `Lotus Beta.app` as a plain zip for scriptable installs and in-app updates.

Prefer source? Clone the repo, run `bash scripts/setup_macos.sh`, then double-click `scripts/Run-Lotus.command` or run `.venv/bin/python -m lotus`.

On macOS the updater swaps the `.app` via a staged POSIX shell script, "run at login" uses a per-user LaunchAgent, and the Lotus-Lab devbox falls back to a **local lab mode** (staging commands run directly on the Mac) when no `Lotus-Lab` VirtualBox VM is registered.

## Scanner safety

Lotus beta does **not** delete files. Suspicious files are moved to:

```text
memory/quarantine/
```

The scanner is a first-pass static guard, not a replacement for a real antivirus. It flags double-extension lures, dangerous script patterns, suspicious archives, unsigned executables (Authenticode on Windows, codesign on macOS), and common insecure code patterns.

## GitHub scans

The scanner can read a public GitHub repo as `github.com/owner/repo` or `owner/repo`. Add a GitHub token in **Settings** only if you need private repositories. Beta scans are read-only; automatic pull requests and vulnerability rewrites are roadmap items.

## Updates

Lotus checks GitHub Releases on launch. When a newer Windows beta zip is published, an **Update** button appears in the top-right. The updater downloads the release asset, stages it, and restarts Lotus.


## Here is the roadmap for future updates

- iOS, Android, Linux, and app-store builds
- Paid personal/enterprise tiers, quotas, and billing
- Multi-AI fallback providers
- VirtualBox/VM sandbox for untrusted code execution
- Automatic GitHub pull requests or vulnerability rewrites
- Voice interface, plugins, remote dashboard, enterprise SSO/audit exports

See `docs/ROADMAP.md` for the full backlog and reasons.

## License

All rights reserved. The public beta is free for personal and nonprofit testing. Commercial use requires a separate license.
