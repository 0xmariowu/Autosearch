#!/usr/bin/env python3
"""F012: Full v2 validation suite runner.

Runs S1-S5 validation steps (S6 = Gate 12 bench, run separately).
Steps:
  S1  pytest full suite
  S2  MCP tool registration check
  S3  Experience layer end-to-end
  S4  doctor() MCP tool smoke
  S5  Gate 12 bench (augmented vs bare) — separate script

Usage:
  python scripts/validate/run_validation.py [--skip-bench]
  python scripts/validate/run_validation.py --bench-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
REPORT_DIR = ROOT / "reports"


def _run(label: str, cmd: list[str]) -> bool:
    print(f"\n{'=' * 60}")
    print(f"[{label}]")
    print(f"  cmd: {' '.join(cmd)}")
    print("=" * 60)
    result = subprocess.run(cmd, cwd=ROOT)
    ok = result.returncode == 0
    print(f"\n  -> {'PASS' if ok else 'FAIL'} ({label})")
    return ok


def _run_bench() -> bool:
    from datetime import date

    output_dir = REPORT_DIR / f"{date.today().isoformat()}-gate12"
    output_dir.mkdir(parents=True, exist_ok=True)
    a_dir = output_dir / "a"
    b_dir = output_dir / "b"
    judge_dir = output_dir / "judge"

    topics = ROOT / "scripts/bench/topics/gate-12-topics.yaml"
    if not topics.exists():
        print(f"  SKIP: topics file not found at {topics}")
        return True

    bench_ok = _run(
        "Gate 12 bench runner",
        [
            sys.executable,
            str(ROOT / "scripts/bench/bench_augment_vs_bare.py"),
            "--topics",
            str(topics),
            "--output",
            str(output_dir),
            "--parallel",
            "4",
            "--runs-per-topic",
            "1",
        ],
    )
    if not bench_ok:
        return False

    judge_ok = _run(
        "Gate 12 pairwise judge",
        [
            sys.executable,
            str(ROOT / "scripts/bench/judge.py"),
            "pairwise",
            "--a-dir",
            str(a_dir),
            "--b-dir",
            str(b_dir),
            "--a-label",
            "augmented",
            "--b-label",
            "bare",
            "--output-dir",
            str(judge_dir),
            "--parallel",
            "8",
        ],
    )
    if not judge_ok:
        return False

    summary = judge_dir / "pairwise-summary.md"
    stats = judge_dir / "stats.json"
    if summary.exists():
        print("\n--- Gate 12 Summary ---")
        print(summary.read_text(encoding="utf-8"))
    if stats.exists():
        import json

        data = json.loads(stats.read_text(encoding="utf-8"))
        win_rate = data.get("augmented_win_rate", data.get("a_win_rate", "N/A"))
        print(f"\nAugmented win rate: {win_rate}")
        if isinstance(win_rate, float):
            if win_rate >= 0.50:
                print("  >= 50% -> v1.0 tag UNBLOCKED")
            elif win_rate >= 0.30:
                print("  30-50% -> positioning: 'augment on specific surfaces'")
            else:
                print("  < 30%  -> diagnose router/SKILL.md trigger keywords")

    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-bench", action="store_true", help="Skip Gate 12 bench")
    parser.add_argument("--bench-only", action="store_true", help="Run only Gate 12 bench")
    args = parser.parse_args()

    results: dict[str, bool] = {}

    if not args.bench_only:
        results["S1 pytest"] = _run(
            "S1 pytest full suite",
            [sys.executable, "-m", "pytest", "-x", "-q", "--ignore=tests/perf"],
        )
        results["S2 mcp tools"] = _run(
            "S2 MCP tool registration",
            [sys.executable, str(ROOT / "scripts/validate/check_mcp_tools.py")],
        )
        results["S3 experience e2e"] = _run(
            "S3 Experience layer e2e",
            [sys.executable, str(ROOT / "scripts/validate/test_experience_e2e.py")],
        )
        results["S4 doctor smoke"] = _run(
            "S4 doctor() smoke test",
            [
                sys.executable,
                "-c",
                "import os; os.environ['AUTOSEARCH_LLM_MODE']='dummy';"
                "from autosearch.core.doctor import scan_channels; r=scan_channels();"
                "print(f'doctor() returned {len(r)} channels'); assert len(r) > 0; print('PASS')",
            ],
        )

    if not args.skip_bench:
        results["S5 gate12 bench"] = _run_bench()

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    all_pass = True
    for step, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {status}  {step}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("ALL STEPS PASSED — v1.0 tag eligible (check Gate 12 win rate)")
        return 0
    else:
        print("SOME STEPS FAILED — fix before tagging v1.0")
        return 1


if __name__ == "__main__":
    sys.exit(main())
