"""Main Lotus desktop window: reactor, Matrix rain, chat, logs, scanner, updater."""
from __future__ import annotations

import html
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

import psutil
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QStandardPaths, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QLabel, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QScrollBar, QSlider, QStackedWidget, QTableWidget,
    QFileDialog, QTableWidgetItem, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from .. import __version__, ai, audit, changelog, config, db, devbox, github, personality, platform_info, privacy, scanner, updater, usage
from .orbnav import OrbNav
from .clockbox import ClockBox
from . import theme
from .settings_dialog import SettingsDialog
from .widgets import MatrixRain, ReactorWidget


class DragBar(QFrame):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window()._begin_drag(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.window()._drag_move(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.window()._end_drag()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()
        super().mouseDoubleClickEvent(event)


class ChatInput(QTextEdit):
    """Multi-line ask box that grows with what you type — Enter sends,
    Shift+Enter inserts a newline, tall messages get a scrollbar."""
    submitted = pyqtSignal()
    _MIN_H, _MAX_H = 40, 170

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)
        self.setPlaceholderText("Ask a question…  (Enter to send — Shift+Enter for a new line)")
        self.textChanged.connect(self._fit_to_content)
        self._fit_to_content()

    def _fit_to_content(self):
        doc_h = self.document().size().height()
        self.setFixedHeight(int(max(self._MIN_H, min(doc_h + 18, self._MAX_H))))

    def keyPressEvent(self, event):
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lotus")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(1360, 800)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(theme.stylesheet(config.get_setting("ui_theme") or theme.DEFAULT_THEME))
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "lotus.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self._ensure_desktop_shortcut()

        self._jobs: list[tuple[queue.Queue, object, object]] = []
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_jobs)
        self._poll_timer.start(100)

        self._drag_offset = None
        self._update_info = None
        self._pending_os_question = ""
        # Status label lives off-layout in orb-nav mode; _build_center re-binds
        # it to the visible reactor panel if the old layout is ever restored.
        self.center_status = QLabel("Lotus online — cybersecurity mode")

        self._build_ui()
        self.refresh_logs()
        self.refresh_memories()
        QTimer.singleShot(800, self._check_update)
        QTimer.singleShot(1200, self.refresh_devbox)

    def _ensure_desktop_shortcut(self):
        if sys.platform != "win32" or not getattr(sys, "frozen", False):
            return
        desktop = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation))
        link = desktop / "Lotus Beta.lnk"
        if link.exists():
            return
        exe = Path(sys.executable)
        base = config.BASE_DIR

        def psq(path: Path) -> str:
            return str(path).replace("'", "''")

        command = (
            "$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{psq(link)}'); "
            f"$s.TargetPath = '{psq(exe)}'; "
            f"$s.WorkingDirectory = '{psq(base)}'; "
            f"$s.IconLocation = '{psq(exe)},0'; "
            "$s.Description = 'Lotus Cybersecurity AI'; "
            "$s.Save()"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
        if result.returncode == 0 and link.exists():
            db.log("info", "desktop", "created desktop shortcut")

    # ── Background jobs ─────────────────────────────────────────────────────
    def _run_bg(self, fn, on_ok=None, on_err=None):
        q: queue.Queue = queue.Queue(maxsize=1)
        self._jobs.append((q, on_ok, on_err))

        def worker():
            try:
                q.put((True, fn()))
            except Exception as exc:  # noqa: BLE001 - surfaced to UI
                q.put((False, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_jobs(self):
        self._drain_chunks()
        remaining = []
        for q, on_ok, on_err in self._jobs:
            try:
                ok, value = q.get_nowait()
            except queue.Empty:
                remaining.append((q, on_ok, on_err))
                continue
            try:
                if ok:
                    if on_ok:
                        on_ok(value)
                elif on_err:
                    on_err(value)
                else:
                    self._show_error(value)
            except Exception as exc:  # noqa: BLE001
                self._show_error(exc)
        self._jobs = remaining

    def _drain_chunks(self):
        chunks_q = getattr(self, "_chunks", None)
        if chunks_q is None:
            return
        while True:
            try:
                piece = chunks_q.get_nowait()
            except queue.Empty:
                break
            if not self._streamed:
                accent = html.escape(theme.current()["section"])
                self.chat_view.append(
                    f"<div class='msg' style='margin:8px 0;'><b style='color:{accent}'>Lotus:</b></div>"
                )
                self.chat_view.moveCursor(self.chat_view.textCursor().MoveOperation.End)
                self._streamed = True
                self.thinking_label.hide()
                self._set_chat_status("Lotus is typing…")
            self.chat_view.insertPlainText(piece)
            bar = self.chat_view.verticalScrollBar()
            bar.setValue(bar.maximum())

    def _show_error(self, exc: Exception):
        message = str(exc) or exc.__class__.__name__
        db.log("error", "ui", message)
        QMessageBox.critical(self, "Lotus error", message)

    # ── UI construction ─────────────────────────────────────────────────────
    def _build_ui(self):
        self.canvas = MatrixRain()
        self.setCentralWidget(self.canvas)
        root = QVBoxLayout(self.canvas)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = DragBar()
        self.header.setObjectName("header")
        self.header.setFixedHeight(46)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(16, 0, 12, 0)
        header_layout.setSpacing(10)

        title_box = QWidget()
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title = QLabel("◈ LOTUS")
        title.setObjectName("title")
        subtitle = QLabel("CYBERSECURITY AI")
        subtitle.setObjectName("subtitle")
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addWidget(title_box)
        header_layout.addStretch(1)
        self._header_title = title_box

        self.update_button = QPushButton("Check for updates")
        self.update_button.clicked.connect(self._check_update_now)
        header_layout.addWidget(self.update_button)

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self._open_settings)
        header_layout.addWidget(settings_button)

        minimize = QPushButton("—")
        minimize.setFixedWidth(42)
        minimize.clicked.connect(self.showMinimized)
        header_layout.addWidget(minimize)
        full = QPushButton("⛶")
        full.setFixedWidth(42)
        full.setToolTip("Full screen")
        full.clicked.connect(self._toggle_fullscreen)
        header_layout.addWidget(full)
        close = QPushButton("×")
        close.setFixedWidth(42)
        close.clicked.connect(self.close)
        header_layout.addWidget(close)
        root.addWidget(self.header)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(14)
        root.addWidget(content, 1)

        self.left_panel = self._build_left_panel()
        content_layout.addWidget(self.left_panel, 1)
        # --- REACTOR PANEL REMOVED FOR ORB-NAV TEST (kept for revert):
        # content_layout.addWidget(self._build_center(), 1) ---
        self.clock_box = ClockBox(self.canvas)
        self.clock_box.show()
        self.version_label = QLabel(f"v{__version__}", self.canvas)
        self.version_label.setStyleSheet(
            f"color: {theme.current()['subtitle']}; font-size: 10px;")
        self.version_label.show()
        QTimer.singleShot(0, self._position_clock)

    def _position_clock(self):
        if not hasattr(self, "clock_box"):
            return
        x = self.canvas.width() - self.clock_box.width() - 8
        self.clock_box.move(max(x, 8), self.header.height() + 8)
        self.clock_box.raise_()
        if hasattr(self, "version_label"):
            self.version_label.adjustSize()
            self.version_label.move(
                self.canvas.width() - self.version_label.width() - 8,
                self.canvas.height() - self.version_label.height() - 8)
            self.version_label.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_clock()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("")  # transparent - orb nav floats over the Matrix bg
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        nav = QFrame()
        nav.setFixedWidth(150)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        self.section_stack = QStackedWidget()
        self._section_pages = {}
        self._section_buttons = {}

        self._register_section("ask", "Ask Lotus", self._build_ask_page(), nav_layout)
        self._register_section("logs", "Logs / Memory", self._build_logs_page(), nav_layout)
        self._register_section("scan", "File / Repo Scan", self._build_scan_page(), nav_layout)
        self._register_section("devbox", "Devbox", self._build_devbox_page(), nav_layout)
        self._register_section("audit", "Project Audit", self._build_audit_page(), nav_layout)
        self._register_section("privacy", "Privacy Sweep", self._build_privacy_page(), nav_layout)
        self._register_section("personality", "Personality", self._build_personality_page(), nav_layout)
        self._register_section("patchnotes", "Patch Notes", self._build_patchnotes_page(), nav_layout)
        nav_layout.addStretch(1)

        # --- OLD LEFT-PANEL NAV (kept for revert): layout.addWidget(nav) ---
        self._legacy_nav = nav  # keep the old nav alive for revert
        self.orb_nav = OrbNav()
        self.orb_nav.set_sections(
            [(k, b.text()) for k, b in self._section_buttons.items()])
        self.orb_nav.section_selected.connect(self._show_section)

        # Centered LOTUS title for orb-menu mode (hidden when a panel is open)
        self._menu_title = QWidget()
        mt = QVBoxLayout(self._menu_title)
        mt.setContentsMargins(0, 0, 0, 0)
        mt.setSpacing(2)
        mt_title = QLabel("◈  L O T U S")
        mt_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mt_title.setStyleSheet("font-size: 34px; font-weight: 700; letter-spacing: 6px;")
        mt_sub = QLabel("C Y B E R S E C U R I T Y   A I")
        mt_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mt_sub.setStyleSheet("font-size: 12px; letter-spacing: 4px; color: #8b7fb0;")
        mt.addWidget(mt_title)
        mt.addWidget(mt_sub)

        self._section_col = QVBoxLayout()
        self._section_col.setContentsMargins(0, 0, 0, 0)
        self._section_col.setSpacing(6)
        self._section_col.addWidget(self._menu_title)
        self._section_col.addStretch(1)
        self._section_col.addWidget(self.orb_nav)
        self._section_col.addStretch(1)
        self._section_col.addWidget(self.section_stack, 3)
        layout.addLayout(self._section_col, 1)

        self._refresh_scan_targets()
        self._on_scan_mode_changed()
        # ORB MENU MODE: orbs dead-center, no panel shown until one is clicked
        self._open_section = None
        self.section_stack.hide()
        self._header_title.hide()
        return panel

    def _register_section(self, key: str, title: str, page: QWidget, nav_layout: QVBoxLayout):
        button = QPushButton(title)
        button.setObjectName("navButton")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda checked=False, section_key=key: self._show_section(section_key))
        nav_layout.addWidget(button)
        self._section_pages[key] = self.section_stack.addWidget(page)
        self._section_buttons[key] = button

    def _show_section(self, key: str):
        if key not in self._section_pages:
            return
        if getattr(self, "_open_section", None) == key:
            self._open_section = None
            self.section_stack.hide()
            self._section_col.setStretch(1, 1)
            self._section_col.setStretch(3, 1)
            self._menu_title.show()
            self._header_title.hide()
            self.clock_box.set_compact(False)
            self._position_clock()
            for button in self._section_buttons.values():
                button.setChecked(False)
            return
        self._open_section = key
        for section_key, button in self._section_buttons.items():
            button.setChecked(section_key == key)
        self._section_col.setStretch(1, 0)
        self._section_col.setStretch(3, 0)
        self._menu_title.hide()
        self._header_title.show()
        self.clock_box.set_compact(True)
        self._position_clock()
        self.section_stack.show()
        self.section_stack.setCurrentIndex(self._section_pages[key])
        if hasattr(self, "orb_nav"):
            self.orb_nav.set_active(key)

    def _build_ask_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.chat_view = QTextBrowser()
        self.chat_view.setOpenExternalLinks(True)
        self.chat_view.setMinimumHeight(240)
        layout.addWidget(self.chat_view, 1)

        self.thinking_label = QLabel("Lotus is thinking…")
        self.thinking_label.setStyleSheet("color: #c4b5fd; font-style: italic;")
        self.thinking_label.hide()
        layout.addWidget(self.thinking_label)

        ask_row = QHBoxLayout()
        self.ask_input = ChatInput()
        self.ask_input.submitted.connect(self._send_question)
        send = QPushButton("Send")
        send.setObjectName("sendButton")
        send.clicked.connect(self._send_question)
        ask_row.addWidget(self.ask_input, 1)
        ask_row.addWidget(send, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(ask_row)
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("View:"))
        self.log_view = QComboBox()
        self.log_view.addItem("Activity", "logs")
        self.log_view.addItem("My usage", "usage")
        if usage.is_dev_build():
            self.log_view.addItem("Global minutes", "global")
        self.log_view.currentIndexChanged.connect(self._on_log_view)
        view_row.addWidget(self.log_view)
        view_row.addStretch(1)
        layout.addLayout(view_row)

        self.log_tabs = QTabWidget()
        self.logs_table = self._make_table(["Time", "Level", "Source", "Message"])
        self.requests_table = self._make_table(["Time", "Model", "Search", "Prompt", "Response"])
        self.memory_table = self._make_table(["Category", "Key", "Value"])
        self.log_tabs.addTab(self.logs_table, "Activity")
        self.log_tabs.addTab(self.requests_table, "Requests")
        self.log_tabs.addTab(self.memory_table, "Memory")
        self.log_tabs.setMinimumHeight(160)
        layout.addWidget(self.log_tabs, 1)

        self.usage_view = QTextBrowser()
        self.usage_view.hide()
        layout.addWidget(self.usage_view, 1)

        log_buttons = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_logs)
        clear = QPushButton("Clear activity")
        clear.setObjectName("dangerButton")
        clear.clicked.connect(self._clear_logs)
        log_buttons.addWidget(refresh)
        log_buttons.addWidget(clear)
        log_buttons.addStretch(1)
        layout.addLayout(log_buttons)
        return page

    def _on_log_view(self, _i: int):
        mode = self.log_view.currentData()
        show_logs = mode == "logs"
        self.log_tabs.setVisible(show_logs)
        self.usage_view.setVisible(not show_logs)
        if not show_logs:
            self._refresh_usage_view()

    def _refresh_usage_view(self):
        if not hasattr(self, "usage_view") or not self.usage_view.isVisible():
            return
        if self.log_view.currentData() == "global":
            rows = usage.global_rollup()
            parts = ["<b>Global minutes — all installs on this machine</b><br><br>"]
            if not rows:
                parts.append("<i>No installs reporting yet.</i>")
            for r in rows:
                parts.append(
                    f"<div style='margin:6px 0;'><b>{html.escape(r['install'])}</b> "
                    f"(install <i>{html.escape(r['id'])}</i>)<br>"
                    f"&nbsp;&nbsp;tokens: {r['tokens']:,.0f} &nbsp;·&nbsp; "
                    f"VM minutes: {r['vm_minutes']:,.1f}</div>")
            tt = sum(r["tokens"] for r in rows)
            tv = sum(r["vm_minutes"] for r in rows)
            parts.append(f"<br><b>Totals — tokens: {tt:,.0f} · VM minutes: {tv:,.1f}</b>")
            self.usage_view.setHtml("".join(parts))
        else:
            s = usage.summary()
            def fmt(p):
                return f"tokens <b>{p['tokens']:,.0f}</b> · VM <b>{p['vm_minutes']:,.1f}</b> min"
            self.usage_view.setHtml(
                f"<b>My usage</b> <i>(install {html.escape(s['install_id'])})</i><br><br>"
                f"Today:&nbsp;&nbsp;{fmt(s['today'])}<br>"
                f"This month:&nbsp;&nbsp;{fmt(s['month'])}<br>"
                f"All time:&nbsp;&nbsp;{fmt(s['all_time'])}<br><br>"
                "<i>Counts Gemini tokens reported by the API and minutes the "
                "Lotus-Lab VM was running. Beta metering is display-only — "
                "nothing limits your usage.</i>")

    def _build_scan_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.scan_mode = QComboBox()
        self.scan_mode.addItem("Folder scan", "folder")
        self.scan_mode.addItem("GitHub repo scan", "github")
        self.scan_mode.currentIndexChanged.connect(self._on_scan_mode_changed)
        layout.addWidget(self.scan_mode)

        self.scan_target_choice = QComboBox()
        self.scan_target_choice_widget = QWidget()
        target_choice_row = QHBoxLayout(self.scan_target_choice_widget)
        target_choice_row.setContentsMargins(0, 0, 0, 0)
        target_choice_row.addWidget(self.scan_target_choice, 1)
        refresh_targets = QPushButton("Refresh drives")
        refresh_targets.clicked.connect(self._refresh_scan_targets)
        target_choice_row.addWidget(refresh_targets)
        layout.addWidget(self.scan_target_choice_widget)

        sched_row = QHBoxLayout()
        sched_row.addWidget(QLabel("Auto-scan:"))
        self.scan_schedule = QComboBox()
        for label, mins in (("Off", 0), ("Every 30 minutes", 30),
                            ("Every hour", 60), ("Every 2 hours", 120)):
            self.scan_schedule.addItem(label, mins)
        saved = int(db.get_setting("scan_interval_min", "0") or 0)
        for i in range(self.scan_schedule.count()):
            if self.scan_schedule.itemData(i) == saved:
                self.scan_schedule.setCurrentIndex(i)
        self.scan_schedule.currentIndexChanged.connect(self._apply_scan_schedule)
        sched_row.addWidget(self.scan_schedule, 1)
        sched_row.addStretch(1)
        layout.addLayout(sched_row)
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._scan_tick)
        self._apply_scan_schedule(self.scan_schedule.currentIndex())

        self.github_target = QLineEdit()
        self.github_target.setPlaceholderText("github.com/owner/repo")
        self.github_target.hide()
        layout.addWidget(self.github_target)

        scan_row = QHBoxLayout()
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self._run_scan)
        self.scan_details = QTextBrowser()
        self.scan_details.setMinimumHeight(120)
        scan_row.addWidget(self.scan_button)
        scan_row.addWidget(self.scan_details, 1)
        layout.addLayout(scan_row, 1)

        self.scan_status = QLabel("no viruses detected")
        self.scan_status.setObjectName("status")
        layout.addWidget(self.scan_status)
        return page

    def _apply_scan_schedule(self, _i: int):
        mins = int(self.scan_schedule.currentData() or 0)
        db.set_setting("scan_interval_min", str(mins))
        if not hasattr(self, "_scan_timer"):
            return
        self._scan_timer.stop()
        if mins > 0:
            self._scan_timer.start(mins * 60 * 1000)

    def _scan_tick(self):
        if self.scan_button.isEnabled():
            self._run_scan()

    def _build_devbox_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.devbox_status = QTextBrowser()
        self.devbox_status.setMaximumHeight(150)
        self.devbox_status.setHtml("<i>Refresh to check the Lotus-Lab VM.</i>")
        layout.addWidget(self.devbox_status)

        buttons = QHBoxLayout()
        for label, fn in (
            ("Refresh", self.refresh_devbox),
            ("Boot VM", lambda: self._devbox_action(devbox.ensure_running)),
            ("Sync source", lambda: self._devbox_action(devbox.sync)),
            ("Run checks", lambda: self._devbox_action(devbox.test)),
            ("Revert to clean", lambda: self._devbox_action(devbox.revert)),
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda checked=False, f=fn: f())
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.experiments_table = self._make_table(["Time", "Kind", "Result", "Secs", "Goal"])
        layout.addWidget(self.experiments_table, 1)
        return page

    def _launch_gate(self, title: str, desc: str) -> QWidget:
        """Teaser page for Pro features in beta - 'Available at launch'
        plus what the feature does. Removed when Pro goes live."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_label(title))
        layout.addStretch(1)
        body = QLabel(f"{desc}\n\nAvailable at launch.")
        body.setObjectName("subtitle")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _build_audit_page(self) -> QWidget:
        if not audit.pro_enabled():
            return self._launch_gate(
                "Project Audit",
                "Audit real codebases, validate findings with AI, review "
                "proposed patches, and apply approved changes - all verified "
                "in Lotus's own lab before anything touches your project.")
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)
        layout.addWidget(self._section_label("Project Audit"))

        row = QHBoxLayout()
        pick = QPushButton("Choose project…")
        pick.clicked.connect(self._audit_pick)
        self.audit_path_label = QLabel("No project selected")
        self.audit_path_label.setObjectName("subtitle")
        self.audit_btn = QPushButton("Audit project")
        self.audit_btn.clicked.connect(self._run_audit)
        row.addWidget(pick)
        row.addWidget(self.audit_path_label, 1)
        row.addWidget(self.audit_btn)
        layout.addLayout(row)

        self.audit_table = QTableWidget(0, 4)
        self.audit_table.setHorizontalHeaderLabels(["Severity", "File", "Line", "Finding"])
        self.audit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.audit_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.audit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.audit_table, 1)

        mid = QHBoxLayout()
        self.patch_btn = QPushButton("Suggest patch")
        self.patch_btn.clicked.connect(self._suggest_patch)
        mid.addWidget(self.patch_btn)
        mid.addStretch(1)
        self.audit_status = QLabel("")
        self.audit_status.setObjectName("subtitle")
        mid.addWidget(self.audit_status)
        layout.addLayout(mid)

        self.patch_view = QTextEdit()
        self.patch_view.setReadOnly(True)
        self.patch_view.setPlaceholderText(
            "Select a finding and choose Suggest patch - the proposed diff appears here for review.")
        layout.addWidget(self.patch_view, 1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.apply_btn = QPushButton("Approve + apply")
        self.apply_btn.clicked.connect(self._apply_patch)
        reject = QPushButton("Reject")
        reject.clicked.connect(self.patch_view.clear)
        actions.addWidget(self.apply_btn)
        actions.addWidget(reject)
        layout.addLayout(actions)
        return page

    def _audit_pick(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose project folder", str(Path.home()))
        if folder:
            self._audit_path = Path(folder)
            self.audit_path_label.setText(folder)

    def _run_audit(self):
        path = getattr(self, "_audit_path", None)
        if not path:
            QMessageBox.information(self, "Project Audit", "Choose a project folder first.")
            return
        self.audit_status.setText("Auditing…")
        self._run_bg(lambda: audit.audit(path), on_ok=self._audit_done)

    def _audit_done(self, report: dict):
        self._audit_findings = report.get("audit_findings", [])
        self.audit_status.setText(
            f"{report['files_scanned']} files · {len(self._audit_findings)} findings")
        self.audit_table.setRowCount(len(self._audit_findings))
        for i, f in enumerate(self._audit_findings):
            for col, val in enumerate((f["severity"].upper(), f["file"],
                                       str(f.get("line") or ""), f["title"])):
                self.audit_table.setItem(i, col, QTableWidgetItem(val))

    def _suggest_patch(self):
        row = self.audit_table.currentRow()
        if row < 0 or not getattr(self, "_audit_findings", None):
            self.audit_status.setText("Select a finding first.")
            return
        finding = self._audit_findings[row]
        self.audit_status.setText("Drafting patch…")
        self._run_bg(lambda: audit.propose_patch(self._audit_path, finding),
                     on_ok=self._patch_ready)

    def _patch_ready(self, diff: str):
        self._patch_diff = diff
        self.patch_view.setPlainText(diff)
        self.audit_status.setText("Review the patch, then Approve or Reject.")

    def _apply_patch(self):
        diff = getattr(self, "_patch_diff", "")
        if not diff.strip():
            self.audit_status.setText("No patch to apply.")
            return
        try:
            files = audit.apply_diff(self._audit_path, diff)
            self.audit_status.setText(
                f"Applied {', '.join(files) or 'nothing'} - backup in .lotus-backup/")
            db.log("info", "audit", f"patch applied: {files}")
            self.patch_view.clear()
            self._patch_diff = ""
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)

    def _build_privacy_page(self) -> QWidget:
        if not audit.pro_enabled():
            return self._launch_gate(
                "Privacy Sweep",
                "Find where your email and phone have leaked or been sold, "
                "then Lotus drafts legal removal requests to data brokers on "
                "your behalf and tracks each opt-out until it is confirmed.")
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)
        layout.addWidget(self._section_label("Privacy Sweep"))

        row = QHBoxLayout()
        self.privacy_email = QLineEdit()
        self.privacy_email.setPlaceholderText("email@you.com")
        self.privacy_email.setText(db.get_setting("privacy_email"))
        self.privacy_name = QLineEdit()
        self.privacy_name.setPlaceholderText("Full name (for requests)")
        self.privacy_name.setText(db.get_setting("privacy_name"))
        self.privacy_phone = QLineEdit()
        self.privacy_phone.setPlaceholderText("Phone (optional)")
        self.privacy_phone.setText(db.get_setting("privacy_phone"))
        save = QPushButton("Save")
        save.clicked.connect(self._privacy_save)
        scan = QPushButton("Scan breaches")
        scan.clicked.connect(self._privacy_scan)
        row.addWidget(self.privacy_email, 2)
        row.addWidget(self.privacy_name, 2)
        row.addWidget(self.privacy_phone, 1)
        row.addWidget(save)
        row.addWidget(scan)
        layout.addLayout(row)

        self.privacy_results = QTextEdit()
        self.privacy_results.setReadOnly(True)
        self.privacy_results.setMaximumHeight(80)
        self.privacy_results.setPlaceholderText("Breach scan results appear here.")
        layout.addWidget(self.privacy_results)

        self.broker_table = QTableWidget(0, 3)
        self.broker_table.setHorizontalHeaderLabels(["Data broker", "Status", "Opt-out page"])
        self.broker_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.broker_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.broker_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.broker_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.broker_table, 1)
        self._privacy_reload_brokers()

        btns = QHBoxLayout()
        for label, fn in (("Draft removal email", self._privacy_draft),
                          ("Open opt-out page", self._privacy_optout),
                          ("Mark requested", lambda: self._privacy_mark("requested")),
                          ("Mark confirmed", lambda: self._privacy_mark("confirmed"))):
            b = QPushButton(label)
            b.clicked.connect(fn)
            btns.addWidget(b)
        btns.addStretch(1)
        self.privacy_status = QLabel("")
        self.privacy_status.setObjectName("subtitle")
        btns.addWidget(self.privacy_status)
        layout.addLayout(btns)
        return page

    def _privacy_reload_brokers(self):
        state = privacy.load_state()
        self.broker_table.setRowCount(len(privacy.BROKERS))
        for i, br in enumerate(privacy.BROKERS):
            self.broker_table.setItem(i, 0, QTableWidgetItem(br[0]))
            status = state.get(br[0], "not started").replace("_", " ")
            self.broker_table.setItem(i, 1, QTableWidgetItem(status))
            self.broker_table.setItem(i, 2, QTableWidgetItem(privacy.optout_url(br)))

    def _privacy_save(self):
        db.set_setting("privacy_email", self.privacy_email.text().strip())
        db.set_setting("privacy_name", self.privacy_name.text().strip())
        db.set_setting("privacy_phone", self.privacy_phone.text().strip())
        self.privacy_status.setText("Saved.")

    def _privacy_scan(self):
        email = self.privacy_email.text().strip()
        if not email:
            self.privacy_results.setPlainText("Enter an email address first.")
            return
        self._privacy_save()
        self.privacy_results.setPlainText("Scanning breach databases…")
        self._run_bg(lambda: privacy.breach_check(email), on_ok=self._privacy_scan_done)

    def _privacy_scan_done(self, res: dict):
        if "error" in res:
            self.privacy_results.setPlainText(f"Scan unavailable: {res['error']}")
            return
        breaches, pastes = res["breaches"], res["pastes"]
        if not breaches and not pastes:
            self.privacy_results.setPlainText("No known breaches or pastes for this email.")
        else:
            self.privacy_results.setPlainText(
                f"Found in {len(breaches)} breaches, {pastes} pastes.\n"
                + ", ".join(breaches[:40]))

    def _privacy_selected(self):
        row = self.broker_table.currentRow()
        if row < 0:
            self.privacy_status.setText("Select a broker row first.")
            return None
        return privacy.BROKERS[row]

    def _privacy_draft(self):
        br = self._privacy_selected()
        if not br:
            return
        self._privacy_save()
        QDesktopServices.openUrl(QUrl(privacy.removal_mailto(
            self.privacy_name.text(), self.privacy_email.text(),
            self.privacy_phone.text(), br)))

    def _privacy_optout(self):
        br = self._privacy_selected()
        if br:
            QDesktopServices.openUrl(QUrl(privacy.optout_url(br)))

    def _privacy_mark(self, status: str):
        br = self._privacy_selected()
        if not br:
            return
        privacy.mark(br[0], status)
        self._privacy_reload_brokers()
        self.privacy_status.setText(f"{br[0]}: {status.replace('_', ' ')}")

    def _build_personality_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)
        layout.addWidget(self._section_label("Personality"))

        info = QLabel(
            "Lotus adapts how it talks to you over time. See what it learned, "
            "tune it yourself, or reset it — every personality choice is yours. "
            "Security outputs (scans, alerts) always stay literal and professional.")
        info.setObjectName("subtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        arch_row = QHBoxLayout()
        arch_row.addWidget(QLabel("Starting style (optional):"))
        self._arch_combo = QComboBox()
        self._arch_combo.addItem("Custom / learned", "")
        for name in personality.ARCHETYPES:
            self._arch_combo.addItem(name.title(), name)
        arch_row.addWidget(self._arch_combo, 1)
        arch_btn = QPushButton("Apply")
        arch_btn.clicked.connect(self._apply_archetype)
        arch_row.addWidget(arch_btn)
        layout.addLayout(arch_row)

        self._trait_sliders = {}
        prof = personality.get()
        for t in personality.TRAITS:
            row = QHBoxLayout()
            row.addWidget(QLabel(t.replace("_", " ").title()))
            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(0, 100)
            s.setValue(int(prof["traits"].get(t, 0.5) * 100))
            s.valueChanged.connect(lambda v, n=t: personality.set_trait(n, v / 100.0))
            row.addWidget(s, 1)
            self._trait_sliders[t] = s
            layout.addLayout(row)

        layout.addWidget(QLabel("How should Lotus treat you?"))
        style_row = QHBoxLayout()
        self.style_note_input = QLineEdit()
        self.style_note_input.setPlaceholderText("e.g. keep it brief, no fluff, I like examples")
        style_row.addWidget(self.style_note_input, 1)
        note_btn = QPushButton("Save")
        note_btn.clicked.connect(self._save_style_note)
        style_row.addWidget(note_btn)
        analyze_btn = QPushButton("Analyze my style")
        analyze_btn.clicked.connect(self._analyze_style)
        style_row.addWidget(analyze_btn)
        layout.addLayout(style_row)

        hist_lbl = QLabel("What Lotus has learned")
        hist_lbl.setObjectName("section")
        layout.addWidget(hist_lbl)
        self.personality_hist = QTextBrowser()
        layout.addWidget(self.personality_hist, 1)

        reset = QPushButton("Reset to neutral")
        reset.clicked.connect(self._reset_personality)
        layout.addWidget(reset, 0, Qt.AlignmentFlag.AlignRight)
        self._refresh_personality()
        return page

    def _apply_archetype(self):
        name = self._arch_combo.currentData()
        if name and personality.apply_archetype(name):
            self._refresh_personality()

    def _save_style_note(self):
        if personality.analyze_style(self.style_note_input.text()):
            self.style_note_input.clear()

    def _analyze_style(self):
        self._run_bg(lambda: personality.synthesize(),
                     on_ok=lambda ok: self._refresh_personality())

    def _reset_personality(self):
        if QMessageBox.question(self, "Reset personality",
                                "Reset Lotus's learned personality to neutral defaults?") \
                == QMessageBox.StandardButton.Yes:
            personality.reset()
            self._refresh_personality()

    def _refresh_personality(self):
        prof = personality.get()
        for t, s in getattr(self, "_trait_sliders", {}).items():
            s.blockSignals(True)
            s.setValue(int(prof["traits"].get(t, 0.5) * 100))
            s.blockSignals(False)
        parts = []
        if prof["notes"]:
            parts.append(f"<b>Style notes:</b> {html.escape(prof['notes'])}")
        for h in personality.history(10):
            changes = ", ".join(f"{k.replace('_',' ')} {v:+.2f}" for k, v in h["deltas"].items()) or "—"
            parts.append(
                f"<div style='margin:4px 0;'><b>{html.escape(h['created'][:19])}</b> — "
                f"{html.escape(changes)}<br><i>{html.escape(h['reason'])}</i></div>")
        self.personality_hist.setHtml(
            "".join(parts) or "<i>Nothing learned yet — keep chatting.</i>")

    def _build_patchnotes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._section_label("Patch Notes"))
        view = QTextBrowser()
        parts = []
        for r in changelog.RELEASES:
            try:
                from datetime import datetime as _dt
                d = _dt.fromisoformat(r["date"]).strftime("%b %-d, %Y")
            except Exception:
                d = r["date"]
            items = "".join(f"<li>{html.escape(n)}</li>" for n in r["notes"])
            parts.append(
                f"<div style='margin-bottom:12px;'><b>v{html.escape(r['version'])}</b>"
                f" <i style='color:#a78bfa'>· {html.escape(d)}</i><ul>{items}</ul></div>")
        view.setHtml("".join(parts))
        layout.addWidget(view, 1)
        return page

    def _maybe_show_patchnotes(self):
        entry = changelog.unseen()
        if not entry:
            return
        changelog.mark_seen()
        items = "\n".join(f"• {n}" for n in entry["notes"])
        QMessageBox.information(
            self, f"Lotus updated to v{entry['version']}",
            f"What's new in this version:\n\n{items}\n\nSee Patch Notes for the full history.")

    def _make_table(self, columns: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    # ── Devbox (Lotus-Lab VM) ───────────────────────────────────────────────
    def refresh_devbox(self):
        self._run_bg(
            devbox.status,
            on_ok=self._on_devbox_status,
            on_err=lambda exc: self.devbox_status.setHtml(
                f"<span style='color:#fda4af'>{html.escape(str(exc))}</span>"),
        )
        self._refresh_experiments()

    def _on_devbox_status(self, st: dict):
        state = html.escape(str(st.get("vm_state", "?")))
        if st.get("mode") == "local":
            state = "local lab (host)"
        color = "#86efac" if st.get("vm_state") == "running" or st.get("mode") == "local" else "#f0abfc"
        lines = [
            f"<b>{html.escape(str(st.get('vm', 'Lotus-Lab')))}</b> — "
            f"<span style='color:{color}'>{state}</span><br>",
            f"VirtualBox: {'yes' if st.get('virtualbox') else '<b>not found</b>'} · "
            f"credentials: {'saved' if st.get('configured') else '<b>missing</b>'}<br>",
            f"staging: {html.escape(str(st.get('staging', '')))} "
            f"({st.get('staged_files', 0)} files)<br>",
            f"<span style='color:#9f8bd0'>Ask Lotus to work in the devbox: “edit your code”/"
            f"“sandbox test” — it edits staging, tests in the VM, then promotes.</span>",
        ]
        self.devbox_status.setHtml("".join(lines))

    def _devbox_action(self, fn):
        self.devbox_status.setHtml("<i>working…</i>")
        self._run_bg(
            fn,
            on_ok=lambda res: (self.refresh_devbox(),
                               db.log("info", "devbox", str(res)[:300])),
            on_err=lambda exc: (self.refresh_devbox(),
                                db.log("error", "devbox", str(exc)[:300])),
        )

    def _refresh_experiments(self):
        try:
            rows = db.recent_experiments(100)
        except Exception:
            return
        self.experiments_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            created = str(row.get("created", ""))
            stamp = created[11:19] if len(created) >= 19 else created
            values = [
                stamp,
                row.get("kind", ""),
                "ok" if row.get("ok") else "failed",
                f"{float(row.get('duration_s') or 0):.0f}",
                str(row.get("goal", ""))[:200],
            ]
            for col, value in enumerate(values):
                self.experiments_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.experiments_table.scrollToBottom()

    def _build_center(self) -> QWidget:
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(12)
        layout.addStretch(1)

        self.reactor = ReactorWidget(size=300)
        layout.addWidget(self.reactor, 0, Qt.AlignmentFlag.AlignCenter)

        self.center_status = QLabel("Lotus online — cybersecurity mode")
        self.center_status.setObjectName("status")
        self.center_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.center_status)

        hint = QLabel("Ask questions, scan files/repos, and review Lotus memory.")
        hint.setObjectName("subtitle")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch(2)

        ver = QLabel(f"v{__version__}")
        ver.setObjectName("version")
        ver.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(ver)
        return center

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def apply_theme(self, name: str):
        """Switch the accent palette instantly — widgets repaint on their own
        timers, so the whole app recolors in well under a second."""
        config.save_setting("ui_theme", name)
        self.setStyleSheet(theme.stylesheet(name))
        if hasattr(self, "orb_nav"):
            self.orb_nav.apply_theme()
        if hasattr(self, "clock_box"):
            self.clock_box.apply_theme()
        if hasattr(self, "version_label"):
            self.version_label.setStyleSheet(
                f"color: {theme.current()['subtitle']}; font-size: 10px;")

    # ── Dragging ────────────────────────────────────────────────────────────
    def _begin_drag(self, pos):
        self._drag_offset = pos - self.frameGeometry().topLeft()

    def _drag_move(self, pos):
        if self._drag_offset is not None:
            self.move(pos - self._drag_offset)

    def _end_drag(self):
        self._drag_offset = None

    # ── Chat ────────────────────────────────────────────────────────────────
    def _append_chat(self, who: str, text: str, css_class: str = ""):
        safe = html.escape(text).replace("\n", "<br>")
        accent = html.escape(theme.current()["section"])
        self.chat_view.append(
            f"<div class='msg {css_class}' style='margin:8px 0;'><b style='color:{accent}'>{html.escape(who)}:</b><br>{safe}</div>"
        )
        bar = self.chat_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_chat_status(self, text: str):
        self.center_status.setText(text)

    def _send_question(self):
        text = self.ask_input.toPlainText().strip()
        if not text:
            return
        self.ask_input.clear()
        self.ask_input.setEnabled(False)
        self._append_chat("You", text)

        if self._looks_like_os_question(text):
            self._answer_os_question(text, allowed=True)
            return

        self._set_chat_status("Lotus is thinking…")
        self.thinking_label.show()
        self._chunks: queue.Queue = queue.Queue()
        self._streamed = False
        self._run_bg(
            lambda: ai.ask_stream(text, self._chunks.put),
            on_ok=self._on_answer,
            on_err=self._on_answer_error,
        )

    @staticmethod
    def _looks_like_os_question(text: str) -> bool:
        lower = text.lower()
        patterns = [
            r"\bmy (os|operating system|computer|pc|laptop|system|hardware)\b",
            r"\b(this|the) (pc|computer|laptop|machine|system)\b",
            r"\b(system info|system information|hardware info|os version|windows version|macos|mac version|os x)\b",
            r"\b(cpu|gpu|ram|disk space|storage|system memory|memory usage)\b",
        ]
        return any(re.search(pattern, lower) for pattern in patterns)

    def _answer_os_question(self, original: str, allowed: bool):
        self._pending_os_question = ""
        if not allowed:
            answer = "Understood — I will not check system details for that question."
        else:
            try:
                info = platform_info.collect()
                answer = "Here is the read-only system information:\n\n" + info
            except Exception as exc:
                answer = f"I could not collect system information: {exc}"
        db.add_message("assistant", answer)
        db.remember_request(original, answer, model="local-system-info")
        db.log("info", "system", "OS info collected")
        self._append_chat("Lotus", answer)
        self._set_chat_status("Lotus online — cybersecurity mode")
        self.refresh_logs()

    def _on_answer(self, answer: str):
        self.thinking_label.hide()
        if not self._streamed:
            self._append_chat("Lotus", answer)
        self._set_chat_status("Lotus online — cybersecurity mode")
        self.ask_input.setEnabled(True)
        self.ask_input.setFocus()
        self.refresh_logs()
        self.refresh_memories()

    def _on_answer_error(self, exc: Exception):
        self.thinking_label.hide()
        self._append_chat("Lotus", f"I hit an error: {exc}")
        self._set_chat_status("Lotus online — cybersecurity mode")
        self.ask_input.setEnabled(True)
        self.ask_input.setFocus()
        self.refresh_logs()

    # ── Logs / memory ───────────────────────────────────────────────────────
    def refresh_logs(self):
        rows = db.recent_logs(300)
        self.logs_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            created = str(row.get("created", ""))
            stamp = created[11:19] if len(created) >= 19 else created
            values = [stamp, row.get("level", ""), row.get("source", ""), row.get("message", "")]
            for col, value in enumerate(values):
                self.logs_table.setItem(i, col, QTableWidgetItem(str(value)))
        self.logs_table.scrollToBottom()
        self._refresh_usage_view()

        requests = db.recent_requests(200)
        self.requests_table.setRowCount(len(requests))
        for i, row in enumerate(requests):
            created = str(row.get("created", ""))
            stamp = created[11:19] if len(created) >= 19 else created
            response = str(row.get("response", "")).replace("\n", " ")[:500]
            values = [
                stamp,
                row.get("model", ""),
                "yes" if row.get("used_search") else "no",
                str(row.get("prompt", ""))[:500],
                response,
            ]
            for col, value in enumerate(values):
                self.requests_table.setItem(i, col, QTableWidgetItem(value))
        self.requests_table.scrollToBottom()

    def refresh_memories(self):
        rows = db.list_memories(limit=500)
        self.memory_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = [row.get("category", ""), row.get("key", ""), row.get("value", "")]
            for col, value in enumerate(values):
                self.memory_table.setItem(i, col, QTableWidgetItem(str(value)))

    def _clear_logs(self):
        answer = QMessageBox.question(
            self, "Clear activity log", "Delete all activity log rows? Requests and memories will remain.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            db.clear_logs()
            self.refresh_logs()

    @staticmethod
    def _scan_target_options() -> list[tuple[str, str]]:
        options = [("Downloads", str(Path.home() / "Downloads"))]
        try:
            partitions = psutil.disk_partitions(all=True)
        except Exception:
            partitions = []
        if sys.platform != "win32":
            options.append(("Home folder", str(Path.home())))
            seen = {options[0][1], str(Path.home())}
            mounts = []
            for part in partitions:
                mount = part.mountpoint
                if mount in seen:
                    continue
                if mount == "/":
                    label = "Macintosh HD" if sys.platform == "darwin" else "System root"
                    kind = "local"
                elif mount.startswith(("/Volumes/", "/media/", "/run/media/", "/mnt/")):
                    label = mount.rstrip("/").rsplit("/", 1)[-1] or mount
                    kind = "external"
                else:
                    continue
                seen.add(mount)
                try:
                    free_gb = psutil.disk_usage(mount).free / (1024 ** 3)
                except Exception:
                    free_gb = 0.0
                mounts.append((f"{label} — {kind} ({free_gb:.0f} GB free)", mount))
            options.extend(sorted(mounts, key=lambda item: item[0].lower()))
            return options
        seen = set()
        drives = []
        for part in partitions:
            mount = part.mountpoint
            if not re.match(r"^[A-Za-z]:\\$", mount):
                continue
            key = mount.upper()
            if key in seen:
                continue
            seen.add(key)
            try:
                usage = psutil.disk_usage(mount)
                free_gb = usage.free / (1024 ** 3)
            except Exception:
                free_gb = 0.0
            opts = (part.opts or "").lower()
            kind = "external" if "removable" in opts or "cdrom" in opts else "local"
            drives.append((mount, kind, free_gb))
        for mount, kind, free_gb in sorted(drives, key=lambda item: item[0].lower()):
            drive_letter = mount.split(":", 1)[0] + ":"
            options.append((f"{drive_letter} — {kind} ({free_gb:.0f} GB free)", mount))
        return options

    def _refresh_scan_targets(self):
        current = self.scan_target_choice.currentData()
        self.scan_target_choice.blockSignals(True)
        self.scan_target_choice.clear()
        for label, path in self._scan_target_options():
            self.scan_target_choice.addItem(label, path)
        index = self.scan_target_choice.findData(current) if current else 0
        self.scan_target_choice.setCurrentIndex(max(index, 0))
        self.scan_target_choice.blockSignals(False)

    def _on_scan_mode_changed(self):
        is_folder = self.scan_mode.currentData() == "folder"
        self.scan_target_choice_widget.setVisible(is_folder)
        self.github_target.setVisible(not is_folder)

    # ── Scanner ─────────────────────────────────────────────────────────────
    def _run_scan(self):
        mode = self.scan_mode.currentData()
        if mode == "github":
            target = self.github_target.text().strip()
            if not target:
                QMessageBox.warning(self, "Scan target", "Enter a GitHub repository first.")
                return
        else:
            target = self.scan_target_choice.currentData() or ""
            if not target:
                QMessageBox.warning(self, "Scan target", "Choose a scan target first.")
                return
        self.scan_button.setEnabled(False)
        self.scan_status.setText("Scanning…")
        self.scan_details.setHtml("<i>Scanning…</i>")

        if mode == "github":
            fn = lambda: github.scan_github_repository(target, token=config.get_github_token())
        else:
            fn = lambda: scanner.scan_folder(target, clean=True)

        self._run_bg(
            fn,
            on_ok=self._on_scan_done,
            on_err=self._on_scan_error,
        )

    def _on_scan_done(self, report: dict):
        self.scan_button.setEnabled(True)
        if report.get("kind") == "code":
            self.scan_status.setText(
                f"code scan complete — {report.get('findings_total', 0)} findings "
                f"({report.get('high', 0)} high, {report.get('medium', 0)} medium, {report.get('low', 0)} low)"
            )
        else:
            self.scan_status.setText(str(report.get("final_status") or report.get("initial_status") or "scan complete"))
        self.scan_details.setHtml(self._scan_report_html(report))
        self.refresh_logs()

    def _on_scan_error(self, exc: Exception):
        self.scan_button.setEnabled(True)
        self.scan_status.setText("scan failed")
        self.scan_details.setHtml(f"<span style='color:#fda4af'>{html.escape(str(exc))}</span>")
        self.refresh_logs()

    @staticmethod
    def _scan_report_html(report: dict) -> str:
        if report.get("kind") == "code":
            lines = [
                f"<b>{html.escape(str(report.get('repo') or report.get('target') or 'repo'))}</b><br>",
                f"Files scanned: {report.get('files_scanned', 0)} · Findings: {report.get('findings_total', 0)}<br><br>",
            ]
            for finding in report.get("findings", [])[:80]:
                lines.append(
                    f"<div style='margin:6px 0;padding:6px;background:#1b0f33;border-radius:6px;'>"
                    f"<b style='color:#f0abfc'>{html.escape(finding.get('severity',''))}</b> "
                    f"{html.escape(finding.get('rule',''))} — {html.escape(finding.get('file',''))}:{finding.get('line','')}<br>"
                    f"<span style='color:#d8c7ff'>{html.escape(finding.get('message',''))}</span><br>"
                    f"<code style='color:#9f8bd0'>{html.escape(finding.get('excerpt',''))}</code></div>"
                )
            return "".join(lines)

        lines = [
            f"<b>{html.escape(str(report.get('target', '')))}</b><br>",
            f"Files scanned: {report.get('files_scanned', 0)} · Threat files: {report.get('threat_files', 0)} · "
            f"Warnings: {report.get('warning_files', 0)} · Cleaned: {report.get('cleaned', 0)}<br><br>",
        ]
        findings = report.get("findings", [])
        if not findings:
            lines.append("<span style='color:#86efac'>no suspicious files found</span>")
        for finding in findings[:80]:
            lines.append(
                "<div style='margin:6px 0;padding:6px;background:#1b0f33;border-radius:6px;'>"
                f"<b>{html.escape(finding.get('name',''))}</b> — {html.escape(finding.get('path',''))}<br>"
                f"Threats: {html.escape('; '.join(finding.get('threats', [])))}<br>"
                f"Warnings: {html.escape('; '.join(finding.get('warnings', [])))}<br>"
                f"Action: {html.escape(finding.get('quarantined','clean'))}</div>"
            )
        return "".join(lines)

    # ── Settings / updater ──────────────────────────────────────────────────
    def _open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
        self.refresh_logs()

    def _check_update(self):
        self._run_bg(
            lambda: updater.check_for_update(),
            on_ok=self._on_update_check,
            on_err=lambda exc: db.log("warning", "updater", f"update check failed: {exc}"),
        )

    def _on_update_check(self, info):
        self._update_info = info
        if info:
            db.log("info", "updater", f"update available: {info.get('version')}")
            self._on_update_clicked()

    def _check_update_now(self):
        self.update_button.setEnabled(False)
        self.update_button.setText("Checking…")

        def done(info):
            self.update_button.setEnabled(True)
            self.update_button.setText("Check for updates")
            self._update_info = info
            if info:
                self._on_update_clicked()
            else:
                QMessageBox.information(
                    self, "Check for updates",
                    "You're currently on the latest version.")

        def err(exc):
            self.update_button.setEnabled(True)
            self.update_button.setText("Check for updates")
            db.log("warning", "updater", f"update check failed: {exc}")
            QMessageBox.warning(self, "Check for updates",
                                f"Couldn't check for updates: {exc}")

        self._run_bg(updater.check_for_update, on_ok=done, on_err=err)

    def _on_update_clicked(self):
        info = self._update_info
        if not info:
            return
        body = (info.get("body") or "")[:1200]
        box = QMessageBox(self)
        box.setWindowTitle(f"Update Lotus to {info.get('version', '')}?")
        box.setText(
            f"Update available — Lotus {info.get('version', '')}.\n\n"
            f"{body}\n\n"
            "Update and restart — install now, Lotus relaunches when done.\n"
            "Update on relaunch — keep using Lotus; it installs automatically "
            "next time you open it."
        )
        restart_btn = box.addButton("Update and restart", QMessageBox.ButtonRole.AcceptRole)
        later_btn = box.addButton("Update on relaunch", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is restart_btn:
            self._start_update_download(restart=True)
        elif clicked is later_btn:
            self._start_update_download(restart=False)

    def _start_update_download(self, restart: bool):
        info = self._update_info
        self.update_button.setEnabled(False)
        self._dl_state = {"done": 0, "total": 0, "cancel": False}
        version = str(info.get("version", ""))
        self._dl_dialog = QProgressDialog(
            f"Downloading Lotus {version}…", "Cancel", 0, 100, self)
        self._dl_dialog.setWindowTitle("Lotus update")
        self._dl_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._dl_dialog.setMinimumDuration(0)
        self._dl_dialog.setAutoClose(False)
        self._dl_dialog.canceled.connect(self._cancel_download)
        self._dl_dialog.show()
        self._dl_restart = restart
        self._dl_timer = QTimer(self)
        self._dl_timer.timeout.connect(self._poll_download)
        self._dl_timer.start(80)

        def work():
            def progress(done: int, total: int):
                if self._dl_state["cancel"]:
                    raise RuntimeError("Download cancelled.")
                self._dl_state["done"], self._dl_state["total"] = done, total
            zip_path = updater.download_update(info, progress=progress)
            updater.apply_update(zip_path, launch=restart)
            return zip_path

        self._run_bg(work, on_ok=self._on_download_done, on_err=self._on_update_error)

    def _poll_download(self):
        state = getattr(self, "_dl_state", None)
        dlg = getattr(self, "_dl_dialog", None)
        if not state or not dlg:
            return
        total, done = state["total"], state["done"]
        version = str((self._update_info or {}).get("version", ""))
        if total:
            dlg.setMaximum(100)
            dlg.setValue(int(done * 100 / total))
            dlg.setLabelText(
                f"Downloading Lotus {version}… "
                f"{done / 1048576:.1f} / {total / 1048576:.1f} MB")
        else:
            dlg.setMaximum(0)
            dlg.setLabelText(f"Downloading Lotus {version}… {done / 1048576:.1f} MB")

    def _cancel_download(self):
        if getattr(self, "_dl_state", None):
            self._dl_state["cancel"] = True

    def _close_download_ui(self):
        timer = getattr(self, "_dl_timer", None)
        if timer:
            timer.stop()
        dlg = getattr(self, "_dl_dialog", None)
        if dlg:
            dlg.close()

    def _on_download_done(self, _zip_path):
        self._close_download_ui()
        version = str((self._update_info or {}).get("version", ""))
        if self._dl_restart:
            QMessageBox.information(
                self, "Lotus update",
                "Update downloaded — Lotus will restart now to apply it.")
            QApplication.quit()
        else:
            QMessageBox.information(
                self, "Lotus update",
                f"Lotus {version} will install automatically next time you open it. "
                "The app must update before it can be used again.")
            self.update_button.setEnabled(True)

    def _on_update_error(self, exc: Exception):
        self._close_download_ui()
        self.update_button.setEnabled(True)
        if str(exc) == "Download cancelled.":
            db.log("info", "updater", "update download cancelled by user")
            return
        self._show_error(exc)
