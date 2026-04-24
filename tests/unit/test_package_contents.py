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


def test_legacy_v1_modules_not_in_source_tree() -> None:
    """Plan §P2-1: the v1 high-level pipeline / FastAPI server / report
    synthesis modules were removed from the runtime package. Re-introducing
    them silently would expand the public API surface to include code that
    cannot satisfy the v2 contract."""
    forbidden = [
        ROOT / "autosearch" / "core" / "pipeline.py",
        ROOT / "autosearch" / "server",
        ROOT / "autosearch" / "synthesis",
    ]
    present = [p for p in forbidden if p.exists()]
    assert not present, (
        "legacy v1 modules reappeared in the source tree (plan §P2-1):\n"
        + "\n".join(f"  {p.relative_to(ROOT)}" for p in present)
        + "\nIf bringing one back, gate it behind an [project.optional-dependencies] "
        "extra and update this test to allowlist the path."
    )


def test_built_wheel_does_not_ship_legacy_v1_modules() -> None:
    """Companion to the source-tree check: catch a future PR that puts the
    legacy modules behind a build-time include glob without removing them
    from the source tree first."""
    dist = ROOT / "dist"
    wheels = sorted(dist.glob("autosearch-*.whl"))
    if not wheels:
        pytest.skip("no built wheel in dist/ — run `uv build --wheel` first")
    latest = wheels[-1]
    with zipfile.ZipFile(latest) as zf:
        names = zf.namelist()
    forbidden_prefixes = (
        "autosearch/core/pipeline",
        "autosearch/server/",
        "autosearch/synthesis/",
    )
    leaked = [n for n in names if n.startswith(forbidden_prefixes)]
    assert not leaked, f"{latest.name} still ships legacy v1 modules (plan §P2-1):\n" + "\n".join(
        f"  {n}" for n in leaked
    )


def test_no_channel_uses_legacy_experience_subdir_seed_path() -> None:
    """Plan §P2-2: bundled experience seed digests must live at
    `<skill>/experience.md`, NOT `<skill>/experience/experience.md`. The runtime
    loader (`autosearch.skills.experience.load_experience_digest`) only checks
    the top-level path, so seeds parked in the subdir variant were silently
    dead. Standardize on top-level."""
    channels_root = ROOT / "autosearch" / "skills" / "channels"
    offenders = sorted(
        channels_root.glob("*/experience/experience.md"),
    )
    assert not offenders, (
        "channel(s) still ship the legacy experience-subdir seed path; the "
        "loader will not see them. Move each to <skill>/experience.md "
        "(top-level):\n" + "\n".join(f"  {p.relative_to(ROOT)}" for p in offenders)
    )


def test_built_wheel_uses_only_top_level_experience_seed_path() -> None:
    """Companion: even if a future PR re-creates a `<skill>/experience/` dir
    locally, this guard catches it at the wheel layer (where setuptools'
    `**/*.md` glob would otherwise quietly include it)."""
    dist = ROOT / "dist"
    wheels = sorted(dist.glob("autosearch-*.whl"))
    if not wheels:
        pytest.skip("no built wheel in dist/ — run `uv build --wheel` first")
    latest = wheels[-1]
    with zipfile.ZipFile(latest) as zf:
        names = zf.namelist()
    pattern = re.compile(r"^autosearch/skills/channels/[^/]+/experience/experience\.md$")
    leaked = [n for n in names if pattern.match(n)]
    assert not leaked, (
        f"{latest.name} ships seed digest(s) at the legacy subdir path "
        "(plan §P2-2):\n" + "\n".join(f"  {n}" for n in leaked)
    )
