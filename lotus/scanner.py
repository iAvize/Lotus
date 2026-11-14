"""Basic file and code scanning for Lotus beta.

This is intentionally conservative: it flags structurally dangerous files and
moves confirmed threats into memory/quarantine instead of deleting them.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from . import config, db

_DANGEROUS_EXT = {
    ".exe", ".msi", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".wsh", ".scr", ".com", ".pif", ".hta", ".lnk", ".dll", ".jar",
    ".reg", ".iso", ".img", ".gadget", ".msc", ".msp", ".cpl", ".inf",
    # macOS executables/installers/scriptable payloads
    ".app", ".dmg", ".pkg", ".command", ".scpt", ".applescript",
    ".workflow", ".mobileconfig", ".dylib", ".kext",
}
_ARCHIVE_EXT = {".zip", ".jar", ".7z", ".rar", ".tar", ".gz"}
_BAIT_EXT = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".jpg", ".jpeg",
    ".png", ".gif", ".mp3", ".mp4", ".zip", ".rar", ".csv",
}
_SCRIPT_EXT = {
    ".ps1", ".bat", ".cmd", ".vbs", ".js", ".jse", ".wsf", ".py", ".reg",
    ".hta", ".sh", ".zsh", ".command", ".scpt", ".applescript",
}
_SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "env", "dist", "build", ".idea", ".vscode",
}
_TEXT_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".php",
    ".rb", ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".json", ".yml",
    ".yaml", ".toml", ".ini", ".cfg", ".conf", ".sh", ".ps1", ".bat",
}

_BAD_CODE = (
    (r"invoke-expression|iex\b", "dynamic code execution (IEX)"),
    (r"downloadstring|downloadfile|invoke-webrequest|wget |curl .*(?:-o|>)", "downloads a remote payload"),
    (r"frombase64string|-enc\b|-encodedcommand", "encoded/obfuscated payload"),
    (r"wscript\.shell|createobject\(.*shell", "spawns a system shell"),
    (r"setwindowshookex|getasynckeystate|keylog", "keylogger pattern"),
    (r"mimikatz|lsass|sekurlsa", "credential-dump pattern"),
    (r"start-process.*hidden|-windowstyle hidden", "hidden process launch"),
)

_CODE_RULES = (
    ("hardcoded-secret", "high", re.compile(r"(?i)(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*[\"'][^\"']{8,}[\"']"), "Possible hardcoded secret"),
    ("shell-true", "high", re.compile(r"shell\s*=\s*True"), "Shell command execution enabled"),
    ("os-system", "high", re.compile(r"\bos\.system\s*\("), "os.system executes shell commands"),
    ("eval-exec", "medium", re.compile(r"\b(?:eval|exec)\s*\("), "Dynamic eval/exec can execute untrusted code"),
    ("pickle-load", "high", re.compile(r"pickle\.loads?\s*\("), "pickle deserialization can execute code"),
    ("yaml-load", "medium", re.compile(r"yaml\.load\s*\("), "yaml.load can execute code without SafeLoader"),
    ("sql-fstring", "high", re.compile(r"(?:execute|executemany)\s*\(\s*f[\"']"), "SQL query built with an f-string"),
    ("verify-false", "medium", re.compile(r"verify\s*=\s*False"), "TLS certificate verification disabled"),
    ("dangerous-html", "medium", re.compile(r"dangerouslySetInnerHTML|\.innerHTML\s*="), "Potential XSS through HTML injection"),
    ("weak-hash", "low", re.compile(r"hashlib\.(?:md5|sha1)\s*\("), "Weak hash algorithm"),
    ("debug-true", "low", re.compile(r"debug\s*=\s*True"), "Debug mode enabled"),
)


_MACHO_MAGIC = {
    b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",  # 64/32-bit Mach-O (LE)
    b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce",  # 64/32-bit Mach-O (BE)
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",  # universal/fat binary
}


def _is_macho(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(4) in _MACHO_MAGIC
    except Exception:
        return False


def _is_signed(path: Path) -> str | None:
    if sys.platform == "darwin":
        suffix = path.suffix.lower()
        if suffix not in {".app", ".dmg", ".pkg", ".command", ".dylib", ".kext"} \
                and not _is_macho(path):
            return None
        try:
            result = subprocess.run(
                ["codesign", "--verify", str(path)],
                capture_output=True, text=True, timeout=15,
            )
            return "signed" if result.returncode == 0 else "unsigned"
        except Exception:
            return None
    if sys.platform != "win32" or path.suffix.lower() not in {".exe", ".msi", ".dll", ".ps1", ".bat", ".cmd"}:
        return None
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-AuthenticodeSignature -LiteralPath $env:LOTUS_SIG_PATH).Status"],
            capture_output=True,
            text=True,
            timeout=15,
            env={**os.environ, "LOTUS_SIG_PATH": str(path)},
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        status = (result.stdout or "").strip()
        if status == "Valid":
            return "signed"
        if status in {"NotSigned", "HashMismatch", "NotTrusted", "Incompatible", "NotSupportedFileFormat"}:
            return "unsigned"
    except Exception:
        pass
    return None


def _script_flags(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:200_000]
    except Exception:
        return []
    low = text.lower()
    return [label for pattern, label in _BAD_CODE if re.search(pattern, low)]


def _archive_flags(path: Path) -> tuple[list[str], list[str]]:
    threats: list[str] = []
    warnings: list[str] = []
    try:
        if path.suffix.lower() != ".zip":
            return threats, warnings
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        exes = [name for name in names if Path(name).suffix.lower() in _DANGEROUS_EXT]
        if exes:
            warnings.append(f"archive contains executables: {', '.join(exes[:3])}")
        if len(names) == 1 and exes:
            threats.append("lone-executable zip — classic dropper shape")
        bait = [name for name in names if len(Path(name).name.split('.')) >= 3
                and Path(name).name.split('.')[-2] in {e.lstrip('.') for e in _BAIT_EXT}
                and Path(name).suffix.lower() in _DANGEROUS_EXT]
        if bait:
            threats.append(f"archive contains double-extension lure: {bait[0]}")
    except Exception:
        pass
    return threats, warnings


def _scan_file(path: Path) -> dict:
    threats: list[str] = []
    warnings: list[str] = []
    suffix = path.suffix.lower()
    name = path.name.lower()
    parts = name.split(".")

    if len(parts) >= 3 and parts[-2] in {e.lstrip(".") for e in _BAIT_EXT} and suffix in _DANGEROUS_EXT:
        threats.append(f"double-extension lure ({'.'.join(parts[-2:])})")

    if suffix in _DANGEROUS_EXT:
        warnings.append(f"executable type ({suffix})")
        signature = _is_signed(path)
        if signature == "unsigned":
            warnings.append("unsigned executable")

    if suffix in _SCRIPT_EXT:
        for flag in _script_flags(path):
            threats.append(flag)

    if suffix in _ARCHIVE_EXT:
        archive_threats, archive_warnings = _archive_flags(path)
        threats.extend(archive_threats)
        warnings.extend(archive_warnings)

    return {"threats": threats, "warnings": warnings}


def _iter_files(root: Path, max_files: int):
    count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for filename in files:
            if count >= max_files:
                return
            path = Path(current) / filename
            try:
                if not path.is_file():
                    continue
                yield path
                count += 1
            except Exception:
                continue


def _quarantine(path: Path) -> tuple[bool, str]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest_dir = config.QUARANTINE_DIR / stamp / path.parent.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    n = 1
    while dest.exists():
        dest = dest_dir / f"{path.stem}_{n}{path.suffix}"
        n += 1
    try:
        shutil.move(str(path), str(dest))
        db.log("warning", "scanner", f"quarantined {path} -> {dest}")
        return True, str(dest)
    except Exception as exc:
        db.log("error", "scanner", f"could not quarantine {path}: {exc}")
        return False, str(exc)


def scan_folder(path: str | Path, clean: bool = True, max_files: int = 5000) -> dict:
    root = Path(path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Folder does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Not a folder: {root}")

    findings: list[dict] = []
    files_scanned = 0
    threat_files = 0
    warning_files = 0
    cleaned = 0
    quarantine_root = config.QUARANTINE_DIR.resolve()

    for file_path in _iter_files(root, max_files):
        try:
            resolved = file_path.resolve()
            if quarantine_root in resolved.parents or resolved == quarantine_root:
                continue
        except Exception:
            pass
        result = _scan_file(file_path)
        files_scanned += 1
        if result["threats"]:
            threat_files += 1
        elif result["warnings"]:
            warning_files += 1
        if not result["threats"] and not result["warnings"]:
            continue

        finding = {
            "path": str(file_path),
            "name": file_path.name,
            "size_kb": round(file_path.stat().st_size / 1024, 1),
            "threats": result["threats"],
            "warnings": result["warnings"],
            "quarantined": "",
        }
        if clean and result["threats"]:
            ok, detail = _quarantine(file_path)
            finding["quarantined"] = detail if ok else f"failed: {detail}"
            if ok:
                cleaned += 1
        findings.append(finding)

    initial_status = "no viruses detected" if threat_files == 0 else "virus detected, cleaning now"
    final_status = initial_status
    if threat_files:
        final_status = f"{threat_files} threat(s) found; {cleaned} quarantined" if clean else f"{threat_files} threat(s) found; cleaning disabled"

    report = {
        "target": str(root),
        "kind": "folder",
        "files_scanned": files_scanned,
        "threat_files": threat_files,
        "warning_files": warning_files,
        "cleaned": cleaned,
        "initial_status": initial_status,
        "final_status": final_status,
        "findings": findings,
    }
    db.record_scan(str(root), "folder", files_scanned, threat_files, cleaned, report)
    db.log("info", "scanner", f"folder scan {root}: {files_scanned} files, {threat_files} threats, {cleaned} cleaned")
    return report


def scan_code_path(path: str | Path, max_files: int = 5000) -> dict:
    root = Path(path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")

    findings: list[dict] = []
    files_scanned = 0
    scan_root = root if root.is_dir() else root.parent

    for file_path in _iter_files(scan_root, max_files):
        if file_path.suffix.lower() not in _TEXT_EXT:
            continue
        try:
            if file_path.stat().st_size > 1_000_000:
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        files_scanned += 1
        rel = file_path.relative_to(scan_root) if file_path.is_relative_to(scan_root) else file_path
        for line_no, line in enumerate(text.splitlines(), 1):
            for rule_id, severity, pattern, message in _CODE_RULES:
                if pattern.search(line):
                    findings.append({
                        "file": str(rel),
                        "line": line_no,
                        "severity": severity,
                        "rule": rule_id,
                        "message": message,
                        "excerpt": line.strip()[:220],
                    })
                    if len(findings) >= 500:
                        break
            if len(findings) >= 500:
                break
        if len(findings) >= 500:
            break

    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")
    low = sum(1 for f in findings if f["severity"] == "low")
    report = {
        "target": str(root),
        "kind": "code",
        "files_scanned": files_scanned,
        "findings_total": len(findings),
        "high": high,
        "medium": medium,
        "low": low,
        "findings": findings,
    }
    db.record_scan(str(root), "code", files_scanned, len(findings), 0, report)
    db.log("info", "scanner", f"code scan {root}: {files_scanned} files, {len(findings)} findings")
    return report
