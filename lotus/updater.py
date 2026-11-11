"""GitHub release update checks and self-update helpers for Lotus beta."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import requests

from . import config

REPO = "iAvize/Lotus"


def _version_tuple(value: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", str(value))
    return tuple(int(n) for n in nums[:4]) or (0,)


def _local_version() -> str:
    try:
        from . import __version__  # the binary's own version is authoritative
        if __version__:
            return __version__
    except Exception:
        pass
    try:
        data = json.loads((config.BASE_DIR / "version.json").read_text(encoding="utf-8"))
        return str(data.get("version") or "")
    except Exception:
        return ""


def check_for_update(repo: str = REPO, timeout: int = 15) -> dict | None:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Lotus-Beta",
    }, timeout=timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    remote = str(data.get("tag_name") or "").lstrip("v")
    local = _local_version().lstrip("v")
    if not remote or _version_tuple(remote) <= _version_tuple(local):
        return None

    assets = data.get("assets") or []
    zip_assets = [a for a in assets if str(a.get("name", "")).lower().endswith(".zip")]

    def asset_score(asset: dict) -> int:
        name = str(asset.get("name", "")).lower()
        score = 1
        if "beta" in name or "windows" in name:
            score += 2
        if "source" in name:
            score -= 3
        return score

    asset = max(zip_assets, key=asset_score, default=None)
    return {
        "repo": repo,
        "version": remote,
        "name": data.get("name") or f"Lotus {remote}",
        "body": data.get("body") or "",
        "html_url": data.get("html_url") or "",
        "published_at": data.get("published_at") or "",
        "asset": asset,
    }


def download_update(info: dict, dest_dir: Path | None = None,
                    progress=None) -> Path:
    asset = info.get("asset") or {}
    url = asset.get("browser_download_url") or asset.get("url")
    name = asset.get("name") or f"Lotus-{info.get('version', 'update')}-Windows.zip"
    if not url:
        raise RuntimeError("The latest release has no downloadable Windows zip asset.")

    dest_dir = dest_dir or (config.UPDATE_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name

    headers = {"User-Agent": "Lotus-Beta"}
    if "api.github.com" in url:
        headers["Accept"] = "application/octet-stream"

    with requests.get(url, headers=headers, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        with dest.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    return dest


def _zip_source_dir(zip_path: Path, extract_dir: Path) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    roots = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(roots) == 1:
        return roots[0]
    return extract_dir


def _launch_bat(bat: Path) -> None:
    creationflags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["cmd.exe", "/c", str(bat)], cwd=str(bat.parent),
                     creationflags=creationflags, close_fds=True)


def pending_update(app_dir: Path | None = None) -> Path | None:
    """The apply-batch a previous 'update on relaunch' left behind. Its mere
    existence means an update is owed before the app may be used."""
    app_dir = app_dir or config.BASE_DIR
    bat = app_dir / "_apply_lotus_update.bat"
    return bat if bat.exists() else None


def run_pending(app_dir: Path | None = None) -> bool:
    """Launch the staged apply-batch; caller must exit immediately after."""
    bat = pending_update(app_dir)
    if not bat:
        return False
    _launch_bat(bat)
    return True


def apply_update(zip_path: Path, app_dir: Path | None = None,
                 launch: bool = True) -> Path:
    """Stage an update and (optionally) launch the helper batch that swaps
    files after exit. launch=False defers the swap to the next app start —
    app.py checks pending_update() before showing any UI."""
    if sys.platform != "win32":
        raise RuntimeError("Self-update is currently implemented for Windows beta only.")

    app_dir = (app_dir or config.BASE_DIR).resolve()
    staging = app_dir / "_lotus_update_staging"
    if staging.exists():
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lotus-update-") as tmp:
        source = _zip_source_dir(zip_path, Path(tmp))
        import shutil
        for item in source.iterdir():
            dest = staging / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    bat = app_dir / "_apply_lotus_update.bat"
    src = staging
    dst = app_dir
    bat.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "SRC={src}"\r\n'
        f'set "DST={dst}"\r\n'
        "timeout /t 2 /nobreak >nul\r\n"
        'robocopy "%SRC%" "%DST%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /XD .git memory config .venv venv __pycache__ dist /XF api_keys.json lotus_ai.db >nul\r\n'
        'if exist "%SRC%" rmdir /s /q "%SRC%"\r\n'
        'if exist "%DST%\\Run-Lotus.bat" start "" "%DST%\\Run-Lotus.bat"\r\n'
        'del "%~f0"\r\n',
        encoding="utf-8",
    )

    if launch:
        _launch_bat(bat)
    return bat
