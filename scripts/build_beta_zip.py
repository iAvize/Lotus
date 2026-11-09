"""Build Windows beta and source zip artifacts for Lotus.

Run from the repo root:  python scripts/build_beta_zip.py
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
EXCLUDE_FILES = {"api_keys.json", ".env"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log"}

APP_TOP_LEVEL = {
    "lotus",
    "Run-Lotus.bat",
    "requirements.txt",
    "README.md",
    "LICENSE",
    "version.json",
}
APP_SCRIPTS = {
    "Run-Lotus.ps1",
    "setup_windows.ps1",
    "setup_windows.bat",
}


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


def include_in_app(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if len(rel.parts) == 1:
        return rel.parts[0] in APP_TOP_LEVEL
    if rel.parts[0] == "lotus":
        return True
    if rel.parts[0] == "scripts":
        return len(rel.parts) == 2 and rel.parts[1] in APP_SCRIPTS
    return False


def add_file(zf: zipfile.ZipFile, path: Path, arc_root: str) -> None:
    arcname = Path(arc_root) / path.relative_to(ROOT)
    zf.write(path, arcname.as_posix())


def build(kind: str) -> Path:
    ver = version()
    DIST.mkdir(exist_ok=True)
    if kind == "app":
        out = DIST / f"Lotus-Beta-{ver}-Windows.zip"
        arc_root = "Lotus"
        predicate = include_in_app
    else:
        out = DIST / f"Lotus-Source-{ver}.zip"
        arc_root = "Lotus"
        predicate = lambda path: not excluded(path)

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or excluded(path) or not predicate(path):
                continue
            add_file(zf, path, arc_root)

    print(f"built {out.relative_to(ROOT)}")
    return out


def main() -> None:
    build("app")
    build("source")


if __name__ == "__main__":
    main()
