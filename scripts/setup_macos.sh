#!/bin/bash
# Lotus macOS setup: build .venv and install requirements.
set -e
cd "$(dirname "$0")/.." || exit 1
PY="$(command -v python3.14 || command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)"
echo "Using $PY"
"$PY" -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
echo "Setup complete — launch with scripts/Run-Lotus.command or: .venv/bin/python -m lotus"
