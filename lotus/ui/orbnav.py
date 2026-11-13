"""Orb nav - Grid-style carousel of overlapping circular nodes.

Ported from the Grid's menu carousel: neighbours arc down and shrink as
they recede, the focused orb glows with a radial bloom, every orb wears
a rotating tick ring on its outer orbit and the core/diamond icon at its
centre. Hover over an orb to slide it to centre; click the centred orb
to open its panel. Fully theme-driven - every painted colour comes from
the active palette so theme swaps repaint instantly.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QRectF, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF, QRadialGradient
from PyQt6.QtWidgets import QWidget

from . import theme


def _col(hex_or_qcolor, alpha=255):
    c = QColor(hex_or_qcolor)
    c.setAlpha(int(alpha))
    return c


class OrbNav(QWidget):
    section_selected = pyqtSignal(str)

    R = 80
    SPACING = 130
    STRIP_H = 230

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
        self._t = 0.0
        self._tick = QTimer(self)
        self._tick.setInterval(50)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()
        self._theme = theme.current()

    def _on_tick(self):
        self._t += 0.05
        self.update()

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

    # -- geometry: the Grid's arc -------------------------------------------
    def _geom(self):
        return self.width() / 2, 105, self.SPACING

    def _node(self, i):
        cx, cy, sp = self._geom()
        off = i - self._pos
        return (cx + off * sp,
                cy + abs(off) * sp * 0.10,
                self.R * max(0.55, 1.0 - 0.10 * abs(off)),
                max(0.0, 1.0 - 0.27 * abs(off)))

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
        best, bd = -1, 1e9
        for i in range(len(self._sections)):
            nx, ny, r, a = self._node(i)
            d = ((x - nx) ** 2 + (y - ny) ** 2) ** 0.5
            if a > 0.05 and d <= r * 1.1 and d < bd:
                best, bd = i, d
        return best

    # -- input ---------------------------------------------------------------
    def mouseMoveEvent(self, e):
        # HOVER SCRUB: instant first step, then a paced walk toward the orb
        # the cursor rests on.
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

    # -- paint: the Grid's node, themed --------------------------------------
    def _draw_core_icon(self, p, x, y, s, colour):
        """Diamond star at the orb's centre."""
        pts = []
        for i in range(8):
            a = math.pi * i / 4 - math.pi / 2
            rr = s if i % 2 == 0 else s * 0.38
            pts.append(QPointF(x + rr * math.cos(a), y + rr * math.sin(a)))
        p.setBrush(QBrush(colour))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF(pts))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        T = self._theme
        accent, accent_light, dim = T["accent"], T["accent_light"], T["subtitle"]
        order = sorted(range(len(self._sections)),
                       key=lambda i: -abs(i - self._pos))
        for i in order:
            _k, title = self._sections[i]
            x, y, r, a = self._node(i)
            if a <= 0.02 or r < 2 or x < -r * 2 or x > self.width() + r * 2:
                continue
            sel = i == round(self._pos)
            # radial bloom behind the focused orb
            if sel:
                g = QRadialGradient(x, y, r * 2.0)
                g.setColorAt(0.0, _col(accent, 120 * a))
                g.setColorAt(0.55, _col(accent, 40 * a))
                g.setColorAt(1.0, _col(accent, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(g))
                p.drawEllipse(QRectF(x - r * 2, y - r * 2, r * 4, r * 4))
            # orb body - radial gradient, theme-tinted
            g = QRadialGradient(x, y - r * 0.3, r * 1.05)
            g.setColorAt(0.0, _col(T["panel_border"], (110 if sel else 70) * a))
            g.setColorAt(1.0, _col(T["nav_bg"], (190 if sel else 140) * a))
            p.setBrush(QBrush(g))
            p.setPen(QPen(_col(accent_light if sel else accent,
                               (255 if sel else 170) * a),
                          2.4 if sel else 1.3))
            p.drawEllipse(QRectF(x - r, y - r, r * 2, r * 2))
            # radial tick ring on the outer orbit - rotating arc pair
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(_col(accent_light if sel else accent,
                               (150 if sel else 70) * a), 1.6 if sel else 1.2))
            orbit = QRectF(x - r * 1.14, y - r * 1.14, r * 2.28, r * 2.28)
            start = int(((self._t * 40) % 360) * 16)
            p.drawArc(orbit, start, 70 * 16)
            p.drawArc(orbit, start + 180 * 16, 34 * 16)
            # diamond-type core icon
            self._draw_core_icon(
                p, x, y, r * 0.16,
                _col(accent_light if sel else accent, 255 * a))
            # label under every orb
            if a > 0.12:
                f = QFont()
                f.setPixelSize(12 if sel else 9)
                f.setBold(sel)
                p.setFont(f)
                p.setPen(_col(accent_light if sel else dim, 235 * a))
                p.drawText(int(x - 90), int(y + r + 10), 180, 20,
                           Qt.AlignmentFlag.AlignCenter, title)
        p.end()
