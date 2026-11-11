"""Animated launch splash — the Lotus reactor logo on a dark card while
the app initializes. Frameless, always on top, closes when the main
window is ready (a short minimum so the animation is glimpsed)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import __version__
from .widgets import ReactorWidget


class LotusSplash(QWidget):
    def __init__(self, min_ms: int = 1400):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(360, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self._reactor = ReactorWidget(self, size=240)
        row.addWidget(self._reactor)
        row.addStretch(1)
        layout.addLayout(row)
        title = QLabel("LOTUS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #e9d5ff; font-size: 24px; font-weight: 800;"
                            " letter-spacing: 8px;")
        layout.addWidget(title)
        sub = QLabel("cybersecurity ai · beta")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #a78bfa; font-size: 11px; letter-spacing: 2px;")
        layout.addWidget(sub)
        ver = QLabel(f"v{__version__}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #5b4a86; font-size: 10px;")
        layout.addWidget(ver)
        layout.addStretch(1)
        self._min_ms = min_ms

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(13, 8, 26, 246))
        p.setPen(QColor(76, 42, 125))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)

    def show(self):
        super().show()
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            self.move(g.center() - self.rect().center())

    def finish(self, main_window=None):
        QTimer.singleShot(self._min_ms, self.close)
