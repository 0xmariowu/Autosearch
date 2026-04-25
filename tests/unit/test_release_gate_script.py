"""Smoke pin for scripts/release-gate.sh.

The script is the single command we expect a release manager to run before
cutting a release. We pin its surface so renames/relocations don't slip past
review.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "release-gate.sh"


def test_release_gate_script_exists_and_is_executable() -> None:
    assert SCRIPT.is_file(), f"{SCRIPT} missing"
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, f"{SCRIPT} not executable"


def test_release_gate_script_supports_quick_and_help_flags() -> None:
    """--help should print the docstring header and exit 0; bad flag rejects."""
    help_out = subprocess.run(
        [str(SCRIPT), "--help"], capture_output=True, text=True, env={**os.environ}
    )
    assert help_out.returncode == 0
    body = help_out.stdout + help_out.stderr
    assert "release-gate.sh" in body
    assert "--quick" in body
    assert "--pypi" in body

    bad = subprocess.run([str(SCRIPT), "--no-such-flag"], capture_output=True, text=True)
    assert bad.returncode != 0


def test_release_workflow_invokes_release_gate_and_validator() -> None:
    """release.yml must run both `check_version_consistency.py` and
    `release-gate.sh` so a tag push can't silently publish a drifted release.
    Pin the wiring textually so a refactor that drops one of them shows up
    in code review."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "check_version_consistency.py" in workflow, (
        "release workflow no longer runs check_version_consistency.py"
    )
    assert "check_version_uniqueness.py" in workflow or "--pypi" in workflow, (
        "release workflow no longer runs version uniqueness checks"
    )
    assert "release-gate.sh" in workflow, "release workflow no longer runs release-gate.sh"
    assert "--skip-existing" not in workflow, "PyPI upload must fail loudly on duplicates"
    assert "needs: [build, publish-pypi]" in workflow
    assert "if: needs.publish-pypi.result == 'success'" in workflow
