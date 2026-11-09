"""Safe system information collection.

Only non-secret host facts are gathered, and only after the UI has asked the
user for permission for the current question.
"""
from __future__ import annotations

import os
import platform
import socket
import sys


def collect() -> str:
    lines = [
        f"Operating system: {platform.system()} {platform.release()} ({platform.version()})",
        f"Platform: {platform.platform()}",
        f"Machine: {platform.machine()}",
        f"Hostname: {socket.gethostname()}",
        f"User profile: {os.path.expanduser('~')}",
        f"Python: {sys.version.split()[0]}",
        f"Processor: {platform.processor() or 'unknown'}",
        f"CPU count: {os.cpu_count() or 'unknown'}",
    ]

    try:
        import psutil
        mem = psutil.virtual_memory()
        lines.append(f"Memory: {mem.total / (1024**3):.1f} GB total, {mem.available / (1024**3):.1f} GB available")
        try:
            disk = psutil.disk_usage(os.path.expanduser("~"))
            lines.append(f"Disk for user profile: {disk.total / (1024**3):.1f} GB total, {disk.free / (1024**3):.1f} GB free")
        except Exception:
            pass
    except Exception:
        pass

    return "\n".join(lines)
