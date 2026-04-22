"""Audit compliance tests — repo-level security and hygiene checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_NOREPLY_ALLOWLIST = (
    "noreply.github.com",
    "users.noreply.github.com",
    "github-actions[bot]",
    "dependabot[bot]",
    "action@github.com",
)


def test_security_md_exists():
    assert (REPO_ROOT / "SECURITY.md").is_file(), "SECURITY.md missing from repo root"


def test_gitleaks_config_exists():
    assert (REPO_ROOT / ".gitleaks.toml").is_file(), ".gitleaks.toml missing from repo root"


def test_no_personal_email_in_git_log():
    result = subprocess.run(
        ["git", "log", "--all", "--format=%ae"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    personal = [
        email
        for email in result.stdout.splitlines()
        if email.strip() and not any(allowed in email for allowed in _NOREPLY_ALLOWLIST)
    ]
    assert not personal, (
        f"Personal email(s) found in git history: {personal}\n"
        "Use noreply GitHub email for all commits."
    )


def test_no_personal_paths_in_tracked_files():
    ls = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    _SKIP_EXT = {".sh", ".json", ".toml", ".md", ".yaml", ".yml", ".txt", ".lock"}
    _SKIP_DIRS = ("tests/", "scripts/", ".husky/")
    tracked = [
        f
        for f in ls.stdout.splitlines()
        if not any(f.startswith(d) for d in _SKIP_DIRS) and Path(f).suffix not in _SKIP_EXT
    ]
    hits = []
    for rel_path in tracked:
        full = REPO_ROOT / rel_path
        if not full.is_file():
            continue
        try:
            content = full.read_text(errors="ignore")
        except OSError:
            continue
        if "/Users/" in content:
            hits.append(rel_path)
    assert not hits, (
        f"Personal path '/Users/' found in tracked files: {hits}\n"
        "Use relative paths or environment variables instead."
    )
