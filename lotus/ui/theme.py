"""Lotus visual theme — deep purple, Matrix accents, clean panels."""

APP_STYLESHEET = """
QWidget {
    color: #ece5ff;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog {
    background: #080512;
}
QFrame#header {
    background: rgba(20, 12, 38, 190);
    border-bottom: 1px solid #3b2168;
}
QLabel#title {
    color: #e9d5ff;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#subtitle {
    color: #a78bfa;
    font-size: 11px;
}
QPushButton {
    background: #241243;
    border: 1px solid #55308f;
    border-radius: 8px;
    color: #eadcff;
    padding: 7px 12px;
}
QPushButton:hover {
    background: #34205f;
    border-color: #8b5cf6;
}
QPushButton:disabled {
    color: #6f6390;
    background: #1a1030;
    border-color: #352450;
}
QPushButton#sendButton {
    background: #7c3aed;
    border-color: #a78bfa;
    font-weight: 700;
}
QPushButton#sendButton:hover {
    background: #8b5cf6;
}
QPushButton#dangerButton {
    background: #4c1d95;
    border-color: #7c3aed;
}
QPushButton#navButton {
    background: #160d2c;
    border: 1px solid #3b2168;
    border-radius: 10px;
    color: #cbb7ff;
    padding: 10px 12px;
    text-align: left;
    font-weight: 600;
}
QPushButton#navButton:hover {
    background: #241243;
    border-color: #7c3aed;
    color: #f3edff;
}
QPushButton#navButton:checked {
    background: #2d1a55;
    border-color: #a78bfa;
    color: #f5efff;
}
QLineEdit, QTextEdit, QPlainTextEdit, QTextBrowser, QComboBox {
    background: #130b24;
    border: 1px solid #43257a;
    border-radius: 8px;
    color: #f3edff;
    selection-background-color: #7c3aed;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QTextBrowser:focus, QComboBox:focus {
    border: 1px solid #a78bfa;
}
QTextBrowser, QTextEdit, QPlainTextEdit {
    padding: 8px;
}
QComboBox QAbstractItemView {
    background: #130b24;
    border: 1px solid #55308f;
    selection-background-color: #7c3aed;
}
QFrame#panel {
    background: rgba(23, 13, 43, 225);
    border: 1px solid #4c2a7d;
    border-radius: 14px;
}
QLabel#section {
    color: #c4b5fd;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 1px;
}
QLabel#status {
    color: #ddd0ff;
    font-weight: 600;
}
QLabel#error {
    color: #fda4af;
}
QTableWidget {
    background: #100a20;
    alternate-background-color: #17102e;
    border: 1px solid #3f2568;
    border-radius: 8px;
    gridline-color: #2c1b4b;
}
QHeaderView::section {
    background: #241243;
    color: #d8c7ff;
    border: none;
    padding: 5px;
}
QTabWidget::pane {
    border: 1px solid #3f2568;
    border-radius: 8px;
    background: #100a20;
}
QTabBar::tab {
    background: #1c1038;
    color: #bda9ee;
    padding: 6px 10px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}
QTabBar::tab:selected {
    background: #2d1a55;
    color: #f3edff;
}
QScrollBar:vertical {
    background: #0d0718;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #5b3aa0;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #0d0718;
    height: 10px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #5b3aa0;
    border-radius: 5px;
}
QMessageBox {
    background: #130b24;
}
QMessageBox QLabel {
    color: #ece5ff;
}
"""
