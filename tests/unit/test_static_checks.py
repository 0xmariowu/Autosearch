"""G1-T4: pytest wrappers for G1 static validation scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "validate"


def _run_script(script: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def test_version_consistency():
    """All 4 version files must agree on the same version string."""
    code, output = _run_script(SCRIPTS / "check_version_consistency.py")
    assert code == 0, f"Version mismatch:\n{output}"


def test_skill_format_compliance():
    """All SKILL.md files must have # Quality Bar and be <= 500 lines."""
    code, output = _run_script(SCRIPTS / "check_skill_format.py")
    assert code == 0, f"SKILL.md format violations:\n{output}"


def test_channel_experience_init_script_exists():
    """The init_channel_experience.sh script must exist and be executable.

    Note: experience/patterns.jsonl files are runtime data, not committed to git.
    Users run scripts/validate/init_channel_experience.sh after cloning.
    """
    script = Path(__file__).resolve().parents[2] / "scripts/validate/init_channel_experience.sh"
    assert script.exists(), f"init_channel_experience.sh not found at {script}"

    if sys.platform == "win32":
        return  # bash not available on Windows — skip execution check

    result = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        cwd=str(script.parents[2]),
    )
    assert result.returncode == 0, f"init script failed:\n{result.stderr}"
