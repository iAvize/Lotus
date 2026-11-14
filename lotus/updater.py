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
        if "beta" in name:
            score += 2
        if sys.platform == "win32" and "windows" in name:
            score += 2
        if sys.platform == "darwin" and ("macos" in name or "mac" in name):
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
    name = asset.get("name") or f"Lotus-{info.get('version', 'update')}.zip"
    if not url:
        raise RuntimeError("The latest release has no downloadable zip asset.")

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


def _launch_helper(script: Path) -> None:
    """Detach the staged apply-script so it outlives the exiting app."""
    if sys.platform == "win32":
        creationflags = 0
        for flag in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP",
                     "CREATE_NO_WINDOW"):
            if hasattr(subprocess, flag):
                creationflags |= getattr(subprocess, flag)
        subprocess.Popen(["cmd.exe", "/c", str(script)], cwd=str(script.parent),
                         creationflags=creationflags, close_fds=True)
    else:
        subprocess.Popen(["/bin/sh", str(script)], cwd=str(script.parent),
                         start_new_session=True, close_fds=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL)


_APPLY_NAMES = ("_apply_lotus_update.bat", "_apply_lotus_update.sh")


def pending_update(app_dir: Path | None = None) -> Path | None:
    """The apply-script a previous 'update on relaunch' left behind. Its mere
    existence means an update is owed before the app may be used."""
    app_dir = app_dir or config.BASE_DIR
    for name in _APPLY_NAMES:
        candidate = app_dir / name
        if candidate.exists():
            return candidate
    return None


def run_pending(app_dir: Path | None = None) -> bool:
    """Launch the staged apply-script; caller must exit immediately after."""
    script = pending_update(app_dir)
    if not script:
        return False
    _launch_helper(script)
    return True


def _relaunch_line() -> str:
    """POSIX: how the apply-script brings Lotus back after swapping files."""
    exe = Path(sys.executable).resolve()
    for parent in (exe, *exe.parents):
        if parent.suffix == ".app":
            return f'open "{parent}"'
    return f'cd "$DST" && nohup "{exe}" -m lotus >/dev/null 2>&1 &'


def apply_update(zip_path: Path, app_dir: Path | None = None,
                 launch: bool = True) -> Path:
    """Stage an update and (optionally) launch the helper script that swaps
    files after exit. launch=False defers the swap to the next app start —
    app.py checks pending_update() before showing any UI."""
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

    src = staging
    dst = app_dir
    if sys.platform == "win32":
        script = app_dir / "_apply_lotus_update.bat"
        script.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            f'set "SRC={src}"\r\n'
            f'set "DST={dst}"\r\n'
            "timeout /t 2 /nobreak >nul\r\n"
            'robocopy "%SRC%" "%DST%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /XD .git memory config .venv venv __pycache__ dist /XF api_keys.json lotus_ai.db >nul\r\n'
            'if exist "%SRC%" rmdir /s /q "%SRC%"\r\n'
            'if exist "%DST%\\Lotus Beta.exe" (start "" "%DST%\\Lotus Beta.exe") else (if exist "%DST%\\Run-Lotus.bat" start "" "%DST%\\Run-Lotus.bat")\r\n'
            'del "%~f0"\r\n',
            encoding="utf-8",
        )
    else:
        script = app_dir / "_apply_lotus_update.sh"
        script.write_text(
            "#!/bin/sh\n"
            f'SRC="{src}"\n'
            f'DST="{dst}"\n'
            "sleep 2\n"
            'rsync -a --exclude .git --exclude memory --exclude config '
            '--exclude .venv --exclude venv --exclude __pycache__ '
            '--exclude dist --exclude api_keys.json --exclude lotus_ai.db '
            '"$SRC"/ "$DST"/\n'
            'rm -rf "$SRC"\n'
            f"{_relaunch_line()}\n"
            'rm -f "$0"\n',
            encoding="utf-8",
        )
        script.chmod(0o755)

    if launch:
        _launch_helper(script)
    return script
