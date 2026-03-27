#!/usr/bin/env python3
"""Run multiple goal cases and summarize cross-project progress."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from goal_bundle_loop import (
    GOAL_CASES_ROOT,
    GOAL_RUNS_ROOT,
    load_goal_case,
    run_goal_bundle_loop,
)


BENCHMARK_ROOT = GOAL_CASES_ROOT / "benchmarks"


def _benchmark_summary(result: dict[str, Any]) -> dict[str, Any]:
    rounds = list(result.get("rounds") or [])
    accepted_rounds = [item for item in rounds if item.get("accepted")]
    target_score = int(result.get("target_score", 0) or 0)
    final_score = int(((result.get("bundle_final") or {}).get("score") or 0))
    return {
        "goal_id": str(result.get("goal_id") or ""),
        "problem": str(result.get("problem") or ""),
        "target_score": target_score,
        "final_score": final_score,
        "goal_reached": bool(result.get("goal_reached")),
        "score_gap": int(
            result.get("score_gap", max(0, target_score - final_score)) or 0
        ),
        "stop_reason": str(result.get("stop_reason") or ""),
        "practical_ceiling": result.get("practical_ceiling"),
        "accepted_rounds": len(accepted_rounds),
        "rounds_run": len(rounds),
        "providers_used": list(result.get("providers_used") or []),
        "accepted_program_id": str(
            (result.get("accepted_program") or {}).get("program_id") or ""
        ),
        "matched_dimensions": list(
            ((result.get("bundle_final") or {}).get("matched_dimensions") or [])
        ),
        "missing_dimensions": list(
            ((result.get("bundle_final") or {}).get("missing_dimensions") or [])
        ),
    }


def run_benchmark(
    goal_paths: list[Path],
    max_rounds: int,
    *,
    plan_count: int | None = None,
    max_queries: int | None = None,
    target_score: int | None = None,
    plateau_rounds: int | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for path in goal_paths:
        goal_case = load_goal_case(path)
        result = run_goal_bundle_loop(
            goal_case,
            max_rounds=max_rounds,
            plan_count_override=plan_count,
            max_queries_override=max_queries,
            target_score_override=target_score,
            plateau_rounds_override=plateau_rounds,
        )
        results.append(result)
        summaries.append(_benchmark_summary(result))

    generated_at = datetime.now().astimezone().isoformat()
    payload = {
        "generated_at": generated_at,
        "max_rounds": int(max_rounds),
        "plan_count": int(plan_count or 0),
        "max_queries": int(max_queries or 0),
        "target_score": int(target_score or 0),
        "plateau_rounds": int(plateau_rounds or 0),
        "goals": summaries,
    }
    return {
        "payload": payload,
        "results": results,
    }


def _write_outputs(benchmark: dict[str, Any]) -> dict[str, Path]:
    BENCHMARK_ROOT.mkdir(parents=True, exist_ok=True)
    GOAL_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    summary_path = BENCHMARK_ROOT / f"{stamp}-goal-benchmark.json"
    summary_path.write_text(
        json.dumps(benchmark["payload"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    per_goal_paths: list[Path] = []
    for result in benchmark["results"]:
        goal_id = str(result.get("goal_id") or "goal")
        run_path = GOAL_RUNS_ROOT / f"{stamp}-{goal_id}-benchmark-bundle.json"
        run_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        per_goal_paths.append(run_path)

    return {
        "summary": summary_path,
        "runs": per_goal_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a cross-goal benchmark for autosearch goal loops"
    )
    parser.add_argument(
        "--goals",
        nargs="*",
        default=[
            "atoms-auto-mining-perfect",
            "autosearch-goal-judge",
            "autosearch-capability-doctor",
        ],
        help="Goal case ids or file paths",
    )
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--plan-count", type=int, default=1)
    parser.add_argument("--max-queries", type=int, default=1)
    parser.add_argument("--target-score", type=int, default=0)
    parser.add_argument("--plateau-rounds", type=int, default=0)
    args = parser.parse_args()

    goal_paths: list[Path] = []
    for goal in args.goals:
        path = Path(goal)
        if path.exists():
            goal_paths.append(path)
            continue
        goal_path = GOAL_CASES_ROOT / f"{goal}.json"
        if not goal_path.exists():
            raise FileNotFoundError(f"Goal case not found: {goal}")
        goal_paths.append(goal_path)

    benchmark = run_benchmark(
        goal_paths,
        max_rounds=args.max_rounds,
        plan_count=args.plan_count,
        max_queries=args.max_queries,
        target_score=args.target_score or None,
        plateau_rounds=args.plateau_rounds or None,
    )
    outputs = _write_outputs(benchmark)
    print(
        json.dumps(
            {
                **benchmark["payload"],
                "summary_path": str(outputs["summary"]),
                "run_paths": [str(path) for path in outputs["runs"]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
