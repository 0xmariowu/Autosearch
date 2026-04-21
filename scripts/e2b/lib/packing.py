from __future__ import annotations

import fnmatch
import tarfile
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDES = {".git", ".mypy_cache", ".pytest_cache", ".venv", "__pycache__", "*.egg-info"}


def pack_directory(
    source_dir: Path,
    destination_tarball: Path,
    exclude: Iterable[str] | None = None,
) -> Path:
    """Create a gzipped tarball for later sandbox upload, skipping common cache directories."""
    excluded = set(DEFAULT_EXCLUDES)
    if exclude is not None:
        excluded.update(exclude)

    source_dir = source_dir.expanduser().resolve()
    destination_tarball = destination_tarball.expanduser()
    if not source_dir.is_dir():
        raise ValueError(f"Source directory not found: {source_dir}")
    destination_tarball.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(destination_tarball, "w:gz") as archive:
        for path in sorted(source_dir.rglob("*")):
            relative = path.relative_to(source_dir)
            if _is_excluded(relative, excluded):
                continue
            archive.add(path, arcname=relative)

    return destination_tarball


def _is_excluded(relative_path: Path, patterns: set[str]) -> bool:
    parts = relative_path.parts
    return any(fnmatch.fnmatch(part, pattern) for part in parts for pattern in patterns)
