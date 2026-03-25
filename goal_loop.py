#!/usr/bin/env python3
"""Goal-driven search loop with independent judging and keep/discard selection."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from engine import PlatformConnector, Scorer
from goal_judge import evaluate_goal_case
from source_capability import get_source_decision, refresh_source_capability


REPO_ROOT = Path(__file__).resolve().parent
GOAL_CASES_ROOT = REPO_ROOT / "goal_cases"
GOAL_RUNS_ROOT = GOAL_CASES_ROOT / "runs"


def load_goal_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _available_platforms(goal_case: dict[str, Any], capability_report: dict[str, Any]) -> list[dict[str, Any]]:
    platforms: list[dict[str, Any]] = []
    for name in goal_case.get("providers", []):
        decision = get_source_decision(capability_report, name)
        if decision["should_skip"]:
            continue
        if name == "github_repos":
            platforms.append({"name": name, "limit": 5, "min_stars": 20})
        elif name == "github_issues":
            platforms.append({"name": name, "limit": 5})
        elif name == "twitter_xreach":
            platforms.append({"name": name, "limit": 10})
        else:
            platforms.append({"name": name, "limit": 5})
    return platforms


def _search_query(query: str, platforms: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    findings: list[dict[str, Any]] = []
    baseline = 0
    scorer = Scorer()
    all_results = []
    for platform in platforms:
        outcome = PlatformConnector.search(platform, query)
        all_results.extend(outcome.results)
    _, raw_score, new_results = scorer.score_results(all_results)
    baseline = raw_score
    for result in new_results[:15]:
        findings.append({
            "title": result.title,
            "url": result.url,
            "body": result.body,
            "source": result.source,
        })
    return findings, baseline


def _mutate_queries(best_query: str, evaluation: dict[str, Any], goal_case: dict[str, Any]) -> list[str]:
    mutations: list[str] = []
    for term in evaluation.get("missing_terms", [])[:3]:
        mutations.append(f"{best_query} {term}".strip())
    for term in goal_case.get("mutation_terms", [])[:3]:
        mutations.append(f"{best_query} {term}".strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for query in mutations:
        normalized = query.strip()
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)
    return deduped[:5]


def run_goal_loop(goal_case: dict[str, Any], max_rounds: int, force_all_rounds: bool = False) -> dict[str, Any]:
    capability_report = refresh_source_capability(goal_case.get("providers"))
    platforms = _available_platforms(goal_case, capability_report)
    rounds: list[dict[str, Any]] = []
    queries = list(goal_case.get("seed_queries", []))
    best_goal_score = -1
    best_goal_run: dict[str, Any] | None = None
    all_runs: list[dict[str, Any]] = []

    for round_index in range(1, max_rounds + 1):
        previous_best_score = best_goal_score
        round_runs: list[dict[str, Any]] = []
        for query in queries:
            findings, baseline_score = _search_query(query, platforms)
            evaluation = evaluate_goal_case(goal_case, query, findings)
            record = {
                "round": round_index,
                "query": query,
                "baseline_score": baseline_score,
                "goal_score": int(evaluation.get("score", 0) or 0),
                "judge": evaluation.get("judge", ""),
                "matched_terms": evaluation.get("matched_terms", []),
                "missing_terms": evaluation.get("missing_terms", []),
                "rationale": evaluation.get("rationale", ""),
                "finding_count": len(findings),
                "sample_findings": [
                    {
                        "title": finding["title"],
                        "url": finding["url"],
                        "source": finding["source"],
                    }
                    for finding in findings[:5]
                ],
                "sample_urls": [finding["url"] for finding in findings[:5]],
            }
            round_runs.append(record)
            all_runs.append(record)
            if record["goal_score"] > best_goal_score:
                best_goal_score = record["goal_score"]
                best_goal_run = record

        round_runs.sort(key=lambda item: item["goal_score"], reverse=True)
        rounds.append({"round": round_index, "runs": round_runs})
        if not round_runs:
            break
        top = round_runs[0]
        if (not force_all_rounds) and top["goal_score"] >= int(goal_case.get("target_score", 100) or 100):
            break
        if (not force_all_rounds) and round_index > 1 and top["goal_score"] <= previous_best_score:
            break
        queries = _mutate_queries(top["query"], top, goal_case)
        if not queries:
            break

    baseline_best = max(all_runs, key=lambda item: item["baseline_score"], default=None)
    goal_best = max(all_runs, key=lambda item: item["goal_score"], default=None)
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "goal_id": goal_case.get("id", ""),
        "problem": goal_case.get("problem", ""),
        "providers_used": [platform["name"] for platform in platforms],
        "judge_model": (goal_best or {}).get("judge", ""),
        "baseline_best": baseline_best,
        "goal_best": goal_best,
        "improvement_vs_baseline": (
            int((goal_best or {}).get("goal_score", 0) or 0)
            - int((baseline_best or {}).get("goal_score", 0) or 0)
        ),
        "rounds": rounds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run goal-driven search loop")
    parser.add_argument(
        "--goal",
        type=str,
        default=str(GOAL_CASES_ROOT / "autosearch-goal-judge.json"),
        help="Path to goal case JSON",
    )
    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument(
        "--force-all-rounds",
        action="store_true",
        help="Keep iterating through all rounds even if target reached or no improvement",
    )
    args = parser.parse_args()

    goal_case = load_goal_case(Path(args.goal))
    result = run_goal_loop(goal_case, args.max_rounds, force_all_rounds=args.force_all_rounds)
    GOAL_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    run_path = GOAL_RUNS_ROOT / f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-{goal_case.get('id', 'goal')}.json"
    run_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nRun: {run_path}")


if __name__ == "__main__":
    main()
