"""Clock box - Nexus-style local-time widget anchored top-right of the UI.

Shows date, 12h time with running seconds and AM/PM, ISO week + day of
year, and a full world-timezone dropdown (persisted in settings). The
date format follows the chosen timezone's regional convention. When a
section panel opens the box collapses to a slim time+date readout.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .. import db
from . import theme

_YMD_CITIES = {"Tokyo", "Seoul", "Shanghai", "Hong_Kong", "Taipei", "Singapore", "Beijing", "Macau", "Pyongyang"}


def _date_format(tzname: str) -> str:
    if not tzname:
        return "%b %d, %Y"
    region = tzname.split("/")[0]
    city = tzname.split("/")[-1]
    if region in ("America", "US"):
        return "%b %d, %Y"
    if region == "Asia" and city in _YMD_CITIES:
        return "%Y %b %d"
    return "%d %b %Y"


class ClockBox(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("clockbox")
        self._compact = False
        self._tzname = db.get_setting("ui_timezone") or ""

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(4)

        top = QHBoxLayout()
        self.date_label = QLabel()
        self.date_label.setObjectName("clockdate")
        top.addWidget(self.date_label)
        top.addStretch(1)
        dot = QLabel("\u25CF SYNCED")
        dot.setObjectName("clocksync")
        top.addWidget(dot)
        root.addLayout(top)

        mid = QHBoxLayout()
        mid.setSpacing(6)
        mid.addStretch(1)
        self.time_label = QLabel()
        self.time_label.setObjectName("clocktime")
        mid.addWidget(self.time_label)
        side = QVBoxLayout()
        side.setSpacing(0)
        self.sec_label = QLabel()
        self.sec_label.setObjectName("clocksec")
        self.ampm_label = QLabel()
        self.ampm_label.setObjectName("clockampm")
        side.addWidget(self.sec_label)
        side.addWidget(self.ampm_label)
        mid.addLayout(side)
        mid.addStretch(1)
        root.addLayout(mid)

        self._info_row = QHBoxLayout()
        self._info_row.setSpacing(18)
        self._info_row.addStretch(1)
        self.day_label = QLabel()
        self.day_label.setObjectName("clockmeta")
        self.day_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.week_label = QLabel()
        self.week_label.setObjectName("clockmeta")
        self.week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_row.addWidget(self.day_label)
        self._info_row.addWidget(self.week_label)
        self._info_row.addStretch(1)
        root.addLayout(self._info_row)

        self.tz_box = QComboBox()
        self.tz_box.setEditable(True)
        self.tz_box.lineEdit().setReadOnly(True)
        self.tz_box.addItem("Local (system)", "")
        for z in sorted(available_timezones()):
            self.tz_box.addItem(z.replace("_", " "), z)
        idx = self.tz_box.findData(self._tzname)
        self.tz_box.setCurrentIndex(idx if idx >= 0 else 0)
        self.tz_box.currentIndexChanged.connect(self._on_tz)
        root.addWidget(self.tz_box)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)
        self._tick()
        self.apply_theme()

    def _tz(self):
        return ZoneInfo(self._tzname) if self._tzname else None

    def _on_tz(self, i: int):
        self._tzname = self.tz_box.itemData(i) or ""
        db.set_setting("ui_timezone", self._tzname)
        self._tick()

    def _tick(self):
        tz = self._tz()
        now = datetime.now(tz) if tz else datetime.now()
        self.date_label.setText(now.strftime(_date_format(self._tzname)).upper())
        self.time_label.setText(now.strftime("%I:%M").lstrip("0"))
        self.sec_label.setText(now.strftime("%S"))
        self.ampm_label.setText(now.strftime("%p"))
        self.day_label.setText(f"DAY\n{int(now.strftime('%j'))}")
        self.week_label.setText(f"WEEK\n{int(now.strftime('%V'))}")

    def set_compact(self, compact: bool):
        if compact == self._compact:
            return
        self._compact = compact
        for i in range(self._info_row.count()):
            w = self._info_row.itemAt(i).widget()
            if w:
                w.setVisible(not compact)
        self.tz_box.setVisible(not compact)
        self.apply_theme()

    def apply_theme(self):
        T = theme.current()
        ts = 22 if self._compact else 34
        w = 210 if self._compact else 260
        self.setStyleSheet(
            f"QFrame#clockbox {{ background: rgba(8,5,16,0.88);"
            f" border: 1px solid {T['accent']}; border-radius: 8px; }}"
            f"QLabel#clocktime {{ color: {T['title']}; font-size: {ts}px; font-weight: 700; }}"
            f"QLabel#clocksec {{ color: {T['accent_light']}; font-size: 13px; font-weight: 600; }}"
            f"QLabel#clockampm {{ color: {T['accent']}; font-size: 10px; font-weight: 700; }}"
            f"QLabel#clockdate {{ color: {T['title']}; font-size: 11px; font-weight: 600; }}"
            f"QLabel#clocksync {{ color: {T['accent_light']}; font-size: 9px; }}"
            f"QLabel#clockmeta {{ color: {T['subtitle']}; font-size: 9px; }}"
            f"QComboBox {{ background: rgba(20,12,38,0.9); color: {T['title']};"
            f" border: 1px solid {T['header_border']}; padding: 3px 8px; font-size: 11px; }}"
            f"QComboBox QAbstractItemView {{ background: #120a24; color: {T['title']};"
            f" selection-background-color: {T['accent']}; }}"
        )
        self.setFixedWidth(w)
        self.adjustSize()
