import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "npm" / "bin" / "autosearch-ai.js"
NODE = shutil.which("node")

pytestmark = [
    pytest.mark.skipif(os.name == "nt", reason="POSIX-only permission shims"),
    pytest.mark.skipif(NODE is None, reason="node is required for npm wrapper tests"),
]


def test_post_install_autosearch_permission_error_returns_nonzero(
    tmp_path: Path,
) -> None:
    assert NODE is not None
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
        'echo "unexpected autosearch invocation" >&2\n'
        "exit 2\n"
        "EOF\n"
        'chmod 0644 "$HOME/.local/bin/autosearch"\n'
        "exit 0\n",
        encoding="utf-8",
    )
    fake_bash.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = os.pathsep.join([str(fake_bin), "/usr/bin", "/bin"])

    result = subprocess.run(
        [NODE, str(WRAPPER), "--yes", "doctor"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "permission denied" in result.stderr.lower()
    assert "execute permission" in result.stderr.lower()


def test_installer_permission_error_returns_nonzero(tmp_path: Path) -> None:
    assert NODE is not None
    home = tmp_path / "home"
    home.mkdir()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_bash = fake_bin / "bash"
    fake_bash.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_bash.chmod(0o644)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = str(fake_bin)

    result = subprocess.run(
        [NODE, str(WRAPPER), "--yes", "doctor"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "permission denied" in result.stderr.lower()
    assert "installer command" in result.stderr.lower()
