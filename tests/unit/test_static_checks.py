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


def test_channel_experience_dirs():
    """Every channel with SKILL.md must have experience/patterns.jsonl initialized."""
    from autosearch.skills.loader import load_all

    channels_root = Path(__file__).resolve().parents[2] / "autosearch/skills/channels"
    specs = load_all(channels_root)
    missing = [
        spec.name
        for spec in specs
        if not (spec.skill_dir / "experience" / "patterns.jsonl").exists()
    ]
    assert not missing, f"Channels missing experience/patterns.jsonl: {missing}"
