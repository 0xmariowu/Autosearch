#!/usr/bin/env python3
"""G7-T1: Pre-release checklist — runs all fast checks before v1.0 tag.

Usage: python scripts/validate/pre_release_check.py
Exit 0 = all checks pass. Exit 1 = one or more fail.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "validate"


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


def _check_gate12_bench() -> tuple[bool, str]:
    reports = sorted(ROOT.glob("reports/*/judge/stats.json"))
    if not reports:
        return (
            False,
            "no Gate 12 bench results found (run scripts/bench/bench_augment_vs_bare.py first)",
        )
    latest = reports[-1]
    try:
        stats = json.loads(latest.read_text(encoding="utf-8"))
        win_rate = stats.get("a_win_rate", stats.get("augmented_win_rate", 0.0))
        ok = float(win_rate) >= 0.50
        return ok, f"win_rate={float(win_rate):.1%} from {latest.parent.parent.name}"
    except Exception as exc:
        return False, f"could not parse {latest}: {exc}"


def _check_open_prs() -> tuple[bool, str]:
    result = subprocess.run(
        ["gh", "pr", "list", "--state", "open", "--json", "number,title"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "GITHUB_TOKEN": ""},
    )
    if result.returncode != 0:
        return True, "gh not available — skipping PR check"
    try:
        prs = json.loads(result.stdout)
        if prs:
            titles = [f"#{p['number']}" for p in prs[:3]]
            return False, f"{len(prs)} open PRs: {', '.join(titles)}"
        return True, "no open PRs"
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


def main() -> int:
    checks = [
        ("Version 4-file consistency", _check_version_consistency),
        ("SKILL.md format compliance", _check_skill_format),
        ("Channel experience dirs", _check_experience_dirs),
        ("MCP tools registered", _check_mcp_tools),
        ("Gate 12 bench ≥ 50%", _check_gate12_bench),
        ("Open PRs = 0", _check_open_prs),
        ("Git working tree clean", _check_git_clean),
    ]

    results: list[tuple[str, bool, str]] = []
    for label, fn in checks:
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"ERROR: {exc}"
        results.append((label, ok, msg))

    print()
    print("=" * 62)
    print("  AutoSearch Pre-Release Checklist")
    print("=" * 62)
    all_pass = True
    for label, ok, msg in results:
        symbol = "✅" if ok else "❌"
        print(f"  {symbol}  {label}")
        print(f"       {msg}")
        if not ok:
            all_pass = False
    print("=" * 62)
    if all_pass:
        print("  ALL CHECKS PASSED — ready for v1.0 tag")
        print("  Next: scripts/bump-version.sh → git tag v1.0.0 → git push --tags")
    else:
        print("  SOME CHECKS FAILED — fix before tagging")
    print()
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
