#!/usr/bin/env python3
"""Verify the pyproject version has not already been claimed.

Checks:
  - local git tag v<version>, if present, points at the current HEAD
  - PyPI releases for autosearch do not already include the normalized version

Network verification failures exit with UNVERIFIED so callers can decide
whether to block or warn.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[2]
PYPI_URL = "https://pypi.org/pypi/autosearch/json"
OK = 0
CONFLICT = 1
UNVERIFIED = 2


def read_pyproject_version(root: Path | None = None) -> str:
    root = ROOT if root is None else root
    with (root / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    try:
        return str(data["project"]["version"])
    except KeyError as exc:
        raise ValueError("version not found in pyproject.toml [project]") from exc


def normalize_version(version: str) -> str:
    return str(Version(version))


def _git(args: list[str], root: Path | None = None) -> subprocess.CompletedProcess[str]:
    root = ROOT if root is None else root
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def check_local_tag(version: str, root: Path | None = None) -> int:
    root = ROOT if root is None else root
    tag = f"v{version}"
    tag_list = _git(["tag", "-l", tag], root)
    if tag_list.returncode != 0:
        print(f"FAIL: could not list git tags: {tag_list.stderr.strip()}", file=sys.stderr)
        return CONFLICT

    if tag_list.stdout.strip() != tag:
        return OK

    head = _git(["rev-parse", "HEAD"], root)
    tag_commit = _git(["rev-list", "-n", "1", tag], root)
    if head.returncode != 0 or tag_commit.returncode != 0:
        detail = (head.stderr or tag_commit.stderr).strip()
        print(f"FAIL: could not resolve git tag {tag}: {detail}", file=sys.stderr)
        return CONFLICT

    head_sha = head.stdout.strip()
    tag_sha = tag_commit.stdout.strip()
    if tag_sha != head_sha:
        print(
            f"FAIL: version {version} local tag {tag} points to {tag_sha}, "
            f"not current HEAD {head_sha}",
            file=sys.stderr,
        )
        return CONFLICT

    return OK


def _fetch_pypi_releases() -> dict[str, Any]:
    with urllib.request.urlopen(PYPI_URL, timeout=10) as response:
        return json.loads(response.read().decode("utf-8")).get("releases", {})


def check_pypi(version: str, *, allow_existing: bool = False) -> int:
    try:
        normalized = normalize_version(version)
        releases = _fetch_pypi_releases()
    except Exception as exc:
        print(
            f"WARN: could not verify version {version} on PyPI: {exc}",
            file=sys.stderr,
        )
        return UNVERIFIED

    claimed_versions: set[str] = set()
    for release_version in releases:
        try:
            claimed_versions.add(normalize_version(release_version))
        except InvalidVersion:
            continue

    if normalized in claimed_versions:
        if allow_existing:
            print(f"OK: version {version} already on PyPI (allowed)")
            return OK
        print(f"FAIL: version {version} already on PyPI", file=sys.stderr)
        return CONFLICT

    return OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("local", "pypi", "full"),
        default="local",
        help="local checks only git tags; pypi checks only PyPI; full checks both",
    )
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="allow an already-published PyPI version; intended for tests only",
    )
    args = parser.parse_args(argv)

    try:
        version = read_pyproject_version()
        normalize_version(version)
    except Exception as exc:
        print(f"FAIL: could not read pyproject version: {exc}", file=sys.stderr)
        return CONFLICT

    if args.mode in {"local", "full"}:
        local_status = check_local_tag(version)
        if local_status != OK:
            return local_status

    if args.mode in {"pypi", "full"}:
        pypi_status = check_pypi(version, allow_existing=args.allow_existing)
        if pypi_status != OK:
            return pypi_status

    print(f"OK: version {version} not yet claimed")
    return OK


if __name__ == "__main__":
    sys.exit(main())
