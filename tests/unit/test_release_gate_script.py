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

    bad = subprocess.run([str(SCRIPT), "--no-such-flag"], capture_output=True, text=True)
    assert bad.returncode != 0
