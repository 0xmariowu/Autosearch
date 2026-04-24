#!/usr/bin/env python3
"""G1-T1: Verify all version files agree on the same version string.

Files checked:
  - pyproject.toml                     [project] version  → canonical (CalVer YYYY.MM.DD.N)
  - .claude-plugin/plugin.json         version            → must equal pyproject
  - .claude-plugin/marketplace.json    version            → must equal pyproject
  - CHANGELOG.md                       first ## heading   → must equal pyproject
  - npm/package.json                   version            → must equal `derive_npm_version(pyproject)`

NPM mapping: npm requires strict 3-part semver, and we don't republish the npm
package on intra-day pyproject bumps, so the daily counter is dropped:
  pyproject "2026.04.23.9"  →  npm "2026.4.23"
  pyproject "2026.04.23.1"  →  npm "2026.4.23"
Leading zeros are stripped (npm/semver rejects them).
A daily-counter bump in pyproject does NOT require touching npm/package.json.

Exit 0 if all agree, exit 1 if any differ.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_pyproject() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise ValueError("version not found in pyproject.toml")
    return m.group(1)


def _read_json_version(path: Path) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    v = data.get("version")
    if not v:
        raise ValueError(f"version not found in {path}")
    return str(v)


def _read_changelog() -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## (\S+)", text, re.MULTILINE)
    if not m:
        raise ValueError("no ## heading found in CHANGELOG.md")
    return m.group(1).strip(" —-")


def derive_npm_version(pyproject_version: str) -> str:
    """Map CalVer `YYYY.MM.DD.N` → npm-compatible 3-part semver `YYYY.M.DD`.

    Year/month/day leading zeros are stripped (semver forbids them).
    The daily counter `N` is intentionally dropped: the npm package is
    republished only when the date base changes, not on intra-day pyproject
    bumps. Users always get the latest base via `npm install autosearch-ai`.
    """
    parts = pyproject_version.split(".")
    if len(parts) != 4:
        raise ValueError(f"expected pyproject version as YYYY.MM.DD.N, got {pyproject_version!r}")
    year, month, day, _seq = parts
    return f"{int(year)}.{int(month)}.{int(day)}"


def main() -> int:
    sources: dict[str, str] = {}
    errors: list[str] = []

    for label, fn in [
        ("pyproject.toml", _read_pyproject),
        ("plugin.json", lambda: _read_json_version(ROOT / ".claude-plugin/plugin.json")),
        ("marketplace.json", lambda: _read_json_version(ROOT / ".claude-plugin/marketplace.json")),
        ("CHANGELOG.md", _read_changelog),
    ]:
        try:
            sources[label] = fn()
        except Exception as exc:
            errors.append(f"  {label}: {exc}")

    npm_path = ROOT / "npm" / "package.json"
    npm_version: str | None = None
    if npm_path.is_file():
        try:
            npm_version = _read_json_version(npm_path)
        except Exception as exc:
            errors.append(f"  npm/package.json: {exc}")

    if errors:
        print("ERROR reading version files:")
        print("\n".join(errors))
        return 1

    canonical = sources.get("pyproject.toml")
    versions = list(sources.values())
    all_match = canonical is not None and all(v == canonical for v in versions)

    if npm_version is not None:
        if canonical is None:
            all_match = False
        else:
            try:
                expected_npm = derive_npm_version(canonical)
            except ValueError as exc:
                print(f"FAIL: {exc}")
                return 1
            if npm_version != expected_npm:
                all_match = False

    if all_match:
        print(f"OK: all version files agree on {canonical}")
        if npm_version is not None:
            print(f"  npm/package.json: {npm_version} (derived from {canonical})")
        return 0

    print("FAIL: version mismatch detected")
    for label, v in sources.items():
        marker = "" if v == canonical else " ← DIFFERS"
        print(f"  {label}: {v}{marker}")
    if npm_version is not None and canonical is not None:
        expected = derive_npm_version(canonical)
        marker = "" if npm_version == expected else f" ← DIFFERS (expected {expected})"
        print(f"  npm/package.json: {npm_version}{marker}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
