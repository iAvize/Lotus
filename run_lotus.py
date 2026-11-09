"""Windows entry point used for packaged Lotus builds."""
from __future__ import annotations

from lotus.app import main

if __name__ == "__main__":
    raise SystemExit(main())
