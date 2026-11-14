"""Build beta and source zip artifacts for Lotus.

Run from the repo root:  python scripts/build_beta_zip.py [--mac]

Windows builds `Lotus Beta.zip` (compiled app only, no source code) plus
`Lotus Source.zip`. On macOS, `Lotus Beta Mac.zip` packages the PyInstaller
`Lotus Beta.app` bundle — build it first with scripts/lotus_beta_mac.spec.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from tempfile import TemporaryDirectory
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

EXCLUDE_DIRS = {
    ".git", "memory", "config", "dist", ".venv", "venv", "env", "node_modules",
    "__pycache__", "_lotus_update_staging", ".idea", ".vscode",
}
EXCLUDE_FILES = {"api_keys.json", "devbox.json", ".env"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}

LAUNCHER_BAT = (
    "@echo off\r\n"
    "powershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0scripts\\Run-Lotus.ps1\"\r\n"
    "exit /b %ERRORLEVEL%\r\n"
)

LAUNCHER_COMMAND = """#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  bash scripts/setup_macos.sh || exit 1
fi
exec .venv/bin/python -m lotus
"""


def version() -> str:
    data = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    return str(data["version"])


def excluded(path: Path) -> bool:
    name = path.name
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    if name in EXCLUDE_FILES or name.startswith(".env"):
        return True
    return path.suffix.lower() in EXCLUDE_SUFFIXES


def build_app() -> Path:
    """Public beta package: compiled app + docs only. No source code."""
    DIST.mkdir(exist_ok=True)
    out = DIST / "Lotus Beta.zip"
    exe = ROOT.parent / "Lotus Beta" / "Lotus Beta.exe"
    if not exe.is_file():
        exe = DIST / "Lotus Beta.exe"
    if not exe.is_file():
        raise SystemExit("Lotus Beta.exe not found — build the PyInstaller exe first")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe, "Lotus Beta/Lotus Beta.exe")
        for name in ("version.json", "README.md", "LICENSE"):
            src = ROOT / name
            if src.is_file():
                zf.write(src, f"Lotus Beta/{name}")
    print(f"built {out.relative_to(ROOT)}")
    return out


def build_source() -> Path:
    DIST.mkdir(exist_ok=True)
    out = DIST / "Lotus Source.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or excluded(path):
                continue
            arcname = Path("Lotus Source") / path.relative_to(ROOT)
            zf.write(path, arcname.as_posix())
        zf.writestr("Lotus Source/Lotus Source.bat", LAUNCHER_BAT)
        info = zipfile.ZipInfo("Lotus Source/Lotus Source.command")
        info.external_attr = 0o755 << 16
        zf.writestr(info, LAUNCHER_COMMAND)
    print(f"built {out.relative_to(ROOT)}")
    return out


DMG_README = """LOTUS BETA — macOS INSTALL
==========================

1. Drag "Lotus Beta.app" onto the Applications folder.

2. FIRST LAUNCH ONLY: macOS may say the developer can't be
   verified (Lotus isn't notarized yet). Fix it either way:
     a) Right-click the app → Open → Open, or
     b) System Settings → Privacy & Security → "Open Anyway".

3. On first launch Lotus asks for your own Gemini API key
   (free at Google AI Studio — the app links you there).

Your data lives in ~/Library/Application Support/Lotus —
updating the app never touches your keys or memories.
"""


def build_dmg() -> Path:
    """Drag-to-Applications installer dmg for macOS end users."""
    app = DIST / "Lotus Beta.app"
    if not app.is_dir():
        raise SystemExit("dist/Lotus Beta.app not found — build it first: "
                         "pyinstaller --clean --noconfirm scripts/lotus_beta_mac.spec")
    out = DIST / "Lotus Beta.dmg"
    out.unlink(missing_ok=True)
    with TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copytree(app, stage / app.name, symlinks=True)
        (stage / "Applications").symlink_to("/Applications")
        (stage / "READ ME FIRST.txt").write_text(DMG_README, encoding="utf-8")
        subprocess.run(
            ["hdiutil", "create", "-volname", "Lotus Beta",
             "-srcfolder", str(stage), "-ov", "-format", "UDZO", str(out)],
            check=True, capture_output=True,
        )
    print(f"built {out.relative_to(ROOT)}")
    return out


def build_mac() -> Path:
    """macOS beta package: the whole Lotus Beta.app bundle. ditto (not
    zipfile) so symlinks and resource metadata inside the app survive."""
    DIST.mkdir(exist_ok=True)
    out = DIST / "Lotus Beta Mac.zip"
    app = DIST / "Lotus Beta.app"
    if not app.is_dir():
        raise SystemExit("dist/Lotus Beta.app not found — build it first: "
                         "pyinstaller --clean --noconfirm scripts/lotus_beta_mac.spec")
    out.unlink(missing_ok=True)
    subprocess.run(
        ["ditto", "-ck", "--sequesterRsrc", "--keepParent",
         str(app), str(out)],
        check=True,
    )
    print(f"built {out.relative_to(ROOT)}")
    return out


def main() -> None:
    if "--mac" in sys.argv or (sys.platform == "darwin" and "--win" not in sys.argv):
        build_mac()
        build_dmg()
        build_source()
        return
    build_app()
    build_source()


if __name__ == "__main__":
    main()
