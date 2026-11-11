"""QApplication entry point for Lotus."""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen

from . import config, db, updater
from . import crashlog
from .ui.main_window import MainWindow
from .ui.setup_dialog import SetupDialog


def _apply_pending_update(app: QApplication) -> int:
    """A staged 'update on relaunch' is owed — apply it before anything else.
    Shows a brief splash, hands off to the apply batch (which relaunches
    Lotus itself), and exits so the app can't be used un-updated."""
    db.log("info", "app", "staged update found — applying before launch")
    pix = QPixmap(480, 160)
    pix.fill(QColor("#130b24"))
    splash = QSplashScreen(pix)
    splash.showMessage("Applying Lotus update…", Qt.AlignmentFlag.AlignCenter,
                       QColor("#c4b5fd"))
    splash.show()
    updater.run_pending()
    QTimer.singleShot(1500, app.quit)
    app.exec()
    return 0


def main() -> int:
    crashlog.install()
    db.log("info", "app", "Lotus starting")
    app = QApplication(sys.argv)
    app.setApplicationName("Lotus")
    app.setOrganizationName("Avize")
    if updater.pending_update():
        return _apply_pending_update(app)
    from .ui.splash import LotusSplash
    splash = LotusSplash()
    splash.show()
    app.processEvents()
    window = MainWindow()
    if not config.is_configured():
        SetupDialog(window).exec()
    window.show()
    splash.finish(window)
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(600, window._maybe_show_patchnotes)
    code = app.exec()
    db.log("info", "app", "Lotus closed")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
