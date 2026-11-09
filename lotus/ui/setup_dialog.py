"""First-run Gemini API key setup for Lotus."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from .. import ai, config, db


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Lotus")
        self.setMinimumWidth(560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Lotus needs a Gemini API key for its beta brain.")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #e9d5ff;")
        layout.addWidget(title)

        explainer = QLabel(
            "Your key is stored only in this app's local config/api_keys.json file. "
            "It is never committed to GitHub. You can also import the key Jarvis already uses on this PC."
        )
        explainer.setWordWrap(True)
        explainer.setStyleSheet("color: #bda9ee;")
        layout.addWidget(explainer)

        key_link = QLabel(
            'Need a key? <a href="https://aistudio.google.com/apikey">'
            'Create a free Gemini API key in Google AI Studio</a>.'
        )
        key_link.setOpenExternalLinks(True)
        key_link.setWordWrap(True)
        key_link.setStyleSheet("color: #c4b5fd;")
        layout.addWidget(key_link)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("Paste Gemini API key")
        layout.addWidget(self.key_edit)

        row = QHBoxLayout()
        import_btn = QPushButton("Import from Jarvis")
        import_btn.clicked.connect(self._import_jarvis)
        test_btn = QPushButton("Test")
        test_btn.clicked.connect(self._test)
        row.addWidget(import_btn)
        row.addWidget(test_btn)
        row.addStretch(1)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #a78bfa;")
        layout.addWidget(self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _import_jarvis(self):
        candidates = config.jarvis_config_candidates()
        if not candidates:
            self.status.setText("No Jarvis config/api_keys.json was found on this machine.")
            return
        for path in candidates:
            key = config.read_jarvis_gemini_key(path)
            if key:
                self.key_edit.setText(key)
                self.status.setText(f"Imported the Gemini key from {path}.")
                db.log("info", "setup", f"imported Gemini key candidate from {path}")
                return
        self.status.setText("Jarvis config was found, but it did not contain a Gemini key.")

    def _test(self):
        key = self.key_edit.text().strip()
        if len(key) <= 15:
            self.status.setText("Paste a valid-looking Gemini API key first.")
            return
        config.save_gemini_key(key)
        self.status.setText("Testing Gemini connection…")
        try:
            reply = ai.ping()
            self.status.setText(f"Gemini answered: {reply[:80]}")
        except Exception as exc:
            self.status.setText(f"Gemini test failed: {exc}")

    def _save(self):
        key = self.key_edit.text().strip()
        if len(key) <= 15:
            QMessageBox.warning(self, "Missing key", "Paste a Gemini API key before continuing.")
            return
        config.save_gemini_key(key)
        db.log("info", "setup", "Gemini API key saved")
        self.accept()
