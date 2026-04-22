#!/usr/bin/env python3
"""G1-T1: Verify all four version files agree on the same version string.

Files checked:
  - pyproject.toml         [project] version
  - .claude-plugin/plugin.json  version
  - .claude-plugin/marketplace.json  version
  - CHANGELOG.md           first ## heading version

Exit 0 if all agree, exit 1 if any differ.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_pyproject() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise ValueError("version not found in pyproject.toml")
    return m.group(1)


def _read_json_version(path: Path) -> str:
    data = json.loads(path.read_text())
    v = data.get("version")
    if not v:
        raise ValueError(f"version not found in {path}")
    return str(v)


def _read_changelog() -> str:
    text = (ROOT / "CHANGELOG.md").read_text()
    m = re.search(r"^## (\S+)", text, re.MULTILINE)
    if not m:
        raise ValueError("no ## heading found in CHANGELOG.md")
    return m.group(1).strip(" —-")


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

    if errors:
        print("ERROR reading version files:")
        print("\n".join(errors))
        return 1

    versions = list(sources.values())
    all_match = all(v == versions[0] for v in versions)

    if all_match:
        print(f"OK: all version files agree on {versions[0]}")
        return 0

    print("FAIL: version mismatch detected")
    for label, v in sources.items():
        marker = "" if v == versions[0] else " ← DIFFERS"
        print(f"  {label}: {v}{marker}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
