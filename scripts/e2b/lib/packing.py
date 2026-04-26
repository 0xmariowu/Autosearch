from __future__ import annotations

import fnmatch
import subprocess
import tarfile
from pathlib import Path
from typing import Iterable


_DENIED_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.env",
    "*.key",
    "*.pem",
    "experience/*",
    "evidence/*",
    "tests/integration/sessions/*",
)


def _is_denied(relative_path: Path) -> bool:
    """Return True if relative_path matches a denylist pattern.

    Denylist takes precedence over git's tracked-file set: even if a sensitive
    file (.env, an SSH key, evidence dump) is intentionally committed, it must
    never enter a sandbox tarball.
    """
    rel_str = relative_path.as_posix()
    for pattern in _DENIED_PATTERNS:
        if "/" in pattern:
            if fnmatch.fnmatch(rel_str, pattern):
                return True
        else:
            if any(fnmatch.fnmatch(part, pattern) for part in relative_path.parts):
                return True
    return False


def _list_tracked_files(source_dir: Path) -> list[Path]:
    """Return absolute paths of all files git tracks under source_dir.

    Uses ``git -C <source_dir> ls-files -z`` so paths with newlines / spaces
    are safe. The list reflects git index state — newly added files are
    included, gitignored files are not, deleted-but-staged files appear.
    Raises RuntimeError if source_dir is not inside a git repository.
    """
    result = subprocess.run(
        ["git", "-C", str(source_dir), "ls-files", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git ls-files failed in {source_dir}: {stderr}")
    raw = result.stdout.decode("utf-8", errors="replace")
    relative_names = [name for name in raw.split("\0") if name]
    return [source_dir / name for name in relative_names]


def _run_secret_scan(source_dir: Path) -> None:
    """Run gitleaks against ``source_dir``; raise if any leak is detected.

    Uses ``gitleaks detect --no-git`` so it scans the on-disk file content
    (matching what we are about to tar), not just commit history. Honors a
    repo-root ``.gitleaks.toml`` if present.

    If gitleaks is not installed, the scan is skipped with a printed
    warning. Callers that REQUIRE the scan to run (e.g. e2b-nightly
    workflow that ships tarballs to external sandboxes) MUST install
    gitleaks themselves and set ``AUTOSEARCH_PACKING_REQUIRE_SECRET_SCAN=1``
    — that flag flips the missing-binary case into a hard error. Default-
    off keeps the main-CI test runner (which does not pack anything for
    upload) from being blocked by a missing optional binary.
    """
    import os
    import shutil

    if shutil.which("gitleaks") is None:
        if os.environ.get("AUTOSEARCH_PACKING_REQUIRE_SECRET_SCAN") == "1":
            raise RuntimeError(
                "secret-scan: aborted — gitleaks is required "
                "(AUTOSEARCH_PACKING_REQUIRE_SECRET_SCAN=1) but not installed"
            )
        print("[packing] secret-scan: skipped (gitleaks not installed)")
        return

    cmd = [
        "gitleaks",
        "detect",
        "--no-git",
        "--source",
        str(source_dir),
    ]
    config_path = source_dir / ".gitleaks.toml"
    if config_path.is_file():
        cmd.extend(["--config", str(config_path)])

    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip().splitlines()[-10:]
        joined = "\n".join(details)
        raise RuntimeError("secret-scan: aborted — gitleaks detected one or more leaks:\n" + joined)
    print("[packing] secret-scan: pass")


def pack_directory(
    source_dir: Path,
    destination_tarball: Path,
    exclude: Iterable[str] | None = None,
) -> Path:
    """Create a gzipped tarball of git-tracked files for later sandbox upload."""
    del exclude  # backward-compat: accepted but ignored — git tracks the file set now.

    source_dir = source_dir.expanduser().resolve()
    destination_tarball = destination_tarball.expanduser()
    if not source_dir.is_dir():
        raise ValueError(f"Source directory not found: {source_dir}")
    destination_tarball.parent.mkdir(parents=True, exist_ok=True)

    _run_secret_scan(source_dir)

    with tarfile.open(destination_tarball, "w:gz") as archive:
        for path in sorted(_list_tracked_files(source_dir)):
            relative = path.relative_to(source_dir)
            if _is_denied(relative):
                continue
            archive.add(path, arcname=relative)

    return destination_tarball
