#!/usr/bin/env python3
"""Evolution Quality Test — does self-evolution improve final report quality?

Runs the full AutoSearch pipeline multiple rounds with evolution,
comparing baseline vs evolved scores to measure real improvement.

Usage:
    # Quick: 2 topics, 2 rounds (~20 min, ~$0.50)
    OPENROUTER_API_KEY=sk-or-... python tests/integration/test_evolution_quality.py --mode quick

    # Full: 8 topics, 3 rounds (~80 min, ~$2.50)
    OPENROUTER_API_KEY=sk-or-... python tests/integration/test_evolution_quality.py --mode full
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.integration.conftest import SessionDir
from tests.integration.run_e2e_test import (
    LLMClient,
    run_block1,
    run_block2,
    run_block3,
    run_block4,
    run_block5,
    run_block6,
)

# ── Config ───────────────────────────────────────────────────────────────

TRAINING_TOPICS = [
    {"id": "train-1", "topic": "AI agent framework comparison 2026"},
    {"id": "train-2", "topic": "中国大模型生态 2026"},
    {"id": "train-3", "topic": "vector database for RAG production"},
    {"id": "train-4", "topic": "smart wearable health market 2026"},
]

TEST_TOPICS = [
    {"id": "test-1", "topic": "WebAssembly edge computing 2026"},
    {"id": "test-2", "topic": "AI 代码审查工具对比"},
    {"id": "test-3", "topic": "quantum computing error correction"},
    {"id": "test-4", "topic": "creator economy monetization platforms"},
]

MODES = {
    "quick": {
        "training_topics": 2,
        "test_topics": 1,
        "rounds": 2,
        "skip_control": True,
    },
    "standard": {
        "training_topics": 4,
        "test_topics": 2,
        "rounds": 3,
        "skip_control": False,
    },
    "full": {
        "training_topics": 4,
        "test_topics": 4,
        "rounds": 3,
        "skip_control": False,
    },
}

COST_LIMIT_USD = 5.0
DEPTH = "standard"


# ── Worktree management ─────────────────────────────────────────────────


def create_worktree(base_path: Path) -> Path:
    """Create an isolated git worktree for the experiment."""
    branch = f"test/evolution-lab-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(base_path)],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    # Copy .venv symlink or directory
    venv_src = ROOT / ".venv"
    venv_dst = base_path / ".venv"
    if venv_src.exists() and not venv_dst.exists():
        if venv_src.is_symlink():
            os.symlink(os.readlink(venv_src), venv_dst)
        else:
            os.symlink(str(venv_src), venv_dst)
    return base_path


def cleanup_worktree(base_path: Path) -> None:
    """Remove the worktree."""
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(base_path)],
            cwd=ROOT,
            capture_output=True,
        )
    except Exception:
        pass


def reset_skills(base_path: Path) -> None:
    """Reset skills/ to the baseline state (HEAD of the branch)."""
    subprocess.run(
        ["git", "checkout", "HEAD", "--", "skills/"],
        cwd=base_path,
        capture_output=True,
    )


def get_skills_diff(base_path: Path) -> str:
    """Get diff of skills/ from baseline."""
    result = subprocess.run(
        ["git", "diff", "HEAD", "--", "skills/", "state/"],
        cwd=base_path,
        capture_output=True,
        text=True,
    )
    return result.stdout


# ── Pipeline runner ──────────────────────────────────────────────────────


# Storage for rubrics generated in baseline — reused across all rounds
_rubric_cache: dict[str, list[dict]] = {}


def _cache_rubrics(topic_id: str, session: SessionDir) -> None:
    """After baseline, cache the rubrics so later rounds reuse them."""
    rubrics = session.read_rubrics()
    if rubrics:
        _rubric_cache[topic_id] = rubrics


def _inject_cached_rubrics(topic_id: str, session: SessionDir) -> bool:
    """Copy cached rubrics into this session so Block 5 uses the same set."""
    if topic_id not in _rubric_cache:
        return False
    rubrics = _rubric_cache[topic_id]
    session.rubrics_path.write_text("\n".join(json.dumps(r) for r in rubrics) + "\n")
    return True


async def run_pipeline(
    llm: LLMClient,
    topic: dict,
    session_base: Path,
    run_id: str,
    evolve: bool = False,
    repo_root: Path | None = None,
    reuse_rubrics: bool = False,
) -> dict:
    """Run full pipeline for one topic. Returns scores dict."""
    slug = topic["topic"].lower().replace(" ", "-")[:30]
    session_id = f"{run_id}-{slug}"
    session = SessionDir(session_base, topic["id"], session_id)

    print(f"  [{run_id}] {topic['topic'][:40]}...")

    block_results = []
    pipeline_start = time.monotonic()

    # Block 1-5
    blocks = [
        ("B1-Prepare", lambda: run_block1(llm, session, topic["topic"], DEPTH)),
        ("B2-Search", lambda: run_block2(session)),
        ("B3-Evaluate", lambda: run_block3(llm, session, topic["topic"])),
        ("B4-Synthesize", lambda: run_block4(llm, session, topic["topic"], DEPTH)),
        ("B5-Quality", lambda: run_block5(llm, session)),
    ]

    for name, fn in blocks:
        result = await fn()
        status = "ok" if result.passed else "FAIL"
        print(f"    [{status}] {name} ({result.time_ms}ms)")
        block_results.append(result)

        # After Block 1: cache or inject rubrics
        if result.block == 1:
            if reuse_rubrics:
                injected = _inject_cached_rubrics(topic["id"], session)
                if injected:
                    print(
                        f"    [reuse] Rubrics from baseline ({len(_rubric_cache.get(topic['id'], []))} rubrics)"
                    )
            else:
                _cache_rubrics(topic["id"], session)

    # Block 6 evolution (optional)
    evolution_data = None
    if evolve:
        evo_result = await run_block6(llm, session, topic["topic"], repo_root=repo_root)
        status = "ok" if evo_result.passed else "FAIL"
        evo_detail = ""
        if evo_result.details.get("evolved"):
            evo_detail = f" → {evo_result.details.get('target_file', '?')}"
        if evo_result.details.get("reverted"):
            evo_detail += " [REVERTED]"
        print(f"    [{status}] B6-Evolve ({evo_result.time_ms}ms){evo_detail}")
        block_results.append(evo_result)
        evolution_data = evo_result.details

    pipeline_ms = int((time.monotonic() - pipeline_start) * 1000)

    # Extract scores
    judge_score = None
    rubric_pass_rate = None
    failed_rubric_count = 0

    for br in block_results:
        if br.block == 4:
            judge_score = br.details.get("judge_score")
        if br.block == 5:
            rubric_pass_rate = br.details.get("pass_rate")
            total = br.details.get("rubrics_total", 0)
            passed = br.details.get("rubrics_passed", 0)
            failed_rubric_count = total - passed

    return {
        "topic_id": topic["id"],
        "topic": topic["topic"],
        "run_id": run_id,
        "judge_score": judge_score,
        "rubric_pass_rate": rubric_pass_rate,
        "failed_rubric_count": failed_rubric_count,
        "pipeline_ms": pipeline_ms,
        "blocks_passed": sum(1 for b in block_results if b.passed),
        "blocks_total": len(block_results),
        "evolution": evolution_data,
    }


# ── Phases ───────────────────────────────────────────────────────────────


async def phase1_baseline(
    llm: LLMClient,
    topics: list[dict],
    session_base: Path,
    repo_root: Path,
) -> list[dict]:
    """Phase 1: Run all topics with fresh skills. Rubrics are cached for reuse."""
    print("\n" + "=" * 60)
    print("PHASE 1: BASELINE (fresh skills, no evolution)")
    print("=" * 60)

    results = []
    for topic in topics:
        score = await run_pipeline(
            llm,
            topic,
            session_base,
            run_id="baseline",
            evolve=False,
            repo_root=repo_root,
            reuse_rubrics=False,  # Generate fresh rubrics, cache them
        )
        results.append(score)
        if score["judge_score"] is not None:
            print(
                f"    => judge={score['judge_score']:.3f}  rubric={score['rubric_pass_rate']:.2f}"
            )
        else:
            print("    => pipeline incomplete")

    avg_rubric = sum(r["rubric_pass_rate"] or 0 for r in results) / len(results)
    avg_judge = sum(r["judge_score"] or 0 for r in results) / len(results)
    print(f"\n  Baseline avg: judge={avg_judge:.3f}  rubric={avg_rubric:.2f}")
    print(f"  Rubrics cached for {len(_rubric_cache)} topics")
    return results


async def phase2_training(
    llm: LLMClient,
    topics: list[dict],
    session_base: Path,
    rounds: int,
    repo_root: Path,
) -> list[list[dict]]:
    """Phase 2: Multiple rounds of evolution. Rubrics reused from baseline."""
    all_rounds = []

    for rnd in range(1, rounds + 1):
        print(f"\n{'=' * 60}")
        print(f"PHASE 2: TRAINING ROUND {rnd}/{rounds}")
        print("=" * 60)

        round_results = []
        for topic in topics:
            score = await run_pipeline(
                llm,
                topic,
                session_base,
                run_id=f"train-r{rnd}",
                evolve=True,
                repo_root=repo_root,
                reuse_rubrics=True,  # Use same rubrics as baseline
            )
            round_results.append(score)

            judge_str = (
                f"judge={score['judge_score']:.3f}"
                if score["judge_score"]
                else "judge=N/A"
            )
            rubric_str = (
                f"rubric={score['rubric_pass_rate']:.2f}"
                if score["rubric_pass_rate"] is not None
                else "rubric=N/A"
            )
            evo_str = ""
            if score.get("evolution"):
                if score["evolution"].get("evolved"):
                    evo_str = f"  evolved={score['evolution'].get('target_file', '?')}"
                if score["evolution"].get("reverted"):
                    evo_str += " [REVERTED]"
            print(f"    => {judge_str}  {rubric_str}{evo_str}")

        all_rounds.append(round_results)

        avg_rubric = sum(r["rubric_pass_rate"] or 0 for r in round_results) / len(
            round_results
        )
        print(f"\n  Round {rnd} avg rubric: {avg_rubric:.2f}")

    return all_rounds


async def phase3_generalization(
    llm: LLMClient,
    topics: list[dict],
    session_base: Path,
    repo_root: Path,
) -> list[dict]:
    """Phase 3: Run unseen test topics with evolved skills. Rubrics reused from baseline."""
    print(f"\n{'=' * 60}")
    print("PHASE 3: GENERALIZATION (unseen topics, evolved skills)")
    print("=" * 60)

    results = []
    for topic in topics:
        score = await run_pipeline(
            llm,
            topic,
            session_base,
            run_id="generalize",
            evolve=False,
            repo_root=repo_root,
            reuse_rubrics=True,
        )
        results.append(score)
        if score["judge_score"] is not None:
            print(
                f"    => judge={score['judge_score']:.3f}  rubric={score['rubric_pass_rate']:.2f}"
            )

    avg_rubric = sum(r["rubric_pass_rate"] or 0 for r in results) / len(results)
    print(f"\n  Generalization avg rubric: {avg_rubric:.2f}")
    return results


async def phase4_control(
    llm: LLMClient,
    topics: list[dict],
    session_base: Path,
    worktree_path: Path,
) -> list[dict]:
    """Phase 4: Reset skills, re-run training topics. Rubrics reused from baseline."""
    print(f"\n{'=' * 60}")
    print("PHASE 4: CONTROL (fresh skills, same topics)")
    print("=" * 60)

    # Reset skills to baseline
    reset_skills(worktree_path)
    print("  Skills reset to baseline")

    results = []
    for topic in topics:
        score = await run_pipeline(
            llm,
            topic,
            session_base,
            run_id="control",
            evolve=False,
            repo_root=worktree_path,
            reuse_rubrics=True,
        )
        results.append(score)
        if score["judge_score"] is not None:
            print(
                f"    => judge={score['judge_score']:.3f}  rubric={score['rubric_pass_rate']:.2f}"
            )

    avg_rubric = sum(r["rubric_pass_rate"] or 0 for r in results) / len(results)
    print(f"\n  Control avg rubric: {avg_rubric:.2f}")
    return results


# ── Analysis ─────────────────────────────────────────────────────────────


def compute_summary(
    baseline: list[dict],
    training_rounds: list[list[dict]],
    generalization: list[dict] | None,
    control: list[dict] | None,
    config: dict,
    duration_sec: float,
    llm: LLMClient,
    skills_diff: str,
) -> dict:
    """Compute final summary and verdict."""

    def avg_metric(results: list[dict], key: str) -> float:
        vals = [r[key] for r in results if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    # Baseline stats (only training topics)
    train_topic_ids = {r["topic_id"] for rounds in training_rounds for r in rounds}
    baseline_train = [r for r in baseline if r["topic_id"] in train_topic_ids]
    baseline_test = [r for r in baseline if r["topic_id"] not in train_topic_ids]

    baseline_rubric = avg_metric(baseline_train, "rubric_pass_rate")
    baseline_judge = avg_metric(baseline_train, "judge_score")

    # Final round stats
    final_round = training_rounds[-1] if training_rounds else []
    evolved_rubric = avg_metric(final_round, "rubric_pass_rate")
    evolved_judge = avg_metric(final_round, "judge_score")

    # Per-round progression
    round_progression = []
    for i, rnd in enumerate(training_rounds):
        round_progression.append(
            {
                "round": i + 1,
                "avg_rubric_pass_rate": avg_metric(rnd, "rubric_pass_rate"),
                "avg_judge_score": avg_metric(rnd, "judge_score"),
            }
        )

    # Generalization stats
    gen_rubric = (
        avg_metric(generalization, "rubric_pass_rate") if generalization else None
    )
    gen_judge = avg_metric(generalization, "judge_score") if generalization else None
    baseline_test_rubric = (
        avg_metric(baseline_test, "rubric_pass_rate") if baseline_test else None
    )

    # Control stats
    ctrl_rubric = avg_metric(control, "rubric_pass_rate") if control else None
    ctrl_judge = avg_metric(control, "judge_score") if control else None

    # Deltas
    training_improvement = evolved_rubric - baseline_rubric
    gen_improvement = (
        (gen_rubric - baseline_test_rubric)
        if gen_rubric is not None and baseline_test_rubric is not None
        else None
    )
    control_diff = (ctrl_rubric - baseline_rubric) if ctrl_rubric is not None else None

    # Evolution stats
    total_evolutions = 0
    commits = 0
    skips = 0
    for rnd in training_rounds:
        for r in rnd:
            evo = r.get("evolution")
            if evo:
                total_evolutions += 1
                if evo.get("evolved"):
                    commits += 1
                else:
                    skips += 1

    # Verdict
    if training_improvement >= 0.10 and (
        gen_improvement is None or gen_improvement >= 0
    ):
        verdict = "EFFECTIVE"
        verdict_detail = (
            f"Evolution improved training topic pass rate by +{training_improvement:.2f} "
            f"({baseline_rubric:.2f}→{evolved_rubric:.2f})."
        )
    elif training_improvement >= 0.03:
        verdict = "MILDLY_EFFECTIVE"
        verdict_detail = (
            f"Evolution showed mild improvement: +{training_improvement:.2f} "
            f"({baseline_rubric:.2f}→{evolved_rubric:.2f})."
        )
    elif training_improvement < -0.03:
        verdict = "HARMFUL"
        verdict_detail = (
            f"Evolution caused regression: {training_improvement:.2f} "
            f"({baseline_rubric:.2f}→{evolved_rubric:.2f})."
        )
    else:
        verdict = "INEFFECTIVE"
        verdict_detail = (
            f"Evolution had no meaningful effect: +{training_improvement:.2f} "
            f"({baseline_rubric:.2f}→{evolved_rubric:.2f})."
        )

    if control_diff is not None:
        evolution_is_cause = training_improvement > control_diff + 0.03
        verdict_detail += (
            f" Control delta: +{control_diff:.2f}. "
            f"Evolution is {'confirmed' if evolution_is_cause else 'NOT confirmed'} as cause."
        )
    else:
        evolution_is_cause = None

    if gen_improvement is not None:
        verdict_detail += f" Generalization: +{gen_improvement:.2f}."

    # Cost estimate
    input_cost = llm.total_input_tokens / 1_000_000 * 3.0  # rough avg
    output_cost = llm.total_output_tokens / 1_000_000 * 15.0
    total_cost = input_cost + output_cost

    return {
        "experiment_id": f"evolution-lab-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "duration_minutes": round(duration_sec / 60, 1),
        "api_cost_usd": round(total_cost, 2),
        "tokens": {
            "input": llm.total_input_tokens,
            "output": llm.total_output_tokens,
        },
        "config": config,
        "baseline": {
            "avg_rubric_pass_rate": round(baseline_rubric, 3),
            "avg_judge_score": round(baseline_judge, 3),
        },
        "evolved": {
            "avg_rubric_pass_rate": round(evolved_rubric, 3),
            "avg_judge_score": round(evolved_judge, 3),
        },
        "control": {
            "avg_rubric_pass_rate": round(ctrl_rubric, 3)
            if ctrl_rubric is not None
            else None,
            "avg_judge_score": round(ctrl_judge, 3) if ctrl_judge is not None else None,
        },
        "generalization": {
            "avg_rubric_pass_rate": round(gen_rubric, 3)
            if gen_rubric is not None
            else None,
            "avg_judge_score": round(gen_judge, 3) if gen_judge is not None else None,
            "baseline_test_rubric": round(baseline_test_rubric, 3)
            if baseline_test_rubric is not None
            else None,
        },
        "deltas": {
            "training_improvement": round(training_improvement, 3),
            "generalization_improvement": round(gen_improvement, 3)
            if gen_improvement is not None
            else None,
            "control_difference": round(control_diff, 3)
            if control_diff is not None
            else None,
            "evolution_is_cause": evolution_is_cause,
        },
        "round_progression": round_progression,
        "evolution_stats": {
            "total_rounds": total_evolutions,
            "commits": commits,
            "skips": skips,
        },
        "skills_diff_lines": len(skills_diff.splitlines()) if skills_diff else 0,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
    }


# ── Main ─────────────────────────────────────────────────────────────────


async def main_async(mode: str, api_key: str) -> int:
    mode_config = MODES[mode]
    training = TRAINING_TOPICS[: mode_config["training_topics"]]
    test = TEST_TOPICS[: mode_config["test_topics"]]
    all_topics = training + test
    rounds = mode_config["rounds"]
    skip_control = mode_config["skip_control"]

    print(f"Evolution Quality Test — mode={mode}")
    print(f"  Training topics: {len(training)}")
    print(f"  Test topics: {len(test)}")
    print(f"  Rounds: {rounds}")
    print(f"  Control: {'skip' if skip_control else 'yes'}")
    print()

    # Create report directory
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = ROOT / "tests" / "integration" / "reports" / f"evolution-lab-{ts}"
    report_dir.mkdir(parents=True, exist_ok=True)

    # Save config
    config = {
        "mode": mode,
        "training_topics": [t["topic"] for t in training],
        "test_topics": [t["topic"] for t in test],
        "rounds": rounds,
        "depth": DEPTH,
        "skip_control": skip_control,
        "timestamp": ts,
    }
    (report_dir / "config.json").write_text(json.dumps(config, indent=2))

    # Create worktree
    worktree_path = Path(f"/tmp/autosearch-evo-lab-{ts}")
    print(f"Creating worktree: {worktree_path}")
    try:
        create_worktree(worktree_path)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: Failed to create worktree: {exc.stderr}")
        return 1

    session_base = worktree_path / "tests" / "integration" / "sessions" / f"evo-{ts}"
    llm = LLMClient(api_key)
    experiment_start = time.monotonic()

    try:
        # Clear rubric cache
        _rubric_cache.clear()

        # Phase 1: Baseline (generates and caches rubrics)
        baseline = await phase1_baseline(llm, all_topics, session_base, worktree_path)
        _save_jsonl(report_dir / "baseline.jsonl", baseline)

        # Phase 2: Training (reuses baseline rubrics, evolves skills)
        training_rounds = await phase2_training(
            llm, training, session_base, rounds, worktree_path
        )
        for i, rnd in enumerate(training_rounds):
            _save_jsonl(report_dir / f"training-round-{i + 1}.jsonl", rnd)

        # Phase 3: Generalization (reuses baseline rubrics, evolved skills)
        gen_results = None
        if test:
            gen_results = await phase3_generalization(
                llm, test, session_base, worktree_path
            )
            _save_jsonl(report_dir / "generalization.jsonl", gen_results)

        # Phase 4: Control
        ctrl_results = None
        if not skip_control:
            ctrl_results = await phase4_control(
                llm, training, session_base, worktree_path
            )
            _save_jsonl(report_dir / "control.jsonl", ctrl_results)

        # Skills diff
        skills_diff = get_skills_diff(worktree_path)
        if skills_diff:
            (report_dir / "skills-diff.patch").write_text(skills_diff)

        # Copy state files
        for fname in ("evolution-log.jsonl", "patterns-v2.jsonl", "worklog.jsonl"):
            for session_dir in session_base.glob(f"**/state/{fname}"):
                content = session_dir.read_text().strip()
                if content:
                    with open(report_dir / fname, "a") as f:
                        f.write(content + "\n")

        # Phase 5: Summary
        duration = time.monotonic() - experiment_start
        summary = compute_summary(
            baseline=baseline,
            training_rounds=training_rounds,
            generalization=gen_results,
            control=ctrl_results,
            config=config,
            duration_sec=duration,
            llm=llm,
            skills_diff=skills_diff,
        )
        (report_dir / "summary.json").write_text(json.dumps(summary, indent=2))

        # Print verdict
        print(f"\n{'=' * 60}")
        print("VERDICT")
        print("=" * 60)
        print(f"  Result: {summary['verdict']}")
        print(f"  {summary['verdict_detail']}")
        print(
            f"\n  Baseline rubric:  {summary['baseline']['avg_rubric_pass_rate']:.3f}"
        )
        print(f"  Evolved rubric:   {summary['evolved']['avg_rubric_pass_rate']:.3f}")
        if summary["control"]["avg_rubric_pass_rate"] is not None:
            print(
                f"  Control rubric:   {summary['control']['avg_rubric_pass_rate']:.3f}"
            )
        if summary["generalization"]["avg_rubric_pass_rate"] is not None:
            print(
                f"  General. rubric:  {summary['generalization']['avg_rubric_pass_rate']:.3f}"
            )
        print(f"\n  Duration: {summary['duration_minutes']} min")
        print(f"  Cost: ~${summary['api_cost_usd']}")
        print(
            f"  Tokens: {summary['tokens']['input']:,} in / {summary['tokens']['output']:,} out"
        )
        print(f"\n  Report: {report_dir}")

        return 0 if summary["verdict"] in ("EFFECTIVE", "MILDLY_EFFECTIVE") else 1

    finally:
        print(f"\nCleaning up worktree: {worktree_path}")
        cleanup_worktree(worktree_path)


def _save_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evolution Quality Test")
    parser.add_argument(
        "--mode",
        choices=["quick", "standard", "full"],
        default="quick",
    )
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY"))
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: OPENROUTER_API_KEY required (env var or --api-key)")
        return 1

    return asyncio.run(main_async(args.mode, args.api_key))


if __name__ == "__main__":
    sys.exit(main())
