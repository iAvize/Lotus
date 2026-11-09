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
from PyQt6.QtCore import QStandardPaths, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollBar, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from .. import ai, config, db, github, platform_info, scanner, updater
from .settings_dialog import SettingsDialog
from .theme import APP_STYLESHEET
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lotus")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(1360, 800)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(APP_STYLESHEET)
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

        self._build_ui()
        self.refresh_logs()
        self.refresh_memories()
        QTimer.singleShot(800, self._check_update)

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

        self.update_button = QPushButton("Update")
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self._on_update_clicked)
        header_layout.addWidget(self.update_button)

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self._open_settings)
        header_layout.addWidget(settings_button)

        minimize = QPushButton("—")
        minimize.setFixedWidth(42)
        minimize.clicked.connect(self.showMinimized)
        header_layout.addWidget(minimize)
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
        content_layout.addWidget(self.left_panel)
        content_layout.addWidget(self._build_center(), 1)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section")
        return label

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedWidth(620)
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
        nav_layout.addStretch(1)

        layout.addWidget(nav)
        layout.addWidget(self.section_stack, 1)

        self._refresh_scan_targets()
        self._on_scan_mode_changed()
        self._show_section("ask")
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
        for section_key, button in self._section_buttons.items():
            button.setChecked(section_key == key)
        self.section_stack.setCurrentIndex(self._section_pages[key])

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
        self.ask_input = QLineEdit()
        self.ask_input.setPlaceholderText("Ask a question…")
        self.ask_input.returnPressed.connect(self._send_question)
        send = QPushButton("Send")
        send.setObjectName("sendButton")
        send.clicked.connect(self._send_question)
        ask_row.addWidget(self.ask_input, 1)
        ask_row.addWidget(send)
        layout.addLayout(ask_row)
        return page

    def _build_logs_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.log_tabs = QTabWidget()
        self.logs_table = self._make_table(["Time", "Level", "Source", "Message"])
        self.requests_table = self._make_table(["Time", "Model", "Search", "Prompt", "Response"])
        self.memory_table = self._make_table(["Category", "Key", "Value"])
        self.log_tabs.addTab(self.logs_table, "Activity")
        self.log_tabs.addTab(self.requests_table, "Requests")
        self.log_tabs.addTab(self.memory_table, "Memory")
        self.log_tabs.setMinimumHeight(160)
        layout.addWidget(self.log_tabs, 1)

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

    def _make_table(self, columns: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

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
        return center

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
        self.chat_view.append(
            f"<div class='msg {css_class}' style='margin:8px 0;'><b style='color:#c4b5fd'>{html.escape(who)}:</b><br>{safe}</div>"
        )
        bar = self.chat_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_chat_status(self, text: str):
        self.center_status.setText(text)

    def _send_question(self):
        text = self.ask_input.text().strip()
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
        self._run_bg(
            lambda: ai.ask(text),
            on_ok=self._on_answer,
            on_err=self._on_answer_error,
        )

    @staticmethod
    def _looks_like_os_question(text: str) -> bool:
        lower = text.lower()
        patterns = [
            r"\bmy (os|operating system|computer|pc|laptop|system|hardware)\b",
            r"\b(this|the) (pc|computer|laptop|machine|system)\b",
            r"\b(system info|system information|hardware info|os version|windows version)\b",
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
            self.update_button.setEnabled(True)
            self.update_button.setText(f"Update {info.get('version', '')}")
            self.update_button.setToolTip(f"Lotus {info.get('version', '')} is available")
            db.log("info", "updater", f"update available: {info.get('version')}")
        else:
            self.update_button.setEnabled(False)
            self.update_button.setText("Up to date")

    def _on_update_clicked(self):
        info = self._update_info
        if not info:
            return
        body = (info.get("body") or "")[:1200]
        answer = QMessageBox.question(
            self,
            f"Update Lotus to {info.get('version', '')}?",
            f"{body}\n\nLotus will download the Windows beta zip and restart to finish updating.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        def perform_update():
            zip_path = updater.download_update(info)
            updater.apply_update(zip_path)
            return zip_path

        self.update_button.setEnabled(False)
        self.update_button.setText("Updating…")
        self._run_bg(
            perform_update,
            on_ok=lambda _path: self._finish_update(),
            on_err=self._on_update_error,
        )

    def _finish_update(self):
        QMessageBox.information(self, "Lotus update", "Update downloaded and staged. Lotus will now restart.")
        QApplication.quit()

    def _on_update_error(self, exc: Exception):
        self.update_button.setEnabled(True)
        self.update_button.setText("Update failed")
        self._show_error(exc)
