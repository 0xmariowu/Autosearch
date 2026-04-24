#!/usr/bin/env python3
"""AutoSearch E2B Comprehensive Test Orchestrator.

Runs 126 scenarios in parallel across E2B sandboxes.
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
from scripts.e2b.scenarios.h_install_diversity import (  # noqa: E402
    h1_uv_venv_install,
    h2_pipx_install,
    h3_editable_install,
    h4_no_api_keys,
    h5_partial_keys_openrouter_only,
    h6_wrong_python_version,
    h7_pinned_version_install,
    h8_reinstall_idempotency,
)
from scripts.e2b.scenarios.i_channel_quality import (  # noqa: E402
    i1_arxiv_transformer_attention,
    i2_pubmed_crispr_off_target,
    i3_hackernews_rust_systems,
    i4_devto_typescript_performance,
    i5_dockerhub_redis_alpine,
    i6_reddit_python_async,
    i7_stackoverflow_postgres_index,
    i8_ddgs_vector_database,
    i9_github_vector_embeddings,
    i10_papers_diffusion_survey,
    i11_wikipedia_quantum,
    i12_wikidata_python_language,
)
from scripts.e2b.scenarios.j_error_cases import (  # noqa: E402
    j1_unknown_channel_error,
    j2_channel_exception_degradation,
    j3_empty_query,
    j4_special_chars_query,
    j5_citation_dedup,
    j6_zero_result_gap_detection,
    j7_experience_compaction_trigger,
    j8_long_query_handling,
)
from scripts.e2b.scenarios.k_avo_evolution import (  # noqa: E402
    k1_avo_baseline_score,
    k2_meta_skill_protection,
    k3_pattern_append_compact,
    k4_git_commit_revert_cycle,
    k5_evolution_contract_validation,
)
from scripts.e2b.scenarios.l_report_quality import (  # noqa: E402
    l1_fast_mode_report,
    l2_deep_mode_loop_report,
    l3_chinese_topic_report,
    l4_mini_gate12_llm_judge,
)
from scripts.e2b.scenarios.w_windows_emulation import (  # noqa: E402
    w1_windows_platform_mock,
    w2_windows_home_dir_mock,
    w3_windows_path_separator,
)
from scripts.e2b.scenarios.p_desktop_gui import (  # noqa: E402
    p1_cli_install_in_terminal,
    p2_doctor_cli_output,
    p3_configure_cli,
    p4_mcp_server_starts,
    p5_list_skills_cli,
    p6_doctor_json_output,
    p7_multiple_tool_calls,
    p8_reinstall_no_state_corruption,
    p9_wine_cli_path_test,
    p10_error_message_quality,
    p11_long_running_no_hang,
    p12_help_text_complete,
)
from scripts.e2b.scenarios.q_search_quality import (  # noqa: E402
    q1_arxiv_cot_prompting,
    q2_pubmed_rna_biomarker,
    q3_hackernews_rust_tokio,
    q4_stackoverflow_asyncio,
    q5_github_opentelemetry,
    q6_devto_typescript_generics,
    q7_ddgs_claude_code_hooks,
    q8_wikipedia_transformer_attention,
    q9_pubmed_crispr_trials,
    q10_arxiv_diffusion_survey,
    q11_hackernews_uv_python,
    q12_stackoverflow_kubernetes_autoscaling,
    q13_ddgs_chinese_rag,
    q14_ddgs_chinese_macos_homebrew,
    q15_devto_ai_coding_workflow,
)
from scripts.e2b.scenarios.r_channel_reliability import (  # noqa: E402
    r1_channel_timeout_graceful,
    r2_channel_429_graceful,
    r3_channel_malformed_response,
    r4_empty_channel_loop_continues,
    r5_concurrent_5_arxiv,
    r6_delegate_1_channel_fails,
    r7_long_query_all_free_channels,
    r8_unicode_query_stability,
    r9_large_k_parameter,
    r10_10_different_channels_simultaneous,
)
from scripts.e2b.scenarios.s_stress_testing import (  # noqa: E402
    s1_concurrent_10_channels,
    s2_citation_100_unique_adds,
    s3_experience_100_events_compact,
    s4_loop_5_rounds,
    s5_delegate_10_channels_parallel,
    s6_context_retention_500_items,
    s7_citation_50_duplicate_stress,
    s8_rapid_loop_20_updates,
)
from scripts.e2b.scenarios.t_experience_effect import (  # noqa: E402
    t1_experience_injected_in_rationale,
    t2_pattern_quality_threshold,
    t3_failure_not_promoted,
    t4_experience_size_compliance,
    t5_multi_channel_independence,
    t6_experience_append_atomic,
    t7_failure_only_in_known_failures,
    t8_experience_compact_integration,
)
from scripts.e2b.scenarios.x_tikhub_pathfinding import (  # noqa: E402
    x1_bilibili_mlx_tutorial,
    x2_bilibili_llm_tutorial,
    x3_xiaohongshu_cursor_ide,
    x4_xiaohongshu_python_learning,
    x5_weibo_ai_tech,
    x6_douyin_programming,
    x7_tiktok_english_tech,
    x8_tikhub_cross_platform,
)
from scripts.e2b.scenarios.v_cross_platform import (  # noqa: E402
    v1_musl_libc_mock,
    v2_python310_version_check,
    v3_windows_full_env_mock,
    v4_windows_no_ansi_cli,
    v5_stub_gh_actions_windows,
    v6_locale_utf8_handling,
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
    # ── Install Diversity ────────────────────────────────────────────────────
    ("H1", "H", h1_uv_venv_install),
    ("H2", "H", h2_pipx_install),
    ("H3", "H", h3_editable_install),
    ("H4", "H", h4_no_api_keys),
    ("H5", "H", h5_partial_keys_openrouter_only),
    ("H6", "H", h6_wrong_python_version),
    ("H7", "H", h7_pinned_version_install),
    ("H8", "H", h8_reinstall_idempotency),
    # ── Per-Channel Quality ──────────────────────────────────────────────────
    ("I1", "I", i1_arxiv_transformer_attention),
    ("I2", "I", i2_pubmed_crispr_off_target),
    ("I3", "I", i3_hackernews_rust_systems),
    ("I4", "I", i4_devto_typescript_performance),
    ("I5", "I", i5_dockerhub_redis_alpine),
    ("I6", "I", i6_reddit_python_async),
    ("I7", "I", i7_stackoverflow_postgres_index),
    ("I8", "I", i8_ddgs_vector_database),
    ("I9", "I", i9_github_vector_embeddings),
    ("I10", "I", i10_papers_diffusion_survey),
    ("I11", "I", i11_wikipedia_quantum),
    ("I12", "I", i12_wikidata_python_language),
    # ── Error & Edge Cases ───────────────────────────────────────────────────
    ("J1", "J", j1_unknown_channel_error),
    ("J2", "J", j2_channel_exception_degradation),
    ("J3", "J", j3_empty_query),
    ("J4", "J", j4_special_chars_query),
    ("J5", "J", j5_citation_dedup),
    ("J6", "J", j6_zero_result_gap_detection),
    ("J7", "J", j7_experience_compaction_trigger),
    ("J8", "J", j8_long_query_handling),
    # ── AVO Evolution ────────────────────────────────────────────────────────
    ("K1", "K", k1_avo_baseline_score),
    ("K2", "K", k2_meta_skill_protection),
    ("K3", "K", k3_pattern_append_compact),
    ("K4", "K", k4_git_commit_revert_cycle),
    ("K5", "K", k5_evolution_contract_validation),
    # ── Report Quality ───────────────────────────────────────────────────────
    ("L1", "L", l1_fast_mode_report),
    ("L2", "L", l2_deep_mode_loop_report),
    ("L3", "L", l3_chinese_topic_report),
    ("L4", "L", l4_mini_gate12_llm_judge),
    # ── Windows Emulation (bonus) ─────────────────────────────────────────────
    ("W1", "W", w1_windows_platform_mock),
    ("W2", "W", w2_windows_home_dir_mock),
    ("W3", "W", w3_windows_path_separator),
    # NOTE: P scenarios create their own e2b_desktop sandbox internally.
    # The headless sandbox_id passed to them is unused.
    # ── Phase 2: Desktop GUI ─────────────────────────────────────────────────
    ("P1", "P", p1_cli_install_in_terminal),
    ("P2", "P", p2_doctor_cli_output),
    ("P3", "P", p3_configure_cli),
    ("P4", "P", p4_mcp_server_starts),
    ("P5", "P", p5_list_skills_cli),
    ("P6", "P", p6_doctor_json_output),
    ("P7", "P", p7_multiple_tool_calls),
    ("P8", "P", p8_reinstall_no_state_corruption),
    ("P9", "P", p9_wine_cli_path_test),
    ("P10", "P", p10_error_message_quality),
    ("P11", "P", p11_long_running_no_hang),
    ("P12", "P", p12_help_text_complete),
    # ── Phase 2: Search Quality Judge ────────────────────────────────────────
    ("Q1", "Q", q1_arxiv_cot_prompting),
    ("Q2", "Q", q2_pubmed_rna_biomarker),
    ("Q3", "Q", q3_hackernews_rust_tokio),
    ("Q4", "Q", q4_stackoverflow_asyncio),
    ("Q5", "Q", q5_github_opentelemetry),
    ("Q6", "Q", q6_devto_typescript_generics),
    ("Q7", "Q", q7_ddgs_claude_code_hooks),
    ("Q8", "Q", q8_wikipedia_transformer_attention),
    ("Q9", "Q", q9_pubmed_crispr_trials),
    ("Q10", "Q", q10_arxiv_diffusion_survey),
    ("Q11", "Q", q11_hackernews_uv_python),
    ("Q12", "Q", q12_stackoverflow_kubernetes_autoscaling),
    ("Q13", "Q", q13_ddgs_chinese_rag),
    ("Q14", "Q", q14_ddgs_chinese_macos_homebrew),
    ("Q15", "Q", q15_devto_ai_coding_workflow),
    # ── Phase 2: Channel Reliability ─────────────────────────────────────────
    ("R1", "R", r1_channel_timeout_graceful),
    ("R2", "R", r2_channel_429_graceful),
    ("R3", "R", r3_channel_malformed_response),
    ("R4", "R", r4_empty_channel_loop_continues),
    ("R5", "R", r5_concurrent_5_arxiv),
    ("R6", "R", r6_delegate_1_channel_fails),
    ("R7", "R", r7_long_query_all_free_channels),
    ("R8", "R", r8_unicode_query_stability),
    ("R9", "R", r9_large_k_parameter),
    ("R10", "R", r10_10_different_channels_simultaneous),
    # ── Phase 2: Stress Testing ───────────────────────────────────────────────
    ("S1", "S", s1_concurrent_10_channels),
    ("S2", "S", s2_citation_100_unique_adds),
    ("S3", "S", s3_experience_100_events_compact),
    ("S4", "S", s4_loop_5_rounds),
    ("S5", "S", s5_delegate_10_channels_parallel),
    ("S6", "S", s6_context_retention_500_items),
    ("S7", "S", s7_citation_50_duplicate_stress),
    ("S8", "S", s8_rapid_loop_20_updates),
    # ── Phase 2: Experience Effectiveness ────────────────────────────────────
    ("T1", "T", t1_experience_injected_in_rationale),
    ("T2", "T", t2_pattern_quality_threshold),
    ("T3", "T", t3_failure_not_promoted),
    ("T4", "T", t4_experience_size_compliance),
    ("T5", "T", t5_multi_channel_independence),
    ("T6", "T", t6_experience_append_atomic),
    ("T7", "T", t7_failure_only_in_known_failures),
    ("T8", "T", t8_experience_compact_integration),
    # ── Phase 2: TikHub Pathfinding ───────────────────────────────────────────
    ("X1", "X", x1_bilibili_mlx_tutorial),
    ("X2", "X", x2_bilibili_llm_tutorial),
    ("X3", "X", x3_xiaohongshu_cursor_ide),
    ("X4", "X", x4_xiaohongshu_python_learning),
    ("X5", "X", x5_weibo_ai_tech),
    ("X6", "X", x6_douyin_programming),
    ("X7", "X", x7_tiktok_english_tech),
    ("X8", "X", x8_tikhub_cross_platform),
    # ── Phase 2: Cross-Platform (bonus) ──────────────────────────────────────
    ("V1", "V", v1_musl_libc_mock),
    ("V2", "V", v2_python310_version_check),
    ("V3", "V", v3_windows_full_env_mock),
    ("V4", "V", v4_windows_no_ansi_cli),
    ("V5", "V", v5_stub_gh_actions_windows),
    ("V6", "V", v6_locale_utf8_handling),
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
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List all scenario IDs and exit without running",
    )
    args = parser.parse_args(argv)

    if args.list_scenarios:
        for sid, cat, fn in ALL_SCENARIOS:
            print(f"{sid:4s} ({cat})  {fn.__name__}")
        return 0

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
