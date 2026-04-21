"""Guard that `scripts/nightly-local.sh` keeps the invariants callers rely on:
executable bit set, `set -euo pipefail`, tarball path matches the
`tests/e2b/matrix.yaml` hardcoded upload path, and the secrets file is read
from `~/.config/ai-secrets.env` (overridable via `AUTOSEARCH_SECRETS_FILE`).
"""

from __future__ import annotations

import stat
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "nightly-local.sh"


def test_script_exists_and_is_executable():
    assert SCRIPT.is_file(), f"{SCRIPT} missing"
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "nightly-local.sh must be executable (+x for owner)"


def test_script_sets_strict_bash_flags():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in body, (
        "nightly-local.sh must fail fast — unset vars, command errors, pipe failures"
    )


def test_tarball_path_matches_matrix_upload():
    body = SCRIPT.read_text(encoding="utf-8")
    matrix = (REPO_ROOT / "tests" / "e2b" / "matrix.yaml").read_text(encoding="utf-8")
    assert "/tmp/autosearch-src.tar.gz" in body, (
        "nightly-local.sh must pack to /tmp/autosearch-src.tar.gz"
    )
    assert "/tmp/autosearch-src.tar.gz" in matrix, (
        "matrix.yaml must agree on the tarball path the runner ships"
    )


def test_script_reads_secrets_file_path_from_env():
    body = SCRIPT.read_text(encoding="utf-8")
    assert "AUTOSEARCH_SECRETS_FILE" in body, (
        "nightly-local.sh must allow overriding secrets file location via env"
    )
