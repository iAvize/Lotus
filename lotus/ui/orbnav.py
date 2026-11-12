"""Orb nav - Nexus-style carousel of overlapping circular nodes.

Hover-scrub: moving the cursor over the orbs slides the carousel - each
orb under the cursor drifts to center. Clicking jumps to that orb. The
centered orb glows, grows, and every orb shows its section label below.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from . import theme


class OrbNav(QWidget):
    section_selected = pyqtSignal(str)

    R = 46
    SPACING = 68
    STRIP_H = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.STRIP_H)
        self.setMinimumWidth(0)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._sections: list[tuple[str, str]] = []
        self._pos = 0.0
        self._target = 0.0
        self._dragging = False
        self._drag_x = 0.0
        self._drag_pos = 0.0
        self._anim = QPropertyAnimation(self, b"scrollPos", self)
        self._anim.setDuration(260)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._theme = theme.current()

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, v: float):
        self._pos = max(-0.4, min(len(self._sections) - 0.6, v))
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

    def _orb_at(self, x: float, y: float) -> int:
        cx = self.width() / 2
        for i in range(len(self._sections)):
            ox = cx + (i - self._pos) * self.SPACING
            if (x - ox) ** 2 + (y - 62) ** 2 <= self.R ** 2:
                return i
        return -1

    def mouseMoveEvent(self, e):
        if self._dragging:
            delta = e.position().x() - self._drag_x
            self._set_pos(self._drag_pos - delta / self.SPACING)
            return
        idx = self._orb_at(e.position().x(), e.position().y())
        if idx >= 0:
            self._scroll_to(idx)

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging = True
        self._drag_x = e.position().x()
        self._drag_pos = self._pos
        self._anim.stop()

    def mouseReleaseEvent(self, e):
        if not self._dragging:
            return
        self._dragging = False
        if abs(e.position().x() - self._drag_x) < 6:
            idx = self._orb_at(e.position().x(), e.position().y())
            if idx >= 0:
                self._scroll_to(idx)
                return
        self._scroll_to(round(self._pos))

    def wheelEvent(self, e):
        step = -1 if e.angleDelta().y() > 0 else 1
        self._scroll_to(round(self._pos) + step)

    def _star(self, p, x, y, r, color):
        pts = []
        for i in range(8):
            a = math.pi * i / 4 - math.pi / 2
            rr = r if i % 2 == 0 else r * 0.38
            pts.append(QPointF(x + rr * math.cos(a), y + rr * math.sin(a)))
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF(pts))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        T = self._theme
        cx = self.width() / 2
        cy = 62
        accent = QColor(T["accent"])
        order = sorted(range(len(self._sections)),
                       key=lambda i: abs(i - self._pos), reverse=True)
        for i in order:
            _k, title = self._sections[i]
            x = cx + (i - self._pos) * self.SPACING
            d = abs(i - self._pos)
            active = d < 0.5
            r = self.R * (1.1 if active else 0.88)
            if x < -r or x > self.width() + r:
                continue
            fade = max(0.16, 1.0 - d * 0.24)
            edge = QColor(accent)
            edge.setAlpha(int(255 * fade) if active else int(140 * fade))
            fill = QColor(18, 10, 34, int(215 * fade))
            if active:
                glow = QColor(accent)
                glow.setAlpha(48)
                p.setBrush(glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(int(x - r - 11), int(cy - r - 11),
                              int((r + 11) * 2), int((r + 11) * 2))
            p.setBrush(fill)
            p.setPen(QPen(edge, 2.6 if active else 1.5))
            p.drawEllipse(int(x - r), int(cy - r), int(r * 2), int(r * 2))
            inner = QColor(accent)
            inner.setAlpha(int(80 * fade))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(inner, 1.1))
            ir = r * 0.6
            p.drawEllipse(int(x - ir), int(cy - ir), int(ir * 2), int(ir * 2))
            dot = QColor(T["accent_light"] if active else T["subtitle"])
            dot.setAlpha(int(255 * fade))
            self._star(p, x, cy, 7 if active else 5, dot)
            if d < 1.8:
                f = QFont(); f.setPixelSize(11 if active else 8)
                f.setBold(active)
                p.setFont(f)
                lc = QColor(T["accent_light"] if active else T["subtitle"])
                lc.setAlpha(int(235 * fade * fade))
                p.setPen(lc)
                p.drawText(int(x - 65), cy + int(r) + 12, 130, 20,
                           Qt.AlignmentFlag.AlignCenter, title)
        p.end()
