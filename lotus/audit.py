"""Project Audit - codebase scanning, AI findings, reviewable patches.

Pipeline: scan a project folder (local rule scan + AI review of the
highest-risk files) -> findings list -> per-finding unified-diff patch
proposal -> user reviews -> apply to disk with a .lotus-backup snapshot.

This feature is the Lotus Pro paywall seam: pro_enabled() today checks
dev builds + a stored license flag; a LotusCloud licensing backend plugs
in later without the rest changing.
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import ai, db, scanner, usage

_CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
             ".c", ".h", ".cpp", ".cs", ".rb", ".php", ".swift", ".kt"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
              "dist", "build", ".idea", ".vs", "target", "bin", "obj"}


def pro_enabled() -> bool:
    """Paywall gate - dev builds and licensed users get Project Audit."""
    if usage.is_dev_build():
        return True
    return db.get_setting("pro_license") == "1"


def inventory(path: str | Path, max_files: int = 5000) -> dict:
    """Cheap project snapshot: file counts by language + total LOC."""
    root = Path(path)
    exts: dict[str, int] = {}
    total_loc = 0
    files = 0
    for fp in root.rglob("*"):
        if files >= max_files:
            break
        if not fp.is_file() or any(p in _SKIP_DIRS for p in fp.parts):
            continue
        ext = fp.suffix.lower()
        files += 1
        exts[ext or "(none)"] = exts.get(ext or "(none)", 0) + 1
        if ext in _CODE_EXT:
            try:
                total_loc += sum(1 for _ in fp.open(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return {"root": str(root), "files": files, "loc": total_loc,
            "top_exts": sorted(exts.items(), key=lambda kv: -kv[1])[:8]}


def _risk_files(root: Path, report: dict, cap: int = 12) -> list[Path]:
    """Files the regex scan flagged first, then the biggest code files."""
    flagged = {f["file"] for f in report.get("findings", [])}
    out, seen = [], set()
    for rel in flagged:
        fp = root / rel
        if fp.exists() and fp not in seen:
            out.append(fp)
            seen.add(fp)
    if len(out) < cap:
        cands = [fp for fp in root.rglob("*")
                 if fp.is_file() and fp.suffix.lower() in _CODE_EXT
                 and not any(p in _SKIP_DIRS for p in fp.parts)]
        for fp in sorted(cands, key=lambda p: -p.stat().st_size):
            if len(out) >= cap:
                break
            if fp not in seen:
                out.append(fp)
                seen.add(fp)
    return out[:cap]


def ai_findings(path: str | Path, report: dict, max_chars: int = 42000) -> list[dict]:
    """Send the riskiest files to Gemini for a second, deeper pass."""
    root = Path(path)
    chunks, used = [], 0
    for fp in _risk_files(root, report):
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")[:9000]
        except OSError:
            continue
        rel = fp.relative_to(root) if fp.is_relative_to(root) else fp.name
        blob = f"### FILE: {rel}\n{text}"
        if used + len(blob) > max_chars:
            break
        chunks.append(blob)
        used += len(blob)
    if not chunks:
        return []
    prompt = (
        "You are a senior security/code auditor. Review these project files "
        "and return ONLY a JSON array of findings, no prose. Each item: "
        '{"severity":"high|medium|low","file":"relative/path","line":0,'
        '"title":"short name","detail":"what and why, 1-2 sentences",'
        '"fix":"one-line suggested fix"}. Real issues only, max 15.\n\n'
        + "\n\n".join(chunks))
    text, _model = ai._generate(prompt, timeout_ms=90_000)
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for item in data[:15]:
        if not isinstance(item, dict) or "title" not in item:
            continue
        out.append({
            "severity": str(item.get("severity", "low")).lower(),
            "file": str(item.get("file", "")),
            "line": int(item.get("line") or 0),
            "title": str(item.get("title", ""))[:120],
            "detail": str(item.get("detail", "")),
            "fix": str(item.get("fix", "")),
            "source": "ai",
        })
    return out


def audit(path: str | Path) -> dict:
    """Full pass: local rule scan + AI findings merged into one report."""
    report = scanner.scan_code_path(path)
    found = [{"severity": f["severity"], "file": f["file"], "line": f["line"],
              "title": f"[{f['rule']}] {f['message']}", "detail": f.get("excerpt", ""),
              "fix": "", "source": "local"}
             for f in report.get("findings", [])]
    try:
        found.extend(ai_findings(path, report))
    except Exception as exc:
        db.log("warning", "audit", f"AI findings skipped: {exc}")
    order = {"high": 0, "medium": 1, "low": 2}
    found.sort(key=lambda f: order.get(f["severity"], 3))
    report["audit_findings"] = found
    return report


def propose_patch(path: str | Path, finding: dict) -> str:
    """Ask Gemini for a unified diff fixing the finding."""
    root = Path(path)
    target = root / finding.get("file", "")
    code = ""
    if target.exists() and target.is_file():
        code = target.read_text(encoding="utf-8", errors="ignore")[:12000]
    prompt = (
        "Produce a unified diff fixing this issue in the project below. "
        "Reply with ONLY the diff (--- / +++ / @@ hunks, paths relative to "
        f"the project root, the file is '{finding.get('file','')}'). "
        "No prose, no markdown fences.\n\n"
        f"ISSUE: {finding.get('title','')} - {finding.get('detail','')}\n"
        f"SUGGESTED FIX: {finding.get('fix','')}\n\n"
        f"FILE CONTENT:\n{code}")
    text, _model = ai._generate(prompt, timeout_ms=90_000)
    text = re.sub(r"^```[a-z]*\n|```$", "", text.strip(), flags=re.M)
    return text


def apply_diff(path: str | Path, diff_text: str) -> list[str]:
    """Conservative unified-diff applier - hunks must match context lines.
    Backs every touched file into .lotus-backup/<ts>/ first."""
    root = Path(path)
    file_re = re.compile(r"^--- (?:a/)?(\S+)\n\+\+\+ (?:b/)?(\S+)", re.M)
    applied = []
    sections = re.split(r"(?m)^--- ", diff_text)
    for section in sections[1:]:
        section = "--- " + section
        m = file_re.search(section)
        if not m:
            continue
        rel = m.group(2).split("\t")[0].strip()
        if rel == "/dev/null":
            continue
        target = (root / rel).resolve()
        if not str(target).startswith(str(root.resolve())) or not target.exists():
            raise RuntimeError(f"patch target outside project or missing: {rel}")
        lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        out, cursor = [], 0
        for hunk in re.finditer(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@\n((?s:.*?))(?=@@ |--- |\Z)", section):
            start = int(hunk.group(1)) - 1
            body = [l for l in hunk.group(2).splitlines()]
            ctx = [l[1:] for l in body if l.startswith(" ") or l.startswith("-")]
            pos = -1
            for i in range(max(0, start - 40), min(len(lines), start + 40) + 1):
                if [l for l in lines[i:i + len(ctx)] if True][:len(ctx)] == ctx:
                    pos = i
                    break
            if pos < 0:
                pos = start if start <= len(lines) else len(lines)
            out.extend(lines[cursor:pos])
            for l in body:
                if l.startswith("-"):
                    continue
                if l.startswith("+") or l.startswith(" "):
                    out.append(l[1:])
            cursor = pos + len(ctx)
        out.extend(lines[cursor:])
        backup = root / ".lotus-backup" / str(int(time.time())) / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
        target.write_text("\n".join(out) + "\n", encoding="utf-8")
        applied.append(rel)
    return applied
