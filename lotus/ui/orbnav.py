"""Orb nav - Nexus-style carousel of overlapping circular nodes.

Hover-scrub: moving the cursor over the orbs slides the carousel - each
orb under the cursor drifts to center. Clicking jumps to that orb. The
centered orb glows, grows, and every orb shows its section label below.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget

from . import theme


class OrbNav(QWidget):
    section_selected = pyqtSignal(str)

    R = 52
    SPACING = 78
    STRIP_H = 160

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.STRIP_H)
        self.setMinimumWidth(0)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._sections: list[tuple[str, str]] = []
        self._pos = 0.0
        self._target = 0.0
        self._press_x = -1.0
        self._hover_target = -1
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(950)
        self._hover_timer.timeout.connect(self._step_toward_hover)
        self._anim = QPropertyAnimation(self, b"scrollPos", self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._theme = theme.current()

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, v: float):
        self._pos = max(-0.4, min(len(self._sections) - 0.6, v))
        self.update()

    scrollPos = pyqtProperty(float, fget=_get_pos, fset=_set_pos)

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

    def _orb_at(self, x: float, y: float) -> int:
        cx = self.width() / 2
        for i in range(len(self._sections)):
            ox = cx + (i - self._pos) * self.SPACING
            if (x - ox) ** 2 + (y - 68) ** 2 <= self.R ** 2:
                return i
        return -1

    def mouseMoveEvent(self, e):
        # HOVER SCRUB: the carousel steps one orb at a time toward whatever
        # orb the cursor rests on - slow enough to stop on the one you want.
        idx = self._orb_at(e.position().x(), e.position().y())
        if idx < 0:
            return
        if idx != self._hover_target:
            self._hover_target = idx
            self._step_toward_hover()
            self._hover_timer.start()

    def leaveEvent(self, e):
        self._hover_target = -1
        self._hover_timer.stop()
        super().leaveEvent(e)

    def _step_toward_hover(self):
        if self._hover_target < 0:
            self._hover_timer.stop()
            return
        current = round(self._target)
        if self._hover_target > current:
            self._scroll_to(min(current + 1, self._hover_target))
        elif self._hover_target < current:
            self._scroll_to(max(current - 1, self._hover_target))
        else:
            self._hover_timer.stop()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_x = e.position().x()

    def mouseReleaseEvent(self, e):
        # Click = open the focused orb only; clicks never scrub the carousel.
        if e.button() != Qt.MouseButton.LeftButton or self._press_x < 0:
            return
        self._press_x = -1.0
        idx = self._orb_at(e.position().x(), e.position().y())
        if idx >= 0 and abs(idx - self._pos) < 0.5:
            self.section_selected.emit(self._sections[idx][0])

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
        cy = 68
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
