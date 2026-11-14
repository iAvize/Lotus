"""Safe system information collection.

Only non-secret host facts are gathered. Lotus may answer read-only system
questions directly after install; it still does not change the OS.
"""
from __future__ import annotations

import os
import platform
import socket
import subprocess
import sys


def _gpu_names() -> str:
    try:
        if sys.platform == "win32":
            kwargs = {"capture_output": True, "text": True, "timeout": 5}
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
                ],
                **kwargs,
            )
            names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return "; ".join(names)
        if sys.platform == "darwin":
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, timeout=10,
            )
            names = []
            for line in (result.stdout or "").splitlines():
                if "Chipset Model:" in line:
                    names.append(line.split(":", 1)[1].strip())
            return "; ".join(dict.fromkeys(names))
        result = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=5)
        names = [line.split(":", 2)[-1].strip()
                 for line in (result.stdout or "").splitlines()
                 if "VGA" in line or "3D controller" in line]
        return "; ".join(names)
    except Exception:
        return ""


def _cpu_name() -> str:
    name = platform.processor()
    if name:
        return name
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5)
            if result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return platform.machine() or "unknown"
    return "unknown"


def collect() -> str:
    lines = [
        f"Operating system: {platform.system()} {platform.release()} ({platform.version()})",
        f"Platform: {platform.platform()}",
        f"Machine: {platform.machine()}",
        f"Hostname: {socket.gethostname()}",
        f"User profile: {os.path.expanduser('~')}",
        f"Python: {sys.version.split()[0]}",
        f"Processor: {_cpu_name()}",
        f"CPU count: {os.cpu_count() or 'unknown'}",
    ]

    gpus = _gpu_names()
    if gpus:
        lines.append(f"GPU: {gpus}")

    try:
        import psutil
        lines.append(f"CPU usage: {psutil.cpu_percent(interval=0.1):.1f}%")
        mem = psutil.virtual_memory()
        lines.append(
            f"Memory: {mem.total / (1024**3):.1f} GB total, "
            f"{mem.available / (1024**3):.1f} GB available ({mem.percent:.1f}% used)"
        )
        try:
            disk = psutil.disk_usage(os.path.expanduser("~"))
            lines.append(
                f"Disk for user profile: {disk.total / (1024**3):.1f} GB total, "
                f"{disk.free / (1024**3):.1f} GB free ({disk.percent:.1f}% used)"
            )
        except Exception:
            pass
    except Exception:
        pass

    return "\n".join(lines)
