"""Build the password-protected trusted developer source zip.

Requires pyzipper:
    pip install pyzipper
Set LOTUS_SOURCE_ZIP_PASSWORD before running. The zip contains the source tree
plus the Windows `Lotus Beta.exe` so trusted developers get the same app.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pyzipper

from build_beta_zip import LAUNCHER_BAT, LAUNCHER_COMMAND, ROOT, excluded

OUT = ROOT / "dist" / "Lotus.Source.Trusted.Developers.zip"
EXE = ROOT / "dist" / "Lotus Beta.exe"


def main() -> None:
    password = os.environ.get("LOTUS_SOURCE_ZIP_PASSWORD", "")
    if not password:
        raise SystemExit("LOTUS_SOURCE_ZIP_PASSWORD is not set")
    if not EXE.is_file():
        raise SystemExit("dist/Lotus Beta.exe not found — build the Windows exe first")

    OUT.parent.mkdir(exist_ok=True)
    OUT.unlink(missing_ok=True)
    with pyzipper.AESZipFile(
        str(OUT), "w", compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as zf:
        zf.setpassword(password.encode("utf-8"))
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or excluded(path):
                continue
            arcname = Path("Lotus Source") / path.relative_to(ROOT)
            zf.write(path, arcname.as_posix())

        zf.write(EXE, "Lotus Source/Lotus Beta.exe")
        zf.writestr("Lotus Source/Lotus Source.bat", LAUNCHER_BAT)
        info = zipfile.ZipInfo("Lotus Source/Lotus Source.command")
        info.external_attr = 0o755 << 16
        info.compress_type = pyzipper.ZIP_DEFLATED
        zf.writestr(info, LAUNCHER_COMMAND)

    print(f"built {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
