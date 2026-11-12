"""Lotus visual theme — dark base with instantly switchable accent palettes."""
from __future__ import annotations

from string import Template

THEME_NAMES = ("purple", "blue", "red", "pink", "green", "orange")
DEFAULT_THEME = "purple"

# Each palette recolors every tinted surface so switching feels native, not
# just a re-tinted button. Keys feed both the stylesheet template and the
# painted widgets (Matrix rain / reactor).
PALETTES: dict[str, dict[str, str]] = {
    "purple": {
        "window": "#080512", "header_bg": "rgba(20, 12, 38, 190)",
        "header_border": "#3b2168", "title": "#e9d5ff", "subtitle": "#a78bfa",
        "btn_bg": "#241243", "btn_border": "#55308f", "btn_hover_bg": "#34205f",
        "btn_hover_border": "#8b5cf6",
        "disabled_text": "#6f6390", "disabled_bg": "#1a1030", "disabled_border": "#352450",
        "accent": "#7c3aed", "accent_hover": "#8b5cf6", "accent_light": "#a78bfa",
        "danger_bg": "#4c1d95",
        "nav_bg": "#160d2c", "nav_text": "#cbb7ff", "nav_checked_bg": "#2d1a55",
        "input_bg": "#130b24", "input_border": "#43257a", "selection": "#7c3aed",
        "panel_bg": "rgba(23, 13, 43, 225)", "panel_border": "#4c2a7d",
        "section": "#c4b5fd", "status_text": "#ddd0ff",
        "table_bg": "#100a20", "table_alt": "#17102e", "table_border": "#3f2568",
        "gridline": "#2c1b4b", "headerview_text": "#d8c7ff",
        "tab_bg": "#1c1038", "tab_text": "#bda9ee", "tab_selected_bg": "#2d1a55",
        "scroll_bg": "#0d0718", "scroll_handle": "#5b3aa0",
        "rain": "#a855f7", "ring1": "#a855f7", "ring2": "#c48dff",
        "ring3": "#7c3aed", "ring4": "#d8b4fe",
        "glow1": "#8b5cf6", "glow2": "#581c87",
        "core1": "#e9d5ff", "core2": "#a855f7", "core3": "#4c1d95",
    },
    "blue": {
        "window": "#050b14", "header_bg": "rgba(8, 18, 38, 190)",
        "header_border": "#1e3a5f", "title": "#dbeafe", "subtitle": "#60a5fa",
        "btn_bg": "#0f2547", "btn_border": "#1d4e89", "btn_hover_bg": "#163a66",
        "btn_hover_border": "#3b82f6",
        "disabled_text": "#64748b", "disabled_bg": "#0c1a30", "disabled_border": "#1e3350",
        "accent": "#2563eb", "accent_hover": "#3b82f6", "accent_light": "#60a5fa",
        "danger_bg": "#1e3a8a",
        "nav_bg": "#0a1730", "nav_text": "#bfd4ff", "nav_checked_bg": "#12285a",
        "input_bg": "#0a1626", "input_border": "#1e3f70", "selection": "#2563eb",
        "panel_bg": "rgba(10, 20, 43, 225)", "panel_border": "#1d4275",
        "section": "#93c5fd", "status_text": "#d7e6ff",
        "table_bg": "#081226", "table_alt": "#0e1c36", "table_border": "#1c3960",
        "gridline": "#152647", "headerview_text": "#c7dbff",
        "tab_bg": "#101c3a", "tab_text": "#a9c2ef", "tab_selected_bg": "#12285a",
        "scroll_bg": "#070d18", "scroll_handle": "#2f5aa8",
        "rain": "#3b82f6", "ring1": "#3b82f6", "ring2": "#93c5fd",
        "ring3": "#2563eb", "ring4": "#bfdbfe",
        "glow1": "#3b82f6", "glow2": "#1e3a8a",
        "core1": "#dbeafe", "core2": "#3b82f6", "core3": "#1e3a8a",
    },
    "red": {
        "window": "#140505", "header_bg": "rgba(38, 10, 10, 190)",
        "header_border": "#5f1e1e", "title": "#fee2e2", "subtitle": "#f87171",
        "btn_bg": "#471010", "btn_border": "#8a2a2a", "btn_hover_bg": "#662222",
        "btn_hover_border": "#ef4444",
        "disabled_text": "#8b6464", "disabled_bg": "#2c0d0d", "disabled_border": "#502020",
        "accent": "#dc2626", "accent_hover": "#ef4444", "accent_light": "#f87171",
        "danger_bg": "#7f1d1d",
        "nav_bg": "#2c0a0a", "nav_text": "#ffc9c9", "nav_checked_bg": "#5a1616",
        "input_bg": "#260a0a", "input_border": "#6e1f1f", "selection": "#dc2626",
        "panel_bg": "rgba(43, 13, 13, 225)", "panel_border": "#752626",
        "section": "#fca5a5", "status_text": "#ffe1e1",
        "table_bg": "#260808", "table_alt": "#361010", "table_border": "#5e2020",
        "gridline": "#471515", "headerview_text": "#ffc7c7",
        "tab_bg": "#381010", "tab_text": "#efa9a9", "tab_selected_bg": "#5a1616",
        "scroll_bg": "#180707", "scroll_handle": "#a83232",
        "rain": "#ef4444", "ring1": "#ef4444", "ring2": "#fca5a5",
        "ring3": "#dc2626", "ring4": "#fecaca",
        "glow1": "#ef4444", "glow2": "#7f1d1d",
        "core1": "#fee2e2", "core2": "#ef4444", "core3": "#7f1d1d",
    },
    "pink": {
        "window": "#140510", "header_bg": "rgba(38, 10, 30, 190)",
        "header_border": "#5f1e4a", "title": "#fce7f3", "subtitle": "#f472b6",
        "btn_bg": "#47102f", "btn_border": "#8a2a5e", "btn_hover_bg": "#662244",
        "btn_hover_border": "#ec4899",
        "disabled_text": "#8b6478", "disabled_bg": "#2c0d1e", "disabled_border": "#502038",
        "accent": "#db2777", "accent_hover": "#ec4899", "accent_light": "#f472b6",
        "danger_bg": "#831843",
        "nav_bg": "#2c0a1e", "nav_text": "#ffc9e3", "nav_checked_bg": "#5a1639",
        "input_bg": "#260a1a", "input_border": "#6e1f4a", "selection": "#db2777",
        "panel_bg": "rgba(43, 13, 32, 225)", "panel_border": "#752655",
        "section": "#f9a8d4", "status_text": "#ffe1f0",
        "table_bg": "#260818", "table_alt": "#361024", "table_border": "#5e2040",
        "gridline": "#47152f", "headerview_text": "#ffc7e0",
        "tab_bg": "#381024", "tab_text": "#efa9cd", "tab_selected_bg": "#5a1639",
        "scroll_bg": "#180711", "scroll_handle": "#a83268",
        "rain": "#ec4899", "ring1": "#ec4899", "ring2": "#f9a8d4",
        "ring3": "#db2777", "ring4": "#fbcfe8",
        "glow1": "#ec4899", "glow2": "#831843",
        "core1": "#fce7f3", "core2": "#ec4899", "core3": "#831843",
    },
    "green": {
        "window": "#04140c", "header_bg": "rgba(8, 30, 20, 190)",
        "header_border": "#1e5f42", "title": "#d1fae5", "subtitle": "#34d399",
        "btn_bg": "#0f4730", "btn_border": "#1d8a5e", "btn_hover_bg": "#16663f",
        "btn_hover_border": "#10b981",
        "disabled_text": "#648b78", "disabled_bg": "#0d2c1e", "disabled_border": "#20503a",
        "accent": "#059669", "accent_hover": "#10b981", "accent_light": "#34d399",
        "danger_bg": "#065f46",
        "nav_bg": "#0a2c1e", "nav_text": "#c9ffe3", "nav_checked_bg": "#155a3a",
        "input_bg": "#0a2618", "input_border": "#1f6e4a", "selection": "#059669",
        "panel_bg": "rgba(13, 43, 30, 225)", "panel_border": "#26754f",
        "section": "#6ee7b7", "status_text": "#e1fff0",
        "table_bg": "#082614", "table_alt": "#0e3620", "table_border": "#205e3e",
        "gridline": "#15472c", "headerview_text": "#c7ffd9",
        "tab_bg": "#103820", "tab_text": "#a9efc4", "tab_selected_bg": "#155a3a",
        "scroll_bg": "#07180f", "scroll_handle": "#32a86a",
        "rain": "#10b981", "ring1": "#10b981", "ring2": "#6ee7b7",
        "ring3": "#059669", "ring4": "#a7f3d0",
        "glow1": "#10b981", "glow2": "#065f46",
        "core1": "#d1fae5", "core2": "#10b981", "core3": "#065f46",
    },
    "orange": {
        "window": "#140a05", "header_bg": "rgba(38, 20, 10, 190)",
        "header_border": "#5f3a1e", "title": "#ffedd5", "subtitle": "#fb923c",
        "btn_bg": "#472410", "btn_border": "#8a4a2a", "btn_hover_bg": "#663a22",
        "btn_hover_border": "#f97316",
        "disabled_text": "#8b7464", "disabled_bg": "#2c1a0d", "disabled_border": "#503020",
        "accent": "#ea580c", "accent_hover": "#f97316", "accent_light": "#fb923c",
        "danger_bg": "#7f2d0f",
        "nav_bg": "#2c150a", "nav_text": "#ffd9b8", "nav_checked_bg": "#5a2e16",
        "input_bg": "#26150a", "input_border": "#6e3a1f", "selection": "#ea580c",
        "panel_bg": "rgba(43, 25, 13, 225)", "panel_border": "#75492a",
        "section": "#fdba74", "status_text": "#ffe8d1",
        "table_bg": "#261408", "table_alt": "#361e10", "table_border": "#5e3a20",
        "gridline": "#47301a", "headerview_text": "#ffd0a0",
        "tab_bg": "#381e10", "tab_text": "#efb98a", "tab_selected_bg": "#5a2e16",
        "scroll_bg": "#180f07", "scroll_handle": "#a86a32",
        "rain": "#f97316", "ring1": "#f97316", "ring2": "#fdba74",
        "ring3": "#ea580c", "ring4": "#fed7aa",
        "glow1": "#f97316", "glow2": "#7f2d0f",
        "core1": "#ffedd5", "core2": "#f97316", "core3": "#7f2d0f",
    },
}

_CURRENT = DEFAULT_THEME


def current_name() -> str:
    return _CURRENT


def current() -> dict[str, str]:
    return PALETTES[_CURRENT]


def set_current(name: str) -> str:
    global _CURRENT
    _CURRENT = name if name in PALETTES else DEFAULT_THEME
    return _CURRENT


_TEMPLATE = Template("""
QWidget {
    color: #ece5ff;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background: $window;
}
QFrame#header {
    background: $header_bg;
    border-bottom: 1px solid $header_border;
}
QLabel#title {
    color: $title;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#subtitle {
    color: $subtitle;
    font-size: 11px;
}
QLabel#version {
    color: $subtitle;
    font-size: 12px;
}
QPushButton {
    background: $btn_bg;
    border: 1px solid $btn_border;
    border-radius: 8px;
    color: #eadcff;
    padding: 7px 12px;
}
QPushButton:hover {
    background: $btn_hover_bg;
    border-color: $btn_hover_border;
}
QPushButton:disabled {
    color: $disabled_text;
    background: $disabled_bg;
    border-color: $disabled_border;
}
QPushButton#sendButton {
    background: $accent;
    border-color: $accent_light;
    font-weight: 700;
}
QPushButton#sendButton:hover {
    background: $accent_hover;
}
QPushButton#dangerButton {
    background: $danger_bg;
    border-color: $accent;
}
QPushButton#navButton {
    background: $nav_bg;
    border: 1px solid $header_border;
    border-radius: 10px;
    color: $nav_text;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
}
QPushButton#navButton:hover {
    background: $btn_bg;
    border-color: $accent;
    color: #f3edff;
}
QPushButton#navButton:checked {
    background: $nav_checked_bg;
    border-color: $accent_light;
    color: #f5efff;
}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox {
    background: $input_bg;
    border: 1px solid $input_border;
    border-radius: 8px;
    color: #f3edff;
    selection-background-color: $selection;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus, QComboBox:focus {
    border: 1px solid $accent_light;
}
QTextBrowser, QTextEdit, QPlainTextEdit {
    padding: 8px;
}
QComboBox QAbstractItemView {
    background: $input_bg;
    border: 1px solid $btn_border;
    selection-background-color: $selection;
}
QFrame#panel {
    background: $panel_bg;
    border: 1px solid $panel_border;
    border-radius: 14px;
}
QLabel#section {
    color: $section;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 1px;
}
QLabel#status {
    color: $status_text;
    font-weight: 600;
}
QLabel#error {
    color: #fda4af;
}
QTableWidget {
    background: $table_bg;
    alternate-background-color: $table_alt;
    border: 1px solid $table_border;
    border-radius: 8px;
    gridline-color: $gridline;
}
QHeaderView::section {
    background: $btn_bg;
    color: $headerview_text;
    border: none;
    padding: 5px;
}
QTabWidget::pane {
    border: 1px solid $table_border;
    border-radius: 8px;
    background: $table_bg;
}
QTabBar::tab {
    background: $tab_bg;
    color: $tab_text;
    padding: 6px 10px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    background: $tab_selected_bg;
    color: #f3edff;
}
QScrollBar:vertical {
    background: $scroll_bg;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: $scroll_handle;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: $scroll_bg;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: $scroll_handle;
    border-radius: 5px;
}
QMessageBox {
    background: $input_bg;
}
QMessageBox QLabel {
    color: #ece5ff;
}
QProgressBar {
    background: $input_bg;
    border: 1px solid $input_border;
    border-radius: 8px;
    text-align: center;
    color: #f3edff;
    min-height: 14px;
}
QProgressBar::chunk {
    background: $accent;
    border-radius: 6px;
}
QCheckBox {
    color: #ece5ff;
    spacing: 8px;
}
""")


def stylesheet(name: str | None = None) -> str:
    """Build the app stylesheet for a palette (defaults to current)."""
    if name is not None:
        set_current(name)
    return _TEMPLATE.substitute(PALETTES[_CURRENT])


APP_STYLESHEET = stylesheet(DEFAULT_THEME)
