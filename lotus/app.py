"""QApplication entry point for Lotus."""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from . import config, db
from .ui.main_window import MainWindow
from .ui.setup_dialog import SetupDialog


def main() -> int:
    db.log("info", "app", "Lotus starting")
    app = QApplication(sys.argv)
    app.setApplicationName("Lotus")
    app.setOrganizationName("Avize")
    window = MainWindow()
    if not config.is_configured():
        SetupDialog(window).exec()
    window.show()
    code = app.exec()
    db.log("info", "app", "Lotus closed")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
