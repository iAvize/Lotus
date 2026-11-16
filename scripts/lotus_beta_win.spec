# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Windows Lotus Beta.exe one-file build.

Build from the repo root:
    pyinstaller --clean --noconfirm scripts/lotus_beta_win.spec
Output: dist/Lotus Beta.exe
"""
import json
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent  # repo root (spec lives in scripts/)
_version = json.loads((ROOT / "version.json").read_text())["version"]

a = Analysis(
    [str(ROOT / "run_lotus.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "lotus" / "assets"), "lotus/assets"),
        (str(ROOT / "version.json"), "."),
        (str(ROOT / "README.md"), "."),
        (str(ROOT / "LICENSE"), "."),
    ] + collect_data_files("tzdata"),
    hiddenimports=["lotus.devbox", "lotus.startup", "winreg"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PySide2", "PySide6", "tkinter", "matplotlib", "numpy",
              "pandas", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Lotus Beta",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(ROOT / "lotus" / "assets" / "lotus.ico")],
)
