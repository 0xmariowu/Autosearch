#!/usr/bin/env python3
"""G1-T2: Verify all SKILL.md files meet format requirements.

Checks:
  - Has '# Quality Bar' section (CLAUDE.md rule 18)
  - Body length <= 500 lines
  - Frontmatter has non-empty 'name' field

Exit 0 if all pass, exit 1 if any violations found.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "autosearch" / "skills"
MAX_LINES = 500
REQUIRED_SECTION = "# Quality Bar"


def check_skill_md(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"cannot read: {exc}"]

    lines = text.splitlines()

    # Check line count
    if len(lines) > MAX_LINES:
        violations.append(f"too long: {len(lines)} lines (max {MAX_LINES})")

    # Check Quality Bar section
    if REQUIRED_SECTION not in text:
        violations.append(f"missing '{REQUIRED_SECTION}' section")

    # Check name in frontmatter (frontmatter may not start at line 0)
    has_name = False
    fence_count = 0
    in_frontmatter = False
    for line in lines:
        if line.strip() == "---":
            fence_count += 1
            if fence_count == 1:
                in_frontmatter = True
                continue
            if fence_count == 2:
                break
        if in_frontmatter and line.startswith("name:"):
            val = line.split(":", 1)[1].strip().strip('"').strip("'")
            if val:
                has_name = True
    if not has_name:
        violations.append("missing or empty 'name' in frontmatter")

    return violations


def main() -> int:
    all_skill_mds = sorted(SKILLS_ROOT.rglob("SKILL.md"))
    if not all_skill_mds:
        print("ERROR: no SKILL.md files found under", SKILLS_ROOT)
        return 1

    violations_by_file: dict[str, list[str]] = {}
    for path in all_skill_mds:
        violations = check_skill_md(path)
        if violations:
            rel = str(path.relative_to(ROOT))
            violations_by_file[rel] = violations

    if not violations_by_file:
        print(f"OK: all {len(all_skill_mds)} SKILL.md files pass format checks")
        return 0

    print(f"FAIL: {len(violations_by_file)} SKILL.md file(s) have violations:\n")
    for path, violations in violations_by_file.items():
        print(f"  {path}:")
        for v in violations:
            print(f"    - {v}")
    print(f"\n{len(all_skill_mds) - len(violations_by_file)}/{len(all_skill_mds)} files pass")
    return 1


if __name__ == "__main__":
    sys.exit(main())
