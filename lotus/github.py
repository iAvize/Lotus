"""GitHub repository scanning for Lotus beta.

This downloads a repository snapshot through the GitHub API and runs the local
code scanner over it. Pull requests and automatic vulnerability rewrites are
roadmap items; beta scans are read-only.
"""
from __future__ import annotations

import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import config, db, scanner


def parse_github_repo(value: str) -> tuple[str, str]:
    value = value.strip()
    if not value:
        raise ValueError("Enter a GitHub repository URL or owner/repo.")

    if "/" in value and not value.startswith(("http://", "https://", "git@")):
        parts = [p for p in value.split("/") if p]
        if len(parts) >= 2:
            return parts[-2], parts[-1].removesuffix(".git")

    if value.startswith("git@github.com:"):
        path = value.split("git@github.com:", 1)[1]
    elif value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError("Only github.com repositories are supported in beta.")
        path = parsed.path.strip("/")
    else:
        raise ValueError("Use a github.com URL or owner/repo.")

    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("Could not find owner/repo in that GitHub URL.")
    return parts[0], parts[1].removesuffix(".git")


def _headers(token: str = "") -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Lotus-Beta",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _download_zip(owner: str, repo: str, branch: str, token: str, dest: Path) -> None:
    url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{branch}"
    with requests.get(url, headers=_headers(token), stream=True, timeout=60) as response:
        response.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)


def scan_github_repository(value: str, token: str | None = None, max_files: int = 5000) -> dict:
    owner, repo = parse_github_repo(value)
    token = (token if token is not None else config.get_github_token()).strip()

    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    repo_response = requests.get(api_url, headers=_headers(token), timeout=30)
    repo_response.raise_for_status()
    repo_info = repo_response.json()
    branch = repo_info.get("default_branch") or "main"

    with tempfile.TemporaryDirectory(prefix="lotus-repo-") as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "repo.zip"
        _download_zip(owner, repo, branch, token, zip_path)

        extract_dir = tmp_path / "repo"
        extract_dir.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

        roots = [p for p in extract_dir.iterdir() if p.is_dir()]
        scan_root = roots[0] if len(roots) == 1 else extract_dir

        report = scanner.scan_code_path(scan_root, max_files=max_files)
        report.update({
            "repo": f"{owner}/{repo}",
            "branch": branch,
            "private": bool(repo_info.get("private")),
            "html_url": repo_info.get("html_url", f"https://github.com/{owner}/{repo}"),
        })
        db.log("info", "github", f"scanned {owner}/{repo}@{branch}: {report['findings_total']} findings")
        return report
