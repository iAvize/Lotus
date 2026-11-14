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
        build_source()
        return
    build_app()
    build_source()


if __name__ == "__main__":
    main()
