"""Plan §Gate G: published package contents match intentional policy.

Three checks at the policy layer (cheap, run on every release-gate invocation):

1. runtime dependencies must not pull in test/lint tools — those belong in the
   `dev` optional extra. A misplaced `pytest` or `ruff` bloats every install.
2. the setuptools package-data glob must not include `*.jsonl` — accumulated
   skill `experience/patterns.jsonl` is runtime state, not seed data, and
   shipping it leaks every author's prior search history into the wheel.
3. the cross-file version pins agree (single source of truth: pyproject;
   mirrored to plugin.json, marketplace.json, CHANGELOG, npm).

A best-effort artifact check also runs against the latest built wheel in
`dist/` if one exists — it skips when no wheel has been built so this test
stays fast in --quick mode.
"""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"


def _read_pyproject() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def test_runtime_deps_exclude_test_and_lint_tools() -> None:
    text = _read_pyproject()
    match = re.search(
        r"^\s*dependencies\s*=\s*\[(?P<body>.*?)\]",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match, "[project].dependencies block not found in pyproject.toml"
    runtime_block = match.group("body").lower()
    forbidden = ("pytest", "ruff", "black", "mypy", "pyright")
    leaked = [tool for tool in forbidden if tool in runtime_block]
    assert not leaked, (
        "runtime dependencies must not contain dev/test tools "
        f"(found: {leaked}); move them to [project.optional-dependencies].dev"
    )


def test_package_data_excludes_runtime_jsonl() -> None:
    text = _read_pyproject()
    match = re.search(
        r"\[tool\.setuptools\.package-data\](?P<body>.*?)(?=^\[|\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match, "[tool.setuptools.package-data] section not found"
    body = match.group("body")
    assert ".jsonl" not in body, (
        "package-data must not glob *.jsonl — accumulated runtime "
        "patterns.jsonl files would leak into the wheel"
    )


def test_version_files_consistent() -> None:
    script = ROOT / "scripts" / "validate" / "check_version_consistency.py"
    assert script.is_file(), f"version check script missing: {script}"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, (
        "version files drifted across pyproject / plugin.json / "
        "marketplace.json / CHANGELOG / npm:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_built_wheel_does_not_ship_runtime_patterns_jsonl() -> None:
    dist = ROOT / "dist"
    wheels = sorted(dist.glob("autosearch-*.whl"))
    if not wheels:
        pytest.skip("no built wheel in dist/ — run `uv build --wheel` first")
    latest = wheels[-1]
    with zipfile.ZipFile(latest) as zf:
        names = zf.namelist()
    leaked = [n for n in names if n.endswith("patterns.jsonl")]
    assert not leaked, (
        f"{latest.name} ships runtime patterns.jsonl files (must be excluded "
        "from package-data):\n" + "\n".join(f"  {n}" for n in leaked)
    )
