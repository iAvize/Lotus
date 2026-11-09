"""Local paths and machine-local configuration for Lotus.

Secrets live only in config/api_keys.json, which is git-ignored. The SQLite
database lives under memory/ and is also git-ignored.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"
MEMORY_DIR = BASE_DIR / "memory"
DB_PATH = MEMORY_DIR / "lotus_ai.db"
QUARANTINE_DIR = MEMORY_DIR / "quarantine"
UPDATE_DIR = MEMORY_DIR / "updates"


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict) -> None:
    ensure_dirs()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)


def _save_value(key: str, value: str) -> None:
    data = load_config()
    data[key] = value.strip()
    save_config(data)


def get_gemini_key() -> str:
    return str(load_config().get("gemini_api_key") or "")


def save_gemini_key(key: str) -> None:
    _save_value("gemini_api_key", key)


def is_configured() -> bool:
    return len(get_gemini_key()) > 15


def get_github_token() -> str:
    return str(load_config().get("github_token") or "")


def save_github_token(token: str) -> None:
    _save_value("github_token", token)


def get_setting(key: str, default: str = "") -> str:
    return str(load_config().get(key, default) or default)


def save_setting(key: str, value: str) -> None:
    _save_value(key, value)


def jarvis_config_candidates() -> list[Path]:
    """Likely places the existing Jarvis install keeps config/api_keys.json."""
    candidates: list[Path] = []
    env_home = os.environ.get("JARVIS_HOME")
    if env_home:
        candidates.append(Path(env_home) / "config" / "api_keys.json")

    home = Path.home()
    candidates.extend([
        Path(r"D:\Mark-LVI-main\config\api_keys.json"),
        home / "Mark-LVI-main" / "config" / "api_keys.json",
        home / "repos" / "Jarvis" / "config" / "api_keys.json",
        BASE_DIR.parent / "Mark-LVI-main" / "config" / "api_keys.json",
        BASE_DIR.parent / "Jarvis" / "config" / "api_keys.json",
    ])

    seen = set()
    out = []
    for p in candidates:
        try:
            resolved = p.resolve()
        except Exception:
            resolved = p
        if resolved not in seen and resolved.exists():
            seen.add(resolved)
            out.append(resolved)
    return out


def read_jarvis_gemini_key(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("gemini_api_key") or "")
    except Exception:
        return ""
