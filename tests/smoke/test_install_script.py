import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.smoke.conftest import smoke_env


ROOT = Path(__file__).resolve().parents[2]
NPM_DIR = ROOT / "npm"
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


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only fake bash installer shim")
def test_install_then_run_e2e_smoke(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_bash = fake_bin / "bash"
    fake_bash.write_text(
        "#!/bin/sh\n"
        'mkdir -p "$HOME/.local/bin"\n'
        "cat > \"$HOME/.local/bin/autosearch\" <<'EOF'\n"
        "#!/bin/sh\n"
        'echo "e2e autosearch $*"\n'
        "exit 0\n"
        "EOF\n"
        'chmod +x "$HOME/.local/bin/autosearch"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    fake_bash.chmod(0o755)

    env = smoke_env(home=home)
    env["PATH"] = os.pathsep.join([str(fake_bin), "/usr/bin", "/bin"])

    result = subprocess.run(
        [
            shutil.which("node") or "node",
            str(NPM_DIR / "bin" / "autosearch-ai.js"),
            "--yes",
            "doctor",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert "e2e autosearch doctor" in result.stdout
