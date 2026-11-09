"""Compile-check Lotus Python sources."""
from __future__ import annotations

import compileall
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ok = compileall.compile_dir(str(root / "lotus"), quiet=1, force=True)
print("compileall:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
