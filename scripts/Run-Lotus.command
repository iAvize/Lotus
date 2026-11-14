#!/bin/bash
# Lotus launcher for macOS — double-clickable from Finder.
cd "$(dirname "$0")/.." || exit 1
if [ -x ".venv/bin/python" ]; then
    exec ".venv/bin/python" -m lotus
fi
exec python3 -m lotus
