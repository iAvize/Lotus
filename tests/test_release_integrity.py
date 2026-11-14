"""Smoke tests that gate releases — would have caught the empty __init__ crash."""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_version_files_in_sync():
    init = (ROOT / "lotus" / "__init__.py").read_text(encoding="utf-8")
    assert '__version__' in init and 'APP_NAME' in init and len(init.strip()) > 20
    ver = json.loads((ROOT / "version.json").read_text())["version"]
    assert f'__version__ = "{ver}"' in init


def test_themes_valid():
    from lotus.ui import theme
    assert set(theme.THEME_NAMES) == {"purple", "blue", "red", "pink", "green", "orange"}
    for name in theme.THEME_NAMES:
        pal = theme.PALETTES[name]
        assert all(k in pal for k in ("accent", "window", "panel_bg", "title", "subtitle"))
        assert theme.stylesheet(name)


import sys as _sys
import pytest


@pytest.mark.skipif(_sys.platform != "win32",
                    reason="beta zip wraps the Windows PyInstaller exe")
def test_beta_zip_has_no_source(tmp_path):
    import subprocess, sys
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_beta_zip.py")],
                   cwd=ROOT, check=True)
    z = zipfile.ZipFile(ROOT / "dist" / "Lotus Beta.zip")
    names = z.namelist()
    assert not any(n.endswith(".py") for n in names)
    assert any(n.endswith("Lotus Beta.exe") for n in names)


def test_updater_pending_gate(tmp_path):
    from lotus import updater
    assert updater.pending_update(tmp_path) is None
    (tmp_path / "_apply_lotus_update.bat").write_text("@echo off")
    assert updater.pending_update(tmp_path) is not None
    (tmp_path / "_apply_lotus_update.bat").unlink()
    (tmp_path / "_apply_lotus_update.sh").write_text("#!/bin/sh")
    assert updater.pending_update(tmp_path) is not None


def test_crashlog_writes(tmp_path, monkeypatch):
    from lotus import crashlog
    monkeypatch.setattr(crashlog, "_LOG_PATH", tmp_path / "err.log")
    crashlog._write("test-entry\n")
    assert "test-entry" in crashlog.tail_bytes().decode()


def test_personality_defaults_and_clamp(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTUS_DB_DIR", str(tmp_path))
    import importlib
    from lotus import db, personality
    p = personality.get()
    assert set(p["traits"]) == set(personality.TRAITS)
    personality.apply_deltas({"verbosity": 5.0}, "test")
    after = personality.get()
    assert after["traits"]["verbosity"] <= 0.6 + 0.001  # clamped to +0.1
    block = personality.prompt_block()
    assert "Voice calibration" in block and "conversation only" in block
    personality.reset()


def test_usage_metering(tmp_path, monkeypatch):
    monkeypatch.setenv("LOTUS_DB_DIR", str(tmp_path))
    from lotus import usage
    iid = usage.install_id()
    assert len(iid) == 12 and usage.install_id() == iid
    usage.record_tokens(150, "gemini-test")
    usage.record_vm_seconds(120)
    s = usage.summary()
    assert s["all_time"]["tokens"] == 150 and s["all_time"]["vm_minutes"] == 2.0
    assert s["today"]["tokens"] == 150
    usage.reset()
    assert usage.summary()["all_time"]["tokens"] == 0
