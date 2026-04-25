import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = ROOT / "scripts" / "install.sh"


def run_install_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALL_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_install_script_dry_run_accepts_valid_version() -> None:
    result = run_install_script("--dry-run", "--version", "2026.04.25.1")
    combined_output = result.stdout + result.stderr

    assert result.returncode == 0, combined_output
    assert "autosearch==2026.04.25.1" in combined_output


def test_install_script_rejects_injected_version_without_execution() -> None:
    result = run_install_script(
        "--dry-run",
        "--version",
        "2026.04.25.1'; echo PWNED >&2; #'",
    )
    combined_output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "PWNED" not in combined_output


def test_install_script_rejects_path_traversal_version() -> None:
    result = run_install_script("--dry-run", "--version", "../../etc/passwd")
    combined_output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "PEP 440-style version" in combined_output
