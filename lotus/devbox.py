"""Lotus Devbox — the dedicated VirtualBox 'Lotus-Lab' sandbox VM.

Lotus uses this lab to experiment on itself safely: it edits a *staging copy*
of the source on the host share, executes the code inside the disposable VM
(never on the live machine), reads the results, and only promotes changes to
the official source after the in-guest checks pass. Every run is recorded in
the `experiments` table and the model is asked to store a `lessons` memory —
that is how Lotus learns from its own attempts across sessions.

Layout (host):  <base>/VMs/<vm>  <base>/share/{staging,reports}
Guest pulls staging to C:\\lotus-staging and runs there (share is transfer only).
Guest credentials live in config/devbox.json (git-ignored), set with
`python -m lotus.devbox configure --user <vm-user> --password <vm-pass>`.
"""
from __future__ import annotations

from . import usage

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import config as _cfg

ROOT = Path(__file__).resolve().parent.parent
VM_NAME = os.environ.get("LOTUS_DEVBOX_VM", "Lotus-Lab")
SHARE_NAME = "lotus-lab"
GUEST_SHARE = f"\\\\vboxsvr\\{SHARE_NAME}"
GUEST_STAGE = r"C:\lotus-staging"
CONFIG_PATH = _cfg.CONFIG_DIR / "devbox.json"
PS_EXE = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

# Where the agent may write inside staging. Everything else is read-only.
_WRITABLE_DIRS = ("lotus/", "scripts/", "docs/")
_WRITABLE_FILES = re.compile(
    r"(?i)^(readme\.md|agents\.md|version\.json|requirements\.txt|"
    r"run-lotus\.bat|lotus source\.bat|lotus beta\.bat)$"
)
_FORBIDDEN = re.compile(r"(?i)(^|[/\\])(\.git|\.venv|memory|config|build|dist)([/\\]|$)")

_NOT_CONFIGURED = {
    "ok": False,
    "error": "devbox not configured",
    "hint": "run: python -m lotus.devbox configure --user <vm-user> --password <vm-pass>",
}

# Files/dirs never copied official -> staging (secrets and runtime data stay out of the VM).
_SYNC_EXCLUDE_DIRS = (".git", ".venv", "memory", "build", "dist", "__pycache__",
                      "_lotus_update_staging")
_SYNC_EXCLUDE_FILES = ("api_keys.json", "devbox.json", "*.pyc", "*.log")


def _base_dir() -> Path:
    env = os.environ.get("LOTUS_DEVBOX_DIR")
    if env:
        return Path(env)
    if sys.platform == "win32":
        for cand in (r"D:\Lotus-Lab", r"C:\Lotus-Lab"):
            p = Path(cand)
            if p.parent.exists() or p.exists():
                return p
        return Path(r"D:\Lotus-Lab")
    return Path.home() / "Lotus-Lab"


def staging_dir() -> Path:
    return _base_dir() / "share" / "staging"


def _vboxman() -> str | None:
    if sys.platform == "win32":
        for cand in (os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                                  "Oracle", "VirtualBox", "VBoxManage.exe"),
                     os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                                  "Oracle", "VirtualBox", "VBoxManage.exe")):
            if Path(cand).exists():
                return cand
        return None
    for cand in ("/Applications/VirtualBox.app/Contents/MacOS/VBoxManage",
                 "/usr/bin/VBoxManage", "/usr/local/bin/VBoxManage"):
        if Path(cand).exists():
            return cand
    return None


def _run(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    exe = _vboxman()
    if not exe:
        return subprocess.CompletedProcess(["VBoxManage"], 127, "", "VBoxManage not found")
    try:
        return subprocess.run([exe, *args], capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([exe, *args], 124, "", "timeout")


def config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(user: str, password: str) -> dict:
    _cfg.ensure_dirs()
    CONFIG_PATH.write_text(json.dumps({"vm": VM_NAME, "user": user, "password": password}),
                           encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
    return {"ok": True, "vm": VM_NAME, "user": user}


def _creds() -> tuple[str, str] | None:
    cfg = config()
    if cfg.get("user") and cfg.get("password"):
        return cfg["user"], cfg["password"]
    return None


def _vm_state() -> str:
    r = _run("showvminfo", VM_NAME, "--machinereadable")
    m = re.search(r'VMState="([^"]+)"', r.stdout or "")
    return m.group(1) if m else ("missing" if r.returncode else "unknown")


def status() -> dict:
    base = _base_dir()
    exe = _vboxman()
    state = _vm_state() if exe else "no-virtualbox"
    share_dir = base / "share"
    stage = staging_dir()
    staged = len([p for p in stage.rglob("*") if p.is_file()]) if stage.is_dir() else 0
    return {
        "ok": True, "vm": VM_NAME, "virtualbox": bool(exe), "vm_state": state,
        "share_dir": str(share_dir), "guest_share": GUEST_SHARE,
        "staging": str(stage), "staged_files": staged,
        "guest_stage": GUEST_STAGE,
        "configured": bool(_creds()),
    }


def ensure_share() -> dict:
    """Create the host share folders and register them with the VM.
    VirtualBox locks a running VM, so this only works while powered off."""
    share = _base_dir() / "share"
    for sub in ("staging", "reports"):
        (share / sub).mkdir(parents=True, exist_ok=True)
    state = _vm_state()
    if state not in ("poweroff", "saved"):
        return {"ok": False, "error": f"VM is {state}; power it off first"}
    r = _run("sharedfolder", "add", VM_NAME, "--name", SHARE_NAME,
             "--hostpath", str(share), "--automount")
    if r.returncode != 0 and "already exists" not in (r.stderr or ""):
        return {"ok": False, "error": (r.stderr or r.stdout or "sharedfolder add failed").strip()[:400]}
    return {"ok": True, "share": str(share), "guest_path": GUEST_SHARE}


def guest_run(exe: str, args: list[str], timeout_ms: int = 180000) -> dict:
    """Run a command inside the guest via VBoxManage guestcontrol."""
    creds = _creds()
    if not creds:
        return dict(_NOT_CONFIGURED)
    user, password = creds
    r = _run("guestcontrol", VM_NAME, "run",
             f"--username={user}", f"--password={password}",
             f"--exe={exe}", f"--timeout={timeout_ms}", "--", *args,
             timeout=int(timeout_ms / 1000) + 60)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        return {"ok": False, "error": (err or out or "guestcontrol failed")[:800],
                "output": out[:2000],
                "hint": "is the VM running, Guest Additions installed, and the user/password correct?"}
    return {"ok": True, "exit_code": r.returncode, "output": out[:6000]}


def guest_start(exe: str, args: list[str]) -> dict:
    """Spawn a process in the guest without waiting — guestcontrol's stdout
    reader can hang when child processes inherit its handles, so real work
    goes through run_guest() and its report file in the share."""
    creds = _creds()
    if not creds:
        return dict(_NOT_CONFIGURED)
    user, password = creds
    r = _run("guestcontrol", VM_NAME, "start",
             f"--username={user}", f"--password={password}",
             f"--exe={exe}", "--", *args, timeout=30)
    if r.returncode != 0:
        return {"ok": False,
                "error": (r.stderr or r.stdout or "guestcontrol start failed")[:500],
                "hint": "is the VM running, Guest Additions installed, and the user/password correct?"}
    return {"ok": True}


_RUNNER_PS1 = r"""param(
  [Parameter(Mandatory=$true)][string]$Cmd,
  [Parameter(Mandatory=$true)][string]$Out,
  [string]$WorkDir = "C:\lotus-staging"
)
$ErrorActionPreference = 'Continue'
if (-not (Test-Path $WorkDir)) { $WorkDir = "C:\" }
$tmpO = Join-Path $env:TEMP "devbox-o.txt"
$tmpE = Join-Path $env:TEMP "devbox-e.txt"
$bat = Join-Path $env:TEMP "devbox-cmd.bat"
Remove-Item $tmpO, $tmpE -Force -ErrorAction SilentlyContinue
Set-Content -Path $bat -Value ("@echo off`r`n" + $Cmd) -Encoding ascii
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/d","/c",$bat `
     -WorkingDirectory $WorkDir -RedirectStandardOutput $tmpO `
     -RedirectStandardError $tmpE -PassThru -Wait -WindowStyle Hidden
$o = Get-Content $tmpO -Raw -ErrorAction SilentlyContinue
$e = Get-Content $tmpE -Raw -ErrorAction SilentlyContinue
"EXIT=$($p.ExitCode)`n--- STDOUT ---`n$o`n--- STDERR ---`n$e" |
  Out-File -FilePath $Out -Encoding utf8
"""


def _ensure_runner() -> Path:
    """(Re)write the in-guest command runner into the share — kept fresh so
    edits here always reach the VM."""
    harness = _base_dir() / "share" / "harness"
    harness.mkdir(parents=True, exist_ok=True)
    runner = harness / "devbox-runner.ps1"
    runner.write_text(_RUNNER_PS1, encoding="utf-8")
    return runner


def run_guest(command: str, timeout_s: int = 180, cwd: str = GUEST_STAGE) -> dict:
    """Run a shell command inside the VM and return captured output.

    The command executes via a PowerShell runner launched with
    `guestcontrol start` (never `run` — its stdout reader hangs when the
    child inherits handles). The runner writes EXIT/STDOUT/STDERR to a report
    file in the shared folder, which the host polls."""
    up = ensure_running()
    if not up.get("ok"):
        return up
    runner = _ensure_runner()
    reports = _base_dir() / "share" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    name = f"r{int(time.time())}{os.getpid() % 1000}.txt"
    report_host = reports / name
    report_host.unlink(missing_ok=True)
    args = ["-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", f"{GUEST_SHARE}\\harness\\{runner.name}",
            "-Cmd", command,
            "-Out", f"{GUEST_SHARE}\\reports\\{name}",
            "-WorkDir", cwd]
    t0 = time.time()
    res = guest_start(PS_EXE, args)
    if not res.get("ok"):
        return res
    deadline = time.time() + timeout_s
    while time.time() < deadline and not report_host.exists():
        time.sleep(1.5)
    elapsed = round(time.time() - t0, 1)
    if not report_host.exists():
        return {"ok": False, "error": f"guest command produced no report within {timeout_s}s",
                "command": command, "elapsed_s": elapsed}
    try:
        text = report_host.read_text(encoding="utf-8-sig", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"report unreadable: {e}"}
    m = re.match(r"EXIT=(-?\d+)\s*\n--- STDOUT ---\n(.*?)\n--- STDERR ---\n(.*)",
                 text, re.S)
    if not m:
        return {"ok": False, "error": "report malformed", "raw": text[:1000]}
    code, stdout, stderr = int(m.group(1)), m.group(2).strip(), m.group(3).strip()
    return {"ok": code == 0, "exit_code": code, "output": stdout[:6000],
            "stderr": stderr[:2000], "command": command, "elapsed_s": elapsed}


def ensure_running(timeout_s: int = 300) -> dict:
    """Boot the lab headless if needed and wait for guest control."""
    if _vm_state() != "running":
        r = _run("startvm", VM_NAME, "--type", "headless")
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or r.stdout or "startvm failed").strip()[:300]}
        usage.vm_boot()
    if not _creds():
        return dict(_NOT_CONFIGURED)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = guest_run(r"C:\Windows\System32\cmd.exe", ["/c", "echo", "ok"], timeout_ms=20000)
        if r.get("ok"):
            return {"ok": True}
        time.sleep(10)
    return {"ok": False, "error": "guest control never came up — Guest "
            "Additions running, and does the lab user auto-log in?"}


def _poweroff(timeout_s: int = 75) -> bool:
    """Graceful shutdown first (ACPI power button = normal Windows shutdown);
    hard poweroff only as fallback. Repeatedly yanking power is how a lab
    disk gets corrupted — the dev VM keeps one disk around for a long time."""
    if _vm_state() != "running":
        return True
    _run("controlvm", VM_NAME, "acpipowerbutton", timeout=20)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _vm_state() != "running":
            time.sleep(2)
            usage.vm_shutdown()
            return True
        time.sleep(3)
    r = _run("controlvm", VM_NAME, "poweroff", timeout=30)
    time.sleep(3)
    if r.returncode == 0:
        usage.vm_shutdown()
    return r.returncode == 0


def snapshot(name: str = "dev-ready") -> dict:
    was_running = _vm_state() == "running"
    if was_running and not _poweroff():
        return {"ok": False, "error": "couldn't power off for the snapshot"}
    r = _run("snapshot", VM_NAME, "take", name, "--description", "lotus devbox baseline",
             timeout=300)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout or "snapshot failed").strip()[:400]}
    if was_running:
        up = ensure_running()
        if not up.get("ok"):
            return up
    return {"ok": True, "snapshot": name}


def revert(name: str = "dev-ready") -> dict:
    """Restore the lab to its clean baseline and boot it again."""
    if not _poweroff():
        return {"ok": False, "error": "couldn't shut down for the restore"}
    r = _run("snapshot", VM_NAME, "restore", name, timeout=300)
    if r.returncode != 0:
        return {"ok": False, "error": (r.stderr or r.stdout or "restore failed").strip()[:400]}
    up = ensure_running()
    if not up.get("ok"):
        return up
    return {"ok": True, "restored": name}


# ── Staging copy (host side) ────────────────────────────────────────────────

def sync() -> dict:
    """Mirror the official source into the staging share. Secrets and runtime
    data are never copied. Returns the robocopy summary."""
    stage = staging_dir()
    stage.mkdir(parents=True, exist_ok=True)
    cmd = ["robocopy", str(ROOT), str(stage), "/MIR", "/R:1", "/W:1",
           "/NFL", "/NDL", "/NJH", "/NP"]
    for d in _SYNC_EXCLUDE_DIRS:
        cmd += ["/XD", d]
    for f in _SYNC_EXCLUDE_FILES:
        cmd += ["/XF", f]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return {"ok": False, "error": "robocopy not available (Windows only)"}
    # robocopy exit codes 0-7 are success; >=8 is a failure
    ok = r.returncode < 8
    out = (r.stdout or "").strip()
    summary = "\n".join(out.splitlines()[-12:])
    return {"ok": ok, "exit_code": r.returncode, "staging": str(stage),
            "summary": summary[-2500:]}


def _safe_rel(path: str) -> Path | None:
    """Resolve an agent-supplied relative path inside staging, enforcing the
    writable allowlist. Returns None when the path is off-limits."""
    rel = str(path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("..") or "/../" in f"/{rel}/" or ":" in rel:
        return None
    if _FORBIDDEN.search(rel):
        return None
    return staging_dir() / rel


def _writable(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/").lower()
    return (any(rel.startswith(d) for d in _WRITABLE_DIRS)
            or bool(_WRITABLE_FILES.match(rel)))


def staging_list() -> list[str]:
    stage = staging_dir()
    if not stage.is_dir():
        return []
    out = []
    for p in sorted(stage.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out.append(str(p.relative_to(stage)).replace("\\", "/"))
    return out


def staging_read(path: str) -> dict:
    p = _safe_rel(path)
    if p is None:
        return {"ok": False, "error": f"path not allowed: {path}"}
    if not p.is_file():
        return {"ok": False, "error": f"not a file in staging: {path} "
                "(run devbox_sync first if it is missing)"}
    try:
        return {"ok": True, "path": str(p.relative_to(staging_dir())),
                "content": p.read_text(encoding="utf-8", errors="replace")[:60000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def staging_write(path: str, content: str) -> dict:
    """Write a file into the staging copy. Only the writable allowlist may be
    touched — config/, memory/ and secrets stay out of the lab entirely."""
    p = _safe_rel(path)
    if p is None or not _writable(path):
        return {"ok": False, "error": f"path not writable in staging: {path} "
                f"(allowed: {_WRITABLE_DIRS} + top-level docs/version/requirements)"}
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        _record("edit", f"staging write {path}", {"path": path, "bytes": len(content)}, True)
        return {"ok": True, "wrote": str(p.relative_to(staging_dir()))}
    except Exception as e:
        _record("edit", f"staging write {path}", {"error": str(e)}, False)
        return {"ok": False, "error": str(e)}


def read_official(path: str) -> dict:
    """Read a file from the official source (read-only reference for the agent)."""
    rel = str(path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/") or ":" in rel or _FORBIDDEN.search(rel):
        return {"ok": False, "error": f"path not allowed: {path}"}
    p = ROOT / rel
    if not p.is_file():
        return {"ok": False, "error": f"not a file: {path}"}
    try:
        return {"ok": True, "path": rel,
                "content": p.read_text(encoding="utf-8", errors="replace")[:60000]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def staging_diff() -> dict:
    """Unified diff of every file that differs between staging and official."""
    stage = staging_dir()
    diffs, changed, missing = [], [], []
    for rel in staging_list():
        sp, op = stage / rel, ROOT / rel
        if not op.is_file():
            changed.append(rel)
            diffs.append(f"--- /dev/null\n+++ staging/{rel}  (new file)\n")
            continue
        try:
            old = op.read_text(encoding="utf-8", errors="replace").splitlines(True)
            new = sp.read_text(encoding="utf-8", errors="replace").splitlines(True)
        except Exception:
            continue
        if old != new:
            changed.append(rel)
            diffs.extend(difflib.unified_diff(
                old, new, fromfile=f"official/{rel}", tofile=f"staging/{rel}", n=2))
    text = "".join(diffs)
    return {"ok": True, "changed": changed, "diff": text[:30000],
            "truncated": len(text) > 30000}


def promote(paths: list[str] | None = None) -> dict:
    """Copy validated staging files into the official source. Each replaced
    file keeps a .bak backup alongside it. Only ever called after in-guest
    checks pass (enforced by the caller / agent rules)."""
    stage = staging_dir()
    targets = paths if paths else staging_diff().get("changed", [])
    promoted, skipped = [], []
    for rel in targets:
        p = _safe_rel(rel)
        if p is None or not _writable(rel):
            skipped.append(rel)
            continue
        official = ROOT / str(rel).replace("/", os.sep)
        try:
            official.parent.mkdir(parents=True, exist_ok=True)
            if official.exists():
                shutil.copy2(official, official.with_suffix(official.suffix + ".bak"))
            shutil.copy2(p, official)
            promoted.append(str(rel))
        except Exception as e:
            skipped.append(f"{rel} ({e})")
    _record("promote", f"promote {len(promoted)} files to official",
            {"promoted": promoted, "skipped": skipped}, bool(promoted))
    return {"ok": bool(promoted), "promoted": promoted, "skipped": skipped}


# ── Guest execution ─────────────────────────────────────────────────────────

_PROVISION_PS = (
    r"[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; "
    r"New-Item -ItemType Directory -Force C:\Users\lotus\Downloads | Out-Null; "
    r"Invoke-WebRequest https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip "
    r"-OutFile C:\Users\lotus\Downloads\pyembed.zip -UseBasicParsing; "
    r"Invoke-WebRequest https://bootstrap.pypa.io/get-pip.py "
    r"-OutFile C:\Users\lotus\Downloads\get-pip.py -UseBasicParsing; "
    r"Expand-Archive -Force C:\Users\lotus\Downloads\pyembed.zip C:\python312; "
    r"(Get-Content C:\python312\python312._pth) -replace '#import site','import site' | "
    r"Set-Content C:\python312\python312._pth; "
    r"C:\python312\python.exe C:\Users\lotus\Downloads\get-pip.py --quiet"
)

_SHIMS_CMD = (
    r'(echo @C:\python312\python.exe %*)> "%LOCALAPPDATA%\Microsoft\WindowsApps\python.bat" & '
    r'(echo @C:\python312\python.exe -m pip %*)> "%LOCALAPPDATA%\Microsoft\WindowsApps\pip.bat" & '
    r'echo C:\lotus-staging> C:\python312\Lib\site-packages\lotus-staging.pth'
)


def provision_guest() -> dict:
    """(Re)build the lab's guest toolchain: embeddable Python 3.12 at
    C:\\python312 (MSI installers can't run under guestcontrol), pip, PATH
    shims, and the requirements from the current staging copy. Idempotent —
    skips the toolchain if it's already there."""
    up = ensure_running()
    if not up.get("ok"):
        return up
    steps: list[dict] = []
    have = run_guest("dir /b C:\\python312\\python.exe",
                     timeout_s=60, cwd=r"C:\\")
    if "python.exe" not in (have.get("output") or ""):
        r = run_guest(f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{_PROVISION_PS}"',
                      timeout_s=600, cwd=r"C:\\")
        steps.append({"step": "python", "ok": r.get("ok", False),
                      "detail": (r.get("output") or r.get("stderr") or r.get("error") or "")[-400:]})
        if not r.get("ok"):
            return {"ok": False, "steps": steps}
        r = run_guest(_SHIMS_CMD, timeout_s=60, cwd=r"C:\\")
        steps.append({"step": "shims", "ok": r.get("ok", False),
                      "detail": (r.get("stderr") or r.get("error") or "")[-300:]})
    else:
        steps.append({"step": "python", "ok": True, "detail": "present"})
        run_guest(_SHIMS_CMD, timeout_s=60, cwd=r"C:\\")  # heal shims/pth
    s = sync()
    steps.append({"step": "sync", "ok": s.get("ok", False), "detail": s.get("summary", "")[-200:]})
    st = guest_stage()
    steps.append({"step": "stage", "ok": st.get("ok", False), "detail": st.get("error", "")})
    r = run_guest("python -m pip install --no-input --timeout 60 -r requirements.txt --quiet",
                  timeout_s=900)
    steps.append({"step": "deps", "ok": r.get("ok", False),
                  "detail": (r.get("stderr") or r.get("error") or "")[-400:]})
    return {"ok": all(x["ok"] for x in steps), "steps": steps}


def guest_stage() -> dict:
    """Refresh C:\\lotus-staging inside the guest from the share."""
    r = run_guest(f"robocopy \"{GUEST_SHARE}\\staging\" \"{GUEST_STAGE}\" /MIR /R:1 /W:1 "
                  f"/NFL /NDL /NJH /NP /XD .venv __pycache__ & exit /b 0",
                  timeout_s=120, cwd=r"C:\\")
    if r.get("ok") or "exit_code" in r:
        return {"ok": True}
    return r


def guest_python() -> str | None:
    """Locate a Python interpreter inside the guest."""
    probe = run_guest("where python py 2>nul & "
                      "for %%d in (C:\\python312\\python.exe C:\\python313\\python.exe "
                      "C:\\python311\\python.exe) do if exist %%d echo %%d & "
                      "if exist \"%LOCALAPPDATA%\\Programs\\Python\" "
                      "dir /b /s \"%LOCALAPPDATA%\\Programs\\Python\\python.exe\"",
                      timeout_s=60, cwd=r"C:\\")
    out = probe.get("output", "")
    for line in out.splitlines():
        line = line.strip()
        if line.lower().endswith("python.exe"):
            return f'"{line}"'
        if line.lower().endswith("py.exe"):
            return f'"{line}" -3'
    return None


def run_command(command: str, timeout_s: int = 180, goal: str = "") -> dict:
    """Run a shell command inside the VM at C:\\lotus-staging. The lab, not the
    live machine, executes it — this is where risky tests belong."""
    staged = guest_stage()
    if not staged.get("ok"):
        return staged
    r = run_guest(command, timeout_s=timeout_s)
    _record("run", goal or command, {"command": command,
            "ok": r.get("ok", False),
            "output": (r.get("output") or r.get("error") or "")[:3000]},
            bool(r.get("ok")), r.get("elapsed_s", 0))
    return r


def test(goal: str = "in-guest checks") -> dict:
    """Full validation: sync official->staging, stage into the guest, compile-
    check the package and import the core modules. This is the gate before
    promote() may run."""
    t0 = time.time()
    steps: list[dict] = []
    s = sync()
    steps.append({"step": "sync", "ok": s.get("ok"), "detail": s.get("summary", "")[-400:]})
    if not s.get("ok"):
        _record("test", goal, {"steps": steps}, False, time.time() - t0)
        return {"ok": False, "steps": steps}
    py = guest_python()
    steps.append({"step": "python", "ok": bool(py), "detail": py or "not found"})
    if not py:
        _record("test", goal, {"steps": steps}, False, time.time() - t0)
        return {"ok": False, "steps": steps}
    staged = guest_stage()
    steps.append({"step": "stage", "ok": staged.get("ok", False),
                  "detail": staged.get("error", "")})
    if not staged.get("ok"):
        _record("test", goal, {"steps": steps}, False, time.time() - t0)
        return {"ok": False, "steps": steps}
    for label, command in (
        ("compile", f"{py} scripts/check.py"),
        ("imports", f"{py} -c \"import lotus.ai, lotus.db, lotus.config, lotus.scanner, "
                    f"lotus.updater, lotus.github, lotus.platform_info\""),
    ):
        r = run_guest(command, timeout_s=240)
        steps.append({"step": label, "ok": r.get("ok", False),
                      "detail": (r.get("output") or r.get("stderr")
                                 or r.get("error") or "")[-800:]})
        if not r.get("ok"):
            break
    ok = all(s["ok"] for s in steps)
    res = {"ok": ok, "steps": steps, "elapsed_s": round(time.time() - t0, 1)}
    _record("test", goal, {"steps": [{"step": s["step"], "ok": s["ok"],
            "detail": s["detail"][:400]} for s in steps]}, ok, res["elapsed_s"])
    return res


# ── Experiments ledger (learn-from-itself) ──────────────────────────────────

def _record(kind: str, goal: str, detail: dict, ok: bool, duration_s: float = 0.0) -> None:
    try:
        from . import db
        db.record_experiment(kind, goal, detail, ok, duration_s)
    except Exception:
        pass


# ── Gemini tool surface ──────────────────────────────────────────────────────
# Plain callables: the google-genai SDK turns them into function declarations
# and executes them via automatic function calling. They never raise — errors
# come back as text so the model can react.

def devbox_status() -> str:
    """Return the current state of the Lotus-Lab sandbox VM and staging area."""
    return json.dumps(status())


def devbox_boot() -> str:
    """Boot the Lotus-Lab sandbox VM and wait for guest control."""
    return json.dumps(ensure_running())


def devbox_sync() -> str:
    """Mirror the official Lotus source into the VM staging area. Call this
    before editing so staging is fresh."""
    return json.dumps(sync())


def staging_list_files() -> str:
    """List every file currently in the staging copy of the Lotus source."""
    files = staging_list()
    return "\n".join(files) if files else "(staging is empty — run devbox_sync first)"


def staging_read_file(path: str) -> str:
    """Read one file from the staging copy (e.g. 'lotus/ai.py')."""
    r = staging_read(path)
    return r.get("content") or f"ERROR: {r.get('error')}"


def read_official_file(path: str) -> str:
    """Read one file from the official Lotus source, read-only. Use it to see
    the current released state before editing staging."""
    r = read_official(path)
    return r.get("content") or f"ERROR: {r.get('error')}"


def staging_write_file(path: str, content: str) -> str:
    """Write or rewrite a file in the staging copy (the experiment version).
    Only files under lotus/, scripts/, docs/ and top-level docs/version files
    are writable. Never writes to the official source."""
    return json.dumps(staging_write(path, content))


def staging_changes() -> str:
    """Show the diff between staging and the official source."""
    r = staging_diff()
    return r.get("diff") or "no differences" + ("" if r.get("ok") else f" ERROR: {r.get('error')}")


def devbox_run(command: str, goal: str = "") -> str:
    """Run a Windows shell command inside the Lotus-Lab VM at C:\\lotus-staging.
    Use it for anything executable: compile checks, pip installs, running the
    code, observing behavior. Never runs on the live machine."""
    return json.dumps(run_command(command, goal=goal))


def devbox_test(goal: str = "validate staging changes") -> str:
    """Full validation pipeline: sync official->staging, copy into the guest,
    compile-check the package and import core modules inside the VM. Must pass
    before promote_changes may be used."""
    return json.dumps(test(goal=goal))


def promote_changes() -> str:
    """Copy every staging file that differs into the official source (with
    .bak backups). Only call after devbox_test returned ok=true."""
    if _cfg.get_setting("devbox_auto_promote", "on") == "off":
        return json.dumps({"ok": False, "error": "auto-promote is disabled in settings — "
                           "ask the user to promote manually"})
    return json.dumps(promote())


def devbox_revert() -> str:
    """Restore the Lotus-Lab VM to its clean dev-ready snapshot."""
    return json.dumps(revert())


def record_lesson(lesson: str) -> str:
    """Store one concise lesson learned from this dev session so future Lotus
    sessions do better (what worked, what failed, why)."""
    try:
        from . import db
        db.add_lesson(lesson)
        return json.dumps({"ok": True})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


DEVBOX_TOOLS = (
    devbox_status, devbox_boot, devbox_sync, staging_list_files,
    staging_read_file, read_official_file, staging_write_file, staging_changes,
    devbox_run, devbox_test, promote_changes, devbox_revert, record_lesson,
)


# ── CLI ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m lotus.devbox",
                                 description="Lotus-Lab sandbox control")
    ap.add_argument("cmd", choices=["status", "configure", "share", "boot", "sync",
                                    "test", "run", "diff", "promote", "provision",
                                    "snapshot", "revert"])
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--user", default="")
    ap.add_argument("--password", default="")
    ap.add_argument("--name", default="")
    a = ap.parse_args(argv)

    if a.cmd == "configure":
        if not a.user or not a.password:
            print(json.dumps({"ok": False, "error": "needs --user and --password"}))
            return 2
        res = save_config(a.user, a.password)
    elif a.cmd == "status":
        res = status()
    elif a.cmd == "share":
        res = ensure_share()
    elif a.cmd == "boot":
        res = ensure_running()
    elif a.cmd == "sync":
        res = sync()
    elif a.cmd == "test":
        res = test()
    elif a.cmd == "run":
        if not a.arg:
            print(json.dumps({"ok": False, "error": "run needs a command"}))
            return 2
        res = run_command(a.arg)
    elif a.cmd == "diff":
        res = staging_diff()
    elif a.cmd == "promote":
        res = promote()
    elif a.cmd == "provision":
        res = provision_guest()
    elif a.cmd == "snapshot":
        res = snapshot(a.name or "dev-ready")
    elif a.cmd == "revert":
        res = revert(a.name or "dev-ready")
    else:
        return 1
    print(json.dumps(res, indent=2, default=str)[:8000])
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
