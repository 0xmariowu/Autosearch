#!/usr/bin/env python3
"""AutoSearch E2B Comprehensive Test Orchestrator.

Runs 20 scenarios in parallel across E2B sandboxes.
Each sandbox: create → install autosearch → run scenario → collect result → kill.

Usage:
  python scripts/e2b/run_comprehensive_tests.py [--categories A,B,C] [--parallel 20]
  python scripts/e2b/run_comprehensive_tests.py --smoke-only   # just A1-A3
  python scripts/e2b/run_comprehensive_tests.py --no-llm       # skip G2/G3 synthesis

Requires: E2B_API_KEY, OPENROUTER_API_KEY, TIKHUB_API_KEY (from ~/.config/ai-secrets.env)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.e2b.evaluate import compute_summary  # noqa: E402
from scripts.e2b.report import render  # noqa: E402
from scripts.e2b.sandbox_runner import (  # noqa: E402
    ScenarioResult,
    _collect_keys,
    create_sandbox,
    install_autosearch,
    kill_sandbox,
)
from scripts.e2b.scenarios.a_infrastructure import (  # noqa: E402
    a1_clean_install,
    a2_channel_health,
    a3_experience_layer,
)
from scripts.e2b.scenarios.b_english_tech import (  # noqa: E402
    b1_uv_monorepo,
    b2_cockroachdb_dev,
    b3_nextjs_migration,
    b4_docker_inference,
)
from scripts.e2b.scenarios.c_chinese_ugc import c1_xhs_cursor, c2_zhihu_deepseek, c3_bili_mlx  # noqa: E402
from scripts.e2b.scenarios.d_academic import (  # noqa: E402
    d1_pubmed_crispr,
    d2_llm_benchmark_contamination,
    d3_citation_dedup,
)
from scripts.e2b.scenarios.e_clarify_flow import (  # noqa: E402
    e1_ambiguous_triggers_clarify,
    e2_clear_query_skips_clarify,
)
from scripts.e2b.scenarios.f_parallel import (  # noqa: E402
    f1_delegate_subtask_parallel,
    f2_select_channels_cross_group,
)
from scripts.e2b.scenarios.g_full_report import (  # noqa: E402
    g1_loop_gap_detection,
    g2_golden_path_with_report,
    g3_complex_report_with_workflows,
)

# ── Scenario registry ─────────────────────────────────────────────────────────

ALL_SCENARIOS = [
    ("A1", "A", a1_clean_install),
    ("A2", "A", a2_channel_health),
    ("A3", "A", a3_experience_layer),
    ("B1", "B", b1_uv_monorepo),
    ("B2", "B", b2_cockroachdb_dev),
    ("B3", "B", b3_nextjs_migration),
    ("B4", "B", b4_docker_inference),
    ("C1", "C", c1_xhs_cursor),
    ("C2", "C", c2_zhihu_deepseek),
    ("C3", "C", c3_bili_mlx),
    ("D1", "D", d1_pubmed_crispr),
    ("D2", "D", d2_llm_benchmark_contamination),
    ("D3", "D", d3_citation_dedup),
    ("E1", "E", e1_ambiguous_triggers_clarify),
    ("E2", "E", e2_clear_query_skips_clarify),
    ("F1", "F", f1_delegate_subtask_parallel),
    ("F2", "F", f2_select_channels_cross_group),
    ("G1", "G", g1_loop_gap_detection),
    ("G2", "G", g2_golden_path_with_report),
    ("G3", "G", g3_complex_report_with_workflows),
]


# ── Single sandbox runner ─────────────────────────────────────────────────────


async def run_scenario_in_sandbox(
    scenario_id: str,
    category: str,
    scenario_fn,
    env: dict[str, str],
    semaphore: asyncio.Semaphore,
) -> ScenarioResult:
    """Create sandbox, install autosearch, run scenario, kill sandbox."""
    async with semaphore:
        sandbox_id = None
        t0 = time.monotonic()

        async with httpx.AsyncClient(timeout=300) as client:
            try:
                print(f"  [{scenario_id}] creating sandbox...")
                sandbox_id = await create_sandbox(client)
                print(f"  [{scenario_id}] installing autosearch... (sandbox={sandbox_id[:8]})")

                ok = await install_autosearch(sandbox_id, timeout=180)
                if not ok:
                    return ScenarioResult(
                        scenario_id,
                        category,
                        scenario_fn.__name__,
                        score=0,
                        passed=False,
                        error="pip install failed",
                        duration_s=time.monotonic() - t0,
                    )

                print(f"  [{scenario_id}] running scenario...")
                result = await scenario_fn(sandbox_id, env)
                result.duration_s = time.monotonic() - t0
                status = "✅" if result.passed else "❌"
                print(
                    f"  [{scenario_id}] {status} score={result.score} ev={result.evidence_count} t={result.duration_s:.0f}s"
                )
                return result

            except Exception as exc:
                dur = time.monotonic() - t0
                print(f"  [{scenario_id}] ❌ exception: {exc}")
                return ScenarioResult(
                    scenario_id,
                    category,
                    scenario_fn.__name__,
                    score=0,
                    passed=False,
                    error=str(exc)[:200],
                    duration_s=dur,
                )
            finally:
                if sandbox_id:
                    await kill_sandbox(client, sandbox_id)


# ── Main ──────────────────────────────────────────────────────────────────────


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_comprehensive_tests.py")
    parser.add_argument(
        "--categories", default="", help="Comma-separated list e.g. A,B,C (default: all)"
    )
    parser.add_argument(
        "--parallel", type=int, default=10, help="Max parallel sandboxes (default: 10)"
    )
    parser.add_argument("--smoke-only", action="store_true", help="Run only A1-A3")
    parser.add_argument("--no-llm", action="store_true", help="Skip G2/G3 (require OpenRouter)")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    if not os.environ.get("E2B_API_KEY"):
        print("error: E2B_API_KEY not set", file=sys.stderr)
        return 1

    # Collect env keys from local environment
    env = _collect_keys()
    if not env.get("OPENROUTER_API_KEY"):
        print(
            "warning: OPENROUTER_API_KEY not set — G2/G3 synthesis will be skipped", file=sys.stderr
        )
    if not env.get("TIKHUB_API_KEY"):
        print(
            "warning: TIKHUB_API_KEY not set — C1-C3 will use graceful-fail path", file=sys.stderr
        )

    # Filter scenarios
    scenarios = ALL_SCENARIOS
    if args.smoke_only:
        scenarios = [s for s in scenarios if s[1] == "A"]
    elif args.categories:
        cats = set(args.categories.upper().split(","))
        scenarios = [s for s in scenarios if s[1] in cats]
    if args.no_llm:
        scenarios = [s for s in scenarios if s[0] not in ("G2", "G3")]

    print("\nAutoSearch E2B Comprehensive Tests")
    print(f"  scenarios: {len(scenarios)}")
    print(f"  parallel:  {args.parallel}")
    print(f"  env keys:  {', '.join(env.keys()) or 'none'}")
    print()

    semaphore = asyncio.Semaphore(args.parallel)
    tasks = [run_scenario_in_sandbox(sid, cat, fn, env, semaphore) for sid, cat, fn in scenarios]

    t_start = time.monotonic()
    results = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - t_start

    # Output directory
    date_str = datetime.now().strftime("%Y-%m-%d-%H%M")
    output_dir = args.output or (ROOT / "reports" / f"e2b-comprehensive-{date_str}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Compute summary & write outputs
    summary = compute_summary(list(results))
    (output_dir / "results.json").write_text(
        json.dumps(
            {"summary": summary, "results": [r.to_dict() for r in results]},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    render(list(results), summary, output_dir)

    # Print final summary
    emoji = {"READY": "🟢", "BETA": "🟡", "NOT_READY": "🔴"}.get(summary["readiness"], "⚪")
    print()
    print("=" * 62)
    print("  AutoSearch E2B 综合测试结果")
    print("=" * 62)
    print(f"  总体得分:   {summary['overall_score']}/100")
    print(f"  v1.0 就绪:  {emoji} {summary['readiness']}")
    print(f"  通过场景:   {summary['passed']}/{summary['total']} ({summary['pass_rate']}%)")
    print(f"  证据总数:   {summary['total_evidence']} 条")
    print(f"  报告字数:   {summary['total_report_chars']} 字")
    print(f"  总耗时:     {elapsed:.0f}s")
    print()
    print("  各类别得分:")
    for cat, score in sorted(summary["category_scores"].items()):
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        print(f"    {cat}  {bar} {score}/100")
    print()
    if summary["failures"]:
        print("  失败场景:")
        for f in summary["failures"][:5]:
            print(f"    ❌ {f['id']} {f['name']} ({f['score']}分): {f['error'][:60]}")
    print()
    print(f"  报告: {output_dir / 'summary.md'}")
    print("=" * 62)

    return 0 if summary["readiness"] in ("READY", "BETA") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
