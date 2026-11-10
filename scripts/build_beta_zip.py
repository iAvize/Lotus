"""Build Windows beta and source zip artifacts for Lotus.

Run from the repo root:  python scripts/build_beta_zip.py

`Lotus Beta.zip` is the PUBLIC package — compiled app only, no source code
or developer assets. Editable/developer content ships exclusively inside the
AES-locked trusted-developers zip.
"""
from __future__ import annotations

import json
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


def main() -> None:
    build_app()
    build_source()


if __name__ == "__main__":
    main()
