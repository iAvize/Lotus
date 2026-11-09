"""Purple reactor and Matrix-rain visuals for Lotus."""
from __future__ import annotations

import math
import random
from PyQt6.QtCore import QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QWidget


MATRIX_CHARS = "アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ABCDEF<>/\\{}[]#$%&"


class MatrixRain(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drops: list[int] = []
        self._frame = 0
        self.setMinimumSize(600, 400)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(80)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cols = max(1, self.width() // 18)
        if len(self._drops) != cols:
            self._drops = [random.randint(-40, 0) for _ in range(cols)]

    def _tick(self):
        self._frame += 1
        rows = max(1, self.height() // 18)
        for i in range(len(self._drops)):
            self._drops[i] += 1
            if self._drops[i] * 18 > self.height() + random.randint(80, 240):
                self._drops[i] = random.randint(-30, 0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(8, 5, 18))

        font = QFont("Consolas", 11)
        painter.setFont(font)
        char_w = 18
        trail = 7
        cols = max(1, self.width() // char_w)
        if len(self._drops) < cols:
            self._drops.extend([random.randint(-30, 0) for _ in range(cols - len(self._drops))])

        for col in range(cols):
            x = col * char_w
            head = self._drops[col] if col < len(self._drops) else 0
            for j in range(trail):
                y = (head - j) * 18
                if y < -20 or y > self.height() + 20:
                    continue
                ch = MATRIX_CHARS[(col * 13 + self._frame + j * 7) % len(MATRIX_CHARS)]
                alpha = 230 if j == 0 else max(20, 220 - j * 32)
                color = QColor(168, 85, 247, alpha)
                painter.setPen(color)
                painter.drawText(x, y, ch)
        painter.end()


class ReactorWidget(QWidget):
    def __init__(self, parent=None, size: int = 280):
        super().__init__(parent)
        self._tick = 0
        self._size = size
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(50)

    def _advance(self):
        self._tick += 1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        center = QRectF(0, 0, w, h).center()

        glow = QRadialGradient(center, w * 0.48)
        glow.setColorAt(0.0, QColor(139, 92, 246, 70))
        glow.setColorAt(0.45, QColor(88, 28, 135, 45))
        glow.setColorAt(1.0, QColor(8, 5, 18, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(center.x() - w * 0.48, center.y() - w * 0.48, w * 0.96, w * 0.96))

        rings = [
            (0.46, 8, 26, 120, QColor(168, 85, 247)),
            (0.40, 5, -18, 90, QColor(196, 141, 255)),
            (0.34, 12, 14, 70, QColor(124, 58, 237)),
            (0.28, 7, -32, 140, QColor(216, 180, 254)),
        ]
        for radius_frac, width, speed, span, color in rings:
            radius = w * radius_frac
            rect = QRectF(center.x() - radius, center.y() - radius, radius * 2, radius * 2)
            start = (self._tick * speed) % 360
            painter.setPen(QPen(color, width))
            painter.drawArc(rect, int(start * 16), int(span * 16))
            painter.drawArc(rect, int(((start + 180) % 360) * 16), int(span * 8))

        core_radius = w * 0.19
        core_rect = QRectF(center.x() - core_radius, center.y() - core_radius,
                           core_radius * 2, core_radius * 2)
        core_grad = QRadialGradient(core_rect.center(), core_radius)
        core_grad.setColorAt(0.0, QColor(233, 213, 255, 235))
        core_grad.setColorAt(0.55, QColor(168, 85, 247, 210))
        core_grad.setColorAt(1.0, QColor(76, 29, 149, 180))
        painter.setBrush(core_grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(core_rect)

        font = QFont("Segoe UI", max(54, int(w * 0.22)), QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(250, 245, 255))
        painter.drawText(core_rect, Qt.AlignmentFlag.AlignCenter, "L")
        painter.end()
