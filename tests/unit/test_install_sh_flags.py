"""Plan §P1-7: scripts/install.sh must support --dry-run, --no-init, and
--version flags so users can preview the install, skip the trailing
`autosearch init`, or pin a specific release.

These flags are the contract for enterprise users who can't pipe an unknown
remote script straight into bash. A future PR that drops them silently
would break that audit-trail / unattended-install workflow.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


INSTALL_SH = Path(__file__).resolve().parents[2] / "scripts" / "install.sh"


def _run(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALL_SH), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_install_sh_passes_bash_syntax_check() -> None:
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_SH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"install.sh has shell syntax errors:\n{result.stderr}"


def test_help_lists_supported_flags() -> None:
    result = _run("--help")
    assert result.returncode == 0, f"--help should exit 0, got {result.returncode}"
    for flag in ("--dry-run", "--no-init", "--version"):
        assert flag in result.stdout, f"--help output missing {flag!r}:\n{result.stdout}"


def test_dry_run_does_not_invoke_install_commands() -> None:
    result = _run("--dry-run")
    assert result.returncode == 0, f"dry-run failed: stderr={result.stderr}"
    assert "DRY RUN" in result.stdout
    assert "[dry-run]" in result.stdout, "expected at least one [dry-run] prefixed line"


def test_dry_run_with_no_init_announces_skip() -> None:
    result = _run("--dry-run", "--no-init")
    assert result.returncode == 0
    assert "skip" in result.stdout.lower() and "autosearch init" in result.stdout, (
        "--no-init should announce that it skips the init step"
    )


def test_dry_run_with_version_pins_package_spec() -> None:
    result = _run("--dry-run", "--version", "2026.04.24.1")
    assert result.returncode == 0
    assert "autosearch==2026.04.24.1" in result.stdout, (
        "--version should propagate to the install command's package spec; "
        f"output:\n{result.stdout}"
    )


def test_unknown_flag_is_rejected() -> None:
    result = _run("--definitely-not-a-flag")
    assert result.returncode != 0, "unknown flag must exit non-zero"
    assert "unknown flag" in result.stderr.lower() or "unknown flag" in result.stdout.lower()


def test_install_persists_path_when_not_in_original(tmp_path: Path) -> None:
    profile = tmp_path / ".zshrc"
    profile.write_text("# existing profile\n", encoding="utf-8")

    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["PATH"] = "/usr/bin:/bin"
    env["SHELL"] = "/bin/zsh"

    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--check-path-persistence"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    expected_line = 'export PATH="$HOME/.local/bin:$PATH"'
    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert expected_line in profile.read_text(encoding="utf-8")

    already_configured_home = tmp_path / "already-configured"
    already_configured_home.mkdir()
    already_configured_profile = already_configured_home / ".zshrc"
    original_profile = "# existing profile\n"
    already_configured_profile.write_text(original_profile, encoding="utf-8")

    env["HOME"] = str(already_configured_home)
    env["PATH"] = os.pathsep.join(
        [str(already_configured_home / ".local" / "bin"), "/usr/bin", "/bin"]
    )

    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--check-path-persistence"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert already_configured_profile.read_text(encoding="utf-8") == original_profile
