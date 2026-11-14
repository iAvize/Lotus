# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the macOS Lotus Beta.app bundle.

Build from the repo root:
    .venv/bin/pyinstaller --clean --noconfirm scripts/lotus_beta_mac.spec
Output: dist/Lotus Beta.app
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
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PySide2", "PySide6", "tkinter", "matplotlib", "numpy",
              "pandas", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Lotus Beta",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Lotus Beta",
)
app = BUNDLE(
    coll,
    name="Lotus Beta.app",
    icon=str(ROOT / "lotus" / "assets" / "lotus.icns"),
    bundle_identifier="com.avize.lotus.beta",
    version=_version,
    info_plist={
        "CFBundleName": "Lotus Beta",
        "CFBundleDisplayName": "Lotus Beta",
        "CFBundleShortVersionString": _version,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
)
