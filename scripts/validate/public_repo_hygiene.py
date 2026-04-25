#!/usr/bin/env python3
"""Verify public-repo hygiene invariants on git-tracked files.

Per public-repo-hygiene-plan F011. Complements gitleaks (which scans
content for secrets / codenames) by enforcing path-level rules:
files that should never be tracked at all.

Reports `path:line` and rule ID. Never prints the matched value.
Exit 0 on clean, 1 on any violation.

Usage:
    python scripts/validate/public_repo_hygiene.py [--tracked] [--paths-only]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    pattern: re.Pattern[str]
    allowlist_paths: tuple[re.Pattern[str], ...] = field(default_factory=tuple)


# Files that must never be tracked. Matched against the file path.
PATH_RULES: tuple[Rule, ...] = (
    Rule(
        id="tracked-handoff",
        description="HANDOFF.md must not be tracked (internal session-handoff state)",
        pattern=re.compile(r"^HANDOFF\.md$"),
    ),
    Rule(
        id="tracked-internal-dir",
        description="docs/{plans,proposals,spikes,channel-hunt,exec-plans}/ must not be tracked",
        pattern=re.compile(r"^docs/(plans|proposals|spikes|channel-hunt|exec-plans)/"),
    ),
    Rule(
        id="tracked-experience-jsonl",
        description="experience/**/*.jsonl must not be tracked (live runtime patterns)",
        pattern=re.compile(r"experience/.*\.jsonl$"),
    ),
    Rule(
        id="tracked-private-md",
        description="*.private.md and *.handoff.md must not be tracked",
        pattern=re.compile(r"\.(private|handoff)\.md$"),
    ),
    Rule(
        id="tracked-reports",
        description="reports/ must not be tracked (E2B per-run artifacts)",
        pattern=re.compile(r"^reports/"),
    ),
    Rule(
        id="tracked-ds-store",
        description=".DS_Store must not be tracked (macOS metadata)",
        pattern=re.compile(r"(^|/)\.DS_Store$"),
    ),
)


# Strings whose presence in tracked files indicates a hygiene leak.
CONTENT_RULES: tuple[Rule, ...] = (
    Rule(
        id="dangerous-permission-flag",
        description=(
            "`dangerously-skip-permissions` must not appear in published files "
            "(internal Claude Code shortcut, not for public docs)"
        ),
        pattern=re.compile(r"dangerously-skip-permissions"),
        allowlist_paths=(
            re.compile(r"^tests/.*\.(py|yaml|yml)$"),
            re.compile(r"^\.gitleaks\.toml$"),
            re.compile(r"^\.husky/"),
            re.compile(r"^\.github/workflows/"),
            re.compile(r"^scripts/validate/public_repo_hygiene\.py$"),
            # Hygiene docs that legitimately describe the rule by literal name.
            re.compile(r"^docs/internal-docs\.md$"),
            re.compile(r"^docs/public-repo-policy\.md$"),
            re.compile(r"^docs/security/hygiene-verify\.md$"),
        ),
    ),
)


def list_tracked_files() -> list[str]:
    """Return paths of every git-tracked file in the repo."""
    out = subprocess.run(  # noqa: S603 — known git binary
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def check_path_rules(files: list[str]) -> list[tuple[str, int, str]]:
    """Find tracked files that match any disallowed-path rule."""
    return [
        (path, 0, rule.id) for rule in PATH_RULES for path in files if rule.pattern.search(path)
    ]


def check_content_rules(files: list[str]) -> list[tuple[str, int, str]]:
    """Find lines in tracked files that match any disallowed-content rule."""
    violations: list[tuple[str, int, str]] = []
    for path in files:
        full = REPO_ROOT / path
        if not full.is_file():
            continue
        try:
            content = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for rule in CONTENT_RULES:
            if any(p.match(path) for p in rule.allowlist_paths):
                continue
            for line_no, line in enumerate(content.splitlines(), start=1):
                if rule.pattern.search(line):
                    violations.append((path, line_no, rule.id))
    return violations


def report(violations: list[tuple[str, int, str]]) -> None:
    rule_index = {r.id: r for r in (*PATH_RULES, *CONTENT_RULES)}
    by_rule: dict[str, list[tuple[str, int]]] = {}
    for path, line_no, rule_id in violations:
        by_rule.setdefault(rule_id, []).append((path, line_no))

    for rule_id in sorted(by_rule):
        rule = rule_index[rule_id]
        print(f"\n[{rule_id}] {rule.description}")
        for path, line_no in by_rule[rule_id]:
            print(f"  {path}:{line_no}" if line_no else f"  {path}")

    file_count = len({v[0] for v in violations})
    print(f"\n{len(violations)} violation(s) across {file_count} file(s).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--tracked",
        action="store_true",
        help="Scan git-tracked files (default behavior; flag is for explicit clarity)",
    )
    parser.add_argument(
        "--paths-only",
        action="store_true",
        help="Run only path-level rules; skip content scan",
    )
    args = parser.parse_args(argv)
    _ = args.tracked  # tracked is the only mode for now

    files = list_tracked_files()
    violations = check_path_rules(files)
    if not args.paths_only:
        violations += check_content_rules(files)

    if not violations:
        print(f"OK: {len(files)} tracked files clean — no hygiene violations.")
        return 0

    report(violations)
    return 1


if __name__ == "__main__":
    sys.exit(main())
