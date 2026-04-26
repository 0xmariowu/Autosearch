#!/usr/bin/env python3
"""G7-T1: Pre-release checklist — runs all fast checks before v1.0 tag.

Usage: python scripts/validate/pre_release_check.py
Exit 0 = all checks pass. Exit 1 = one or more fail.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "validate"

CheckFn = Callable[[], tuple[bool, str]]
AdvisoryCheckFn = Callable[..., tuple[bool, str]]


def _run(label: str, cmd: list[str]) -> tuple[bool, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    ok = result.returncode == 0
    out = (result.stdout + result.stderr).strip()
    return ok, out


def _check_version_consistency() -> tuple[bool, str]:
    ok, out = _run("version", [sys.executable, str(SCRIPTS / "check_version_consistency.py")])
    return ok, out.splitlines()[0] if out else "?"


def _check_skill_format() -> tuple[bool, str]:
    ok, out = _run("skill_format", [sys.executable, str(SCRIPTS / "check_skill_format.py")])
    return ok, out.splitlines()[0] if out else "?"


def _check_experience_dirs() -> tuple[bool, str]:
    channels_root = ROOT / "autosearch" / "skills" / "channels"
    patterns_files = list(channels_root.rglob("patterns.jsonl"))
    skill_dirs = [d for d in channels_root.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
    missing = [d.name for d in skill_dirs if not (d / "experience" / "patterns.jsonl").exists()]
    if missing:
        return False, f"{len(missing)} channels missing experience/patterns.jsonl: {missing[:5]}"
    return True, f"all {len(patterns_files)} channel experience dirs initialized"


def _check_mcp_tools() -> tuple[bool, str]:
    os.environ["AUTOSEARCH_LLM_MODE"] = "dummy"
    ok, out = _run(
        "mcp_tools",
        [
            sys.executable,
            "-c",
            (
                "import os; os.environ['AUTOSEARCH_LLM_MODE']='dummy';"
                "from autosearch.mcp.server import create_server;"
                "s=create_server(); tools=[t.name for t in s._tool_manager.list_tools()];"
                "required=['doctor','list_channels','select_channels_tool','run_clarify','run_channel'];"
                "missing=[t for t in required if t not in tools];"
                "print(f'{len(tools)} tools registered');"
                "assert not missing, f'missing: {missing}'"
            ),
        ],
    )
    return ok, out.splitlines()[0] if out else "error"


def _current_head() -> tuple[bool, str]:
    ok, out = _run("git_head", ["git", "rev-parse", "HEAD"])
    if not ok:
        return False, f"could not determine HEAD commit: {out}"
    return True, out.splitlines()[0].strip()


def _stats_sort_key(path: Path, stats: dict[str, object]) -> tuple[str, float]:
    generated_at = stats.get("generated_at")
    if not isinstance(generated_at, str):
        generated_at = ""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return generated_at, mtime


def _read_gate12_reports() -> list[tuple[Path, dict[str, object]]]:
    reports: list[tuple[Path, dict[str, object]]] = []
    for path in ROOT.glob("reports/*/judge/stats.json"):
        stats = json.loads(path.read_text(encoding="utf-8"))
        reports.append((path, stats))
    return sorted(reports, key=lambda item: _stats_sort_key(item[0], item[1]))


def _check_gate12_bench(*, allow_stale: bool = False) -> tuple[bool, str]:
    paths = sorted(ROOT.glob("reports/*/judge/stats.json"))
    if not paths:
        return (
            False,
            "no Gate 12 bench results found (run scripts/bench/bench_augment_vs_bare.py first)",
        )

    head_ok, head = _current_head()
    if not head_ok:
        return False, head

    try:
        reports = _read_gate12_reports()
    except Exception as exc:
        return False, f"could not parse Gate 12 stats: {exc}"

    if not reports:
        return (
            False,
            "no Gate 12 bench results found (run scripts/bench/bench_augment_vs_bare.py first)",
        )

    matching = [(path, stats) for path, stats in reports if stats.get("commit_sha") == head]
    if matching:
        latest, stats = matching[-1]
        stale_prefix = ""
    elif allow_stale:
        latest, stats = reports[-1]
        stale_commit = stats.get("commit_sha")
        stale_prefix = (
            f"WARNING: Gate 12 stale: stats are from commit {stale_commit or 'unknown'} "
            f"but HEAD is {head}; "
        )
    else:
        latest, stats = reports[-1]
        stale_commit = stats.get("commit_sha")
        if stale_commit:
            return (
                False,
                f"Gate 12 stale: Gate 12 stats are from commit {stale_commit} "
                f"but HEAD is {head}; rerun gate-12",
            )
        return (
            False,
            "Gate 12 stale: stats are missing commit_sha; rerun gate-12",
        )

    try:
        win_rate = stats.get("a_win_rate", stats.get("augmented_win_rate", 0.0))
        ok = float(win_rate) >= 0.50
        return ok, f"{stale_prefix}win_rate={float(win_rate):.1%} from {latest.parent.parent.name}"
    except Exception as exc:
        return False, f"could not parse {latest}: {exc}"


def _label_names(pr: dict[str, object]) -> set[str]:
    labels = pr.get("labels") or []
    names: set[str] = set()
    if not isinstance(labels, list):
        return names
    for label in labels:
        if isinstance(label, dict) and isinstance(label.get("name"), str):
            names.add(label["name"])
        elif isinstance(label, str):
            names.add(label)
    return names


def _check_open_prs() -> tuple[bool, str]:
    result = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "number,title,labels"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "GITHUB_TOKEN": ""},
    )
    if result.returncode != 0:
        return True, "gh not available — skipping PR check"
    try:
        prs = json.loads(result.stdout)
        blockers = [p for p in prs if "release-blocker" in _label_names(p)]
        summary = f"{len(prs)} open PRs ({len(blockers)} release-blockers)"
        if blockers:
            titles = [f"#{p['number']}" for p in blockers[:3]]
            return False, f"{summary}: {', '.join(titles)}"
        return True, summary
    except Exception:
        return True, "could not parse gh output — skipping"


def _check_git_clean() -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if result.stdout.strip():
        lines = result.stdout.strip().splitlines()
        return False, f"{len(lines)} uncommitted change(s): {lines[0]}"
    return True, "working tree clean"


MANDATORY_CHECKS: list[tuple[str, CheckFn]] = [
    ("Version 4-file consistency", _check_version_consistency),
    ("SKILL.md format", _check_skill_format),
    ("Channel experience dirs", _check_experience_dirs),
    ("MCP tools registered", _check_mcp_tools),
    ("Open PR release blockers", _check_open_prs),
    ("Git working tree clean", _check_git_clean),
]

ADVISORY_CHECKS: list[tuple[str, AdvisoryCheckFn]] = [
    ("Gate 12 bench ≥ 50%", _check_gate12_bench),
]


def _run_mandatory_checks() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for label, fn in MANDATORY_CHECKS:
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"ERROR: {exc}"
        results.append((label, ok, msg))
    return results


def _run_advisory_checks(*, allow_stale_gate12: bool) -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for label, fn in ADVISORY_CHECKS:
        try:
            ok, msg = fn(allow_stale=allow_stale_gate12)
        except Exception as exc:
            ok, msg = False, f"ERROR: {exc}"
        results.append((label, ok, msg))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run fast pre-release checks.")
    parser.add_argument(
        "--allow-stale-gate12",
        action="store_true",
        help="Allow Gate 12 stats from a different commit for emergency or dry-run checks.",
    )
    args = parser.parse_args(argv)

    mandatory_results = _run_mandatory_checks()
    advisory_results = _run_advisory_checks(allow_stale_gate12=args.allow_stale_gate12)

    print()
    print("=" * 62)
    print("  AutoSearch Pre-Release Checklist")
    print("=" * 62)
    mandatory_pass = True
    for label, ok, msg in mandatory_results:
        symbol = "✅" if ok else "❌"
        print(f"  {symbol}  [mandatory] {label}")
        print(f"       {msg}")
        if not ok:
            mandatory_pass = False
    for label, ok, msg in advisory_results:
        symbol = "PASS" if ok else "WARN"
        print(f"  [{symbol}] [advisory] {label}")
        print(f"        {msg}")
    mandatory_count = sum(1 for _, ok, _ in mandatory_results if ok)
    advisory_count = sum(1 for _, ok, _ in advisory_results if ok)
    print("=" * 62)
    print(f"  MANDATORY: {mandatory_count}/{len(mandatory_results)} passed")
    print(f"  ADVISORY: {advisory_count}/{len(advisory_results)} passed")
    if mandatory_pass:
        print("  MANDATORY CHECKS PASSED — ready for v1.0 tag")
        print("  Next: scripts/bump-version.sh → git tag v1.0.0 → git push --tags")
    else:
        print("  MANDATORY CHECKS FAILED — fix before tagging")
    print()
    return 0 if mandatory_pass else 1


if __name__ == "__main__":
    sys.exit(main())
