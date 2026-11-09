"""Settings dialog for Lotus secrets and integration tokens."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from .. import ai, config, db


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lotus Settings")
        self.setMinimumWidth(560)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Gemini API key"))
        self.gemini_edit = QLineEdit()
        self.gemini_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_edit.setPlaceholderText("Stored locally — enter a new key to replace it")
        layout.addWidget(self.gemini_edit)

        gemini_row = QHBoxLayout()
        import_btn = QPushButton("Import from Jarvis")
        import_btn.clicked.connect(self._import_jarvis)
        test_btn = QPushButton("Test Gemini")
        test_btn.clicked.connect(self._test_gemini)
        gemini_row.addWidget(import_btn)
        gemini_row.addWidget(test_btn)
        gemini_row.addStretch(1)
        layout.addLayout(gemini_row)

        layout.addWidget(QLabel("GitHub token (optional, for private repo scans)"))
        self.github_edit = QLineEdit()
        self.github_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_edit.setPlaceholderText("Stored locally — enter a new token to replace it")
        layout.addWidget(self.github_edit)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #a78bfa;")
        layout.addWidget(self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _import_jarvis(self):
        for path in config.jarvis_config_candidates():
            key = config.read_jarvis_gemini_key(path)
            if key:
                self.gemini_edit.setText(key)
                self.status.setText(f"Loaded Gemini key from {path}.")
                return
        self.status.setText("No Jarvis Gemini key was found.")

    def _test_gemini(self):
        replacement = self.gemini_edit.text().strip()
        if replacement:
            config.save_gemini_key(replacement)
        self.status.setText("Testing Gemini connection…")
        try:
            reply = ai.ping()
            self.status.setText(f"Gemini answered: {reply[:80]}")
        except Exception as exc:
            self.status.setText(f"Gemini test failed: {exc}")

    def _save(self):
        gemini = self.gemini_edit.text().strip()
        github = self.github_edit.text().strip()
        if gemini:
            config.save_gemini_key(gemini)
        if github:
            config.save_github_token(github)
        db.log("info", "settings", "settings saved")
        QMessageBox.information(self, "Saved", "Lotus settings were saved locally.")
        self.accept()
