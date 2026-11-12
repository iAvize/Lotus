"""Orb nav - Nexus-style carousel of overlapping circular nodes that
wheel-scroll through the app sections. The active orb centers itself.

Swap-in replacement for the left button nav; the old nav code stays in
main_window.py for revert.
"""
from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from . import theme

ICONS = {
    "ask": "L", "logs": "H", "scan": "S", "devbox": "D",
    "personality": "P", "patchnotes": "N",
}


class OrbNav(QWidget):
    section_selected = pyqtSignal(str)

    R = 40
    SPACING = 64
    STRIP_H = 110

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.STRIP_H)
        self.setMinimumWidth(0)
        self._sections: list[tuple[str, str]] = []
        self._pos = 0.0
        self._target = 0.0
        self._anim = QPropertyAnimation(self, b"scrollPos", self)
        self._anim.setDuration(240)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._theme = theme.current()

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, v: float):
        self._pos = v
        self.update()

    scrollPos = property(_get_pos, _set_pos)

    def set_sections(self, sections: list[tuple[str, str]]):
        self._sections = sections
        self.update()

    def set_active(self, key: str):
        for i, (k, _t) in enumerate(self._sections):
            if k == key:
                self._scroll_to(i)
                return

    def apply_theme(self):
        self._theme = theme.current()
        self.update()

    def _scroll_to(self, idx: float):
        idx = max(0.0, min(len(self._sections) - 1, idx))
        if abs(idx - self._target) < 0.01:
            return
        self._target = idx
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(idx)
        self._anim.start()
        nearest = round(idx)
        if 0 <= nearest < len(self._sections):
            self.section_selected.emit(self._sections[nearest][0])

    def wheelEvent(self, e):
        step = -1 if e.angleDelta().y() > 0 else 1
        self._scroll_to(round(self._target) + step)

    def mousePressEvent(self, e):
        cx = self.width() / 2
        for i in range(len(self._sections)):
            x = cx + (i - self._pos) * self.SPACING
            if (e.position().x() - x) ** 2 + (e.position().y() - 52) ** 2 <= self.R ** 2:
                self._scroll_to(i)
                return

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        T = self._theme
        cx = self.width() / 2
        cy = 52
        accent = QColor(T["accent"])
        order = sorted(range(len(self._sections)),
                       key=lambda i: abs(i - self._pos), reverse=True)
        for i in order:
            k, title = self._sections[i]
            x = cx + (i - self._pos) * self.SPACING
            d = abs(i - self._pos)
            active = d < 0.5
            r = self.R * (1.08 if active else 0.92)
            if x < -r or x > self.width() + r:
                continue
            fade = max(0.25, 1.0 - d * 0.22)
            edge = QColor(accent)
            edge.setAlpha(int(255 * fade) if active else int(160 * fade))
            fill = QColor(20, 12, 38, int(220 * fade))
            if active:
                glow = QColor(accent)
                glow.setAlpha(46)
                p.setBrush(glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(int(x - r - 9), int(cy - r - 9),
                              int((r + 9) * 2), int((r + 9) * 2))
            p.setBrush(fill)
            p.setPen(QPen(edge, 2.4 if active else 1.6))
            p.drawEllipse(int(x - r), int(cy - r), int(r * 2), int(r * 2))
            p.setPen(QColor(T["title"] if active else T["subtitle"]))
            f = QFont(); f.setPixelSize(22 if active else 18); f.setBold(active)
            p.setFont(f)
            p.drawText(int(x - r), int(cy - r - 4), int(r * 2), int(r * 2),
                       Qt.AlignmentFlag.AlignCenter, ICONS.get(k, "?"))
            if d < 1.3:
                f2 = QFont(); f2.setPixelSize(10 if active else 8)
                f2.setBold(active)
                p.setFont(f2)
                lc = QColor(T["accent_light"] if active else T["subtitle"])
                lc.setAlpha(int(230 * fade))
                p.setPen(lc)
                p.drawText(int(x - 70), cy + int(r) + 8, 140, 18,
                           Qt.AlignmentFlag.AlignCenter, title)
        p.end()
