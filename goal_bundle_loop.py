#!/usr/bin/env python3
"""Bundle-scored goal loop with separate judge and searcher roles."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation_harness import build_bundle, bundle_metrics
from goal_editor import GoalSearcher
from goal_judge import evaluate_goal_bundle
from goal_runtime import (
    archive_candidate_program,
    build_candidate_program,
    ensure_harness,
    load_accepted_program,
    runtime_paths,
    save_accepted_program,
)
from goal_services import (
    available_platforms as _available_platforms,
    merge_findings as _merge_findings,
    normalize_query_spec as _normalize_query_spec,
    query_key as _query_key,
    query_text as _query_text,
    replay_queries as _replay_queries,
    sample_findings as _sample_findings,
    search_query as _search_query,
)
from selector import candidate_rank, evaluate_acceptance
from source_capability import refresh_source_capability


REPO_ROOT = Path(__file__).resolve().parent
GOAL_CASES_ROOT = REPO_ROOT / "goal_cases"
GOAL_RUNS_ROOT = GOAL_CASES_ROOT / "runs"


def load_goal_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_run(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _best_prior_run(goal_id: str) -> tuple[Path | None, dict[str, Any] | None]:
    best_path: Path | None = None
    best_payload: dict[str, Any] | None = None
    best_score = -1
    if not GOAL_RUNS_ROOT.exists():
        return None, None
    for path in sorted(GOAL_RUNS_ROOT.glob(f"*-{goal_id}-bundle.json")):
        payload = _load_run(path)
        if not payload:
            continue
        score = int(((payload.get("bundle_final") or {}).get("score") or 0))
        if score > best_score:
            best_score = score
            best_path = path
            best_payload = payload
    return best_path, best_payload


def _accepted_queries_from_run(payload: dict[str, Any]) -> list[dict[str, Any]]:
    accepted_queries: list[dict[str, Any]] = []
    warm_start = payload.get("warm_start") or {}
    for item in list(warm_start.get("query_runs") or []):
        spec = _normalize_query_spec(item.get("query_spec") or {})
        if spec["text"] and spec not in accepted_queries:
            accepted_queries.append(spec)
    for round_item in payload.get("rounds", []):
        if not round_item.get("accepted"):
            continue
        for query in round_item.get("queries", []):
            spec = _normalize_query_spec(query)
            if spec["text"] and spec not in accepted_queries:
                accepted_queries.append(spec)
    return accepted_queries

def _promote_compatible_archive_candidate(
    *,
    goal_case: dict[str, Any],
    accepted_program: dict[str, Any],
    bundle_state: dict[str, Any],
    harness: dict[str, Any],
    platforms: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    archive_dir = runtime_paths(str(goal_case.get("id") or "goal"))["program_archive"]
    if not archive_dir.exists():
        return accepted_program, bundle_state, {
            "score": bundle_state.get("score", 0),
            "dimension_scores": bundle_state.get("dimension_scores", {}),
            "missing_dimensions": bundle_state.get("missing_dimensions", []),
            "matched_dimensions": bundle_state.get("matched_dimensions", []),
            "rationale": bundle_state.get("rationale", ""),
            "judge": bundle_state.get("judge", ""),
        }, None

    compatible: list[dict[str, Any]] = []
    for path in sorted(archive_dir.glob("*.json")):
        payload = _load_run(path)
        if not payload:
            continue
        candidate_program = dict(payload.get("candidate_program") or {})
        result = dict(payload.get("result") or {})
        selection = dict(result.get("selection") or {})
        if candidate_program.get("parent_program_id") != accepted_program.get("program_id"):
            continue
        if int(selection.get("current_score", -1) or -1) != int(bundle_state.get("score", 0) or 0):
            continue
        reevaluated = evaluate_acceptance(
            current_state=bundle_state,
            candidate_score=int(result.get("score", 0) or 0),
            candidate_dimensions=dict(result.get("dimension_scores") or {}),
            candidate_metrics=dict(result.get("harness_metrics") or {}),
            harness=harness,
            candidate_finding_count=int((result.get("harness_metrics") or {}).get("total_findings", 0) or 0),
        )
        if not reevaluated.get("accepted"):
            continue
        compatible.append({
            "program": candidate_program,
            "score": int(result.get("score", 0) or 0),
            "dimension_scores": dict(result.get("dimension_scores") or {}),
            "harness_metrics": dict(result.get("harness_metrics") or {}),
            "selection": reevaluated,
            "archive_path": str(path),
        })

    if not compatible:
        return accepted_program, bundle_state, {
            "score": bundle_state.get("score", 0),
            "dimension_scores": bundle_state.get("dimension_scores", {}),
            "missing_dimensions": bundle_state.get("missing_dimensions", []),
            "matched_dimensions": bundle_state.get("matched_dimensions", []),
            "rationale": bundle_state.get("rationale", ""),
            "judge": bundle_state.get("judge", ""),
        }, None

    best = max(compatible, key=candidate_rank)
    promoted_queries = list(bundle_state.get("accepted_queries", [])) + [
        _normalize_query_spec(query) for query in list(best["program"].get("queries") or [])
    ]
    replay_runs, replay_findings = _replay_queries(promoted_queries, platforms)
    replay_bundle = build_bundle([], replay_findings, harness)
    replay_judge = evaluate_goal_bundle(goal_case, replay_bundle)
    promoted_bundle_state = {
        "accepted_findings": replay_bundle,
        "accepted_queries": promoted_queries,
        "score": int(replay_judge.get("score", 0) or 0),
        "judge": replay_judge.get("judge", ""),
        "dimension_scores": replay_judge.get("dimension_scores", {}),
        "missing_dimensions": replay_judge.get("missing_dimensions", []),
        "rationale": replay_judge.get("rationale", ""),
        "matched_dimensions": replay_judge.get("matched_dimensions", []),
    }
    promoted_program = {
        **best["program"],
        "queries": promoted_queries,
        "score": promoted_bundle_state["score"],
        "dimension_scores": dict(promoted_bundle_state["dimension_scores"]),
        "accepted_at": datetime.now().astimezone().isoformat(),
    }
    save_accepted_program(str(goal_case.get("id") or "goal"), promoted_program)
    return promoted_program, promoted_bundle_state, replay_judge, {
        "program_id": promoted_program["program_id"],
        "archive_path": best["archive_path"],
        "selection": best["selection"],
        "query_runs": replay_runs,
        "replayed_score": promoted_bundle_state["score"],
    }


def run_goal_bundle_loop(goal_case: dict[str, Any], max_rounds: int = 8) -> dict[str, Any]:
    capability_report = refresh_source_capability(goal_case.get("providers"))
    platforms = _available_platforms(goal_case, capability_report)
    harness = ensure_harness(goal_case)
    searcher = GoalSearcher(goal_case)
    available_provider_names = [platform["name"] for platform in platforms]
    accepted_program = load_accepted_program(goal_case, available_provider_names)
    tried_queries: set[str] = set()
    rounds: list[dict[str, Any]] = []
    no_improvement_rounds = 0
    warm_start: dict[str, Any] | None = None

    bundle_state = {
        "accepted_findings": [],
        "accepted_queries": [],
        "score": 0,
        "judge": "",
        "dimension_scores": {},
        "missing_dimensions": list(goal_case.get("dimension_queries", {}).keys()),
        "rationale": "empty bundle",
    }

    judge_result: dict[str, Any] = {
        "score": 0,
        "dimension_scores": {},
        "missing_dimensions": list(goal_case.get("dimension_queries", {}).keys()),
        "matched_dimensions": [],
        "rationale": "empty bundle",
    }
    target_score = int(goal_case.get("target_score", 100) or 100)

    prior_path, prior_payload = _best_prior_run(str(goal_case.get("id") or ""))
    prior_queries = list(accepted_program.get("queries") or [])
    prior_score = int((((prior_payload or {}).get("bundle_final") or {}).get("score") or 0))
    accepted_score = int(accepted_program.get("score", 0) or 0)
    if prior_payload and (not prior_queries or prior_score > accepted_score):
        prior_queries = _accepted_queries_from_run(prior_payload)
        if prior_queries:
            accepted_program["queries"] = list(prior_queries)
            accepted_program["score"] = prior_score
            accepted_program["dimension_scores"] = dict(((prior_payload.get("bundle_final") or {}).get("dimension_scores") or {}))
    if prior_queries:
        if prior_queries:
            replay_runs, replay_findings = _replay_queries(prior_queries, platforms)
            replay_bundle = build_bundle([], replay_findings, harness)
            replay_judge = evaluate_goal_bundle(goal_case, replay_bundle)
            bundle_state = {
                "accepted_findings": replay_bundle,
                "accepted_queries": list(prior_queries),
                "score": int(replay_judge.get("score", 0) or 0),
                "judge": replay_judge.get("judge", ""),
                "dimension_scores": replay_judge.get("dimension_scores", {}),
                "missing_dimensions": replay_judge.get("missing_dimensions", []),
                "rationale": replay_judge.get("rationale", ""),
                "matched_dimensions": replay_judge.get("matched_dimensions", []),
            }
            judge_result = replay_judge
            accepted_program["score"] = bundle_state["score"]
            accepted_program["dimension_scores"] = dict(bundle_state["dimension_scores"])
            for query in prior_queries:
                tried_queries.add(_query_key(query))
            warm_start = {
                "source_run": str(prior_path) if prior_path else "",
                "replayed_query_count": len(prior_queries),
                "replayed_finding_count": len(replay_bundle),
                "replayed_score": bundle_state["score"],
                "query_runs": replay_runs,
            }
            accepted_program, bundle_state, judge_result, promoted = _promote_compatible_archive_candidate(
                goal_case=goal_case,
                accepted_program=accepted_program,
                bundle_state=bundle_state,
                harness=harness,
                platforms=platforms,
            )
            if promoted:
                for query in accepted_program.get("queries", []):
                    tried_queries.add(_query_key(query))
                warm_start = {
                    **warm_start,
                    "promoted_archive_candidate": promoted,
                }

    for round_index in range(1, max_rounds + 1):
        if round_index == 1 and not bundle_state["accepted_queries"]:
            candidate_plans = [{"label": "seed", "queries": searcher.initial_queries()}]
        else:
            candidate_plans = searcher.candidate_plans(
                bundle_state=bundle_state,
                judge_result=judge_result,
                tried_queries=tried_queries,
                available_providers=available_provider_names,
                round_history=rounds,
                plan_count=int(accepted_program.get("plan_count", 3) or 3),
                max_queries=int(accepted_program.get("max_queries", 5) or 5),
            )
        if not candidate_plans:
            break

        strategy_summaries: list[dict[str, Any]] = []
        best_candidate: dict[str, Any] | None = None
        for plan_index, plan in enumerate(candidate_plans, start=1):
            candidate_program = build_candidate_program(
                goal_id=str(goal_case.get("id") or "goal"),
                parent_program=accepted_program,
                label=str(plan.get("label") or f"plan-{plan_index}"),
                queries=list(plan.get("queries") or []),
                provider_mix=available_provider_names,
                round_index=round_index,
                candidate_index=plan_index,
            )
            query_runs: list[dict[str, Any]] = []
            round_findings: list[dict[str, Any]] = []
            plan_query_keys: list[str] = []
            for query in plan.get("queries", []):
                query_key = _query_key(query)
                if query_key in tried_queries:
                    continue
                plan_query_keys.append(query_key)
                run = _search_query(query, platforms)
                query_runs.append({
                    "query": run["query"],
                    "query_spec": run["query_spec"],
                    "baseline_score": run["baseline_score"],
                    "finding_count": len(run["findings"]),
                    "sample_findings": _sample_findings(run["findings"], limit=5),
                })
                round_findings.extend(run["findings"])
            if not query_runs:
                strategy_summaries.append({
                    "label": plan.get("label", f"plan-{plan_index}"),
                    "program_id": candidate_program["program_id"],
                    "queries": plan.get("queries", []),
                    "query_runs": [],
                    "candidate_score": bundle_state["score"],
                    "matched_dimensions": list(bundle_state.get("matched_dimensions", [])),
                    "missing_dimensions": list(bundle_state.get("missing_dimensions", [])),
                    "sample_bundle": _sample_findings(bundle_state.get("accepted_findings", []), limit=6),
                    "rationale": "all plan queries already tried",
                })
                continue

            candidate_bundle = build_bundle(bundle_state["accepted_findings"], round_findings, harness)
            plan_judge = evaluate_goal_bundle(goal_case, candidate_bundle)
            harness_state = bundle_metrics(
                candidate_bundle,
                previous_bundle=bundle_state.get("accepted_findings", []),
            )
            selection = evaluate_acceptance(
                current_state=bundle_state,
                candidate_score=int(plan_judge.get("score", 0) or 0),
                candidate_dimensions=plan_judge.get("dimension_scores", {}),
                candidate_metrics=harness_state,
                harness=harness,
                candidate_finding_count=len(candidate_bundle),
            )
            candidate = {
                "program": candidate_program,
                "label": plan.get("label", f"plan-{plan_index}"),
                "queries": plan.get("queries", []),
                "query_keys": plan_query_keys,
                "query_runs": query_runs,
                "round_findings": round_findings,
                "bundle": candidate_bundle,
                "judge_result": plan_judge,
                "score": int(plan_judge.get("score", 0) or 0),
                "dimension_scores": plan_judge.get("dimension_scores", {}),
                "matched_count": len(plan_judge.get("matched_dimensions", []) or []),
                "finding_count": len(candidate_bundle),
                "harness_metrics": harness_state,
                "selection": selection,
                "plan_index": plan_index,
            }
            archive_path = archive_candidate_program(
                str(goal_case.get("id") or "goal"),
                candidate_program,
                result={
                    "score": candidate["score"],
                    "dimension_scores": candidate["dimension_scores"],
                    "harness_metrics": harness_state,
                    "selection": selection,
                    "query_runs": query_runs,
                },
            )
            strategy_summaries.append({
                "label": candidate["label"],
                "program_id": candidate_program["program_id"],
                "program_archive": str(archive_path),
                "queries": candidate["queries"],
                "query_runs": query_runs,
                "candidate_score": candidate["score"],
                "matched_dimensions": plan_judge.get("matched_dimensions", []),
                "missing_dimensions": plan_judge.get("missing_dimensions", []),
                "harness_metrics": harness_state,
                "selection": selection,
                "sample_bundle": _sample_findings(candidate_bundle, limit=6),
                "rationale": plan_judge.get("rationale", ""),
            })
            if (
                best_candidate is None
                or (
                    not candidate["selection"]["anti_cheat_failures"]
                    and best_candidate["selection"]["anti_cheat_failures"]
                )
                or (
                    (not candidate["selection"]["anti_cheat_failures"])
                    == (not best_candidate["selection"]["anti_cheat_failures"])
                    and candidate_rank(candidate) > candidate_rank(best_candidate)
                )
            ):
                best_candidate = candidate

        if best_candidate is None:
            break

        for query_key in best_candidate["query_keys"]:
            tried_queries.add(query_key)

        judge_result = best_candidate["judge_result"]
        candidate_score = best_candidate["score"]
        accepted = bool(best_candidate["selection"]["accepted"])
        if accepted:
            bundle_state = {
                "accepted_findings": best_candidate["bundle"],
                "accepted_queries": list(bundle_state["accepted_queries"]) + [
                    _normalize_query_spec(query) for query in best_candidate["queries"]
                ],
                "score": candidate_score,
                "judge": judge_result.get("judge", ""),
                "dimension_scores": judge_result.get("dimension_scores", {}),
                "missing_dimensions": judge_result.get("missing_dimensions", []),
                "rationale": judge_result.get("rationale", ""),
                "matched_dimensions": judge_result.get("matched_dimensions", []),
            }
            accepted_program = {
                **best_candidate["program"],
                "queries": list(bundle_state["accepted_queries"]),
                "score": candidate_score,
                "dimension_scores": dict(judge_result.get("dimension_scores", {})),
                "accepted_at": datetime.now().astimezone().isoformat(),
            }
            save_accepted_program(str(goal_case.get("id") or "goal"), accepted_program)
            no_improvement_rounds = 0
        else:
            no_improvement_rounds += 1

        rounds.append({
            "round": round_index,
            "queries": best_candidate["queries"],
            "accepted_program_id": accepted_program.get("program_id"),
            "selected_program_id": best_candidate["program"]["program_id"],
            "strategy_candidates": strategy_summaries,
            "editor_plans": strategy_summaries,
            "selected_plan_label": best_candidate["label"],
            "query_runs": best_candidate["query_runs"],
            "added_finding_count": len(best_candidate["round_findings"]),
            "candidate_score": candidate_score,
            "accepted": accepted,
            "selection": best_candidate["selection"],
            "harness_metrics": best_candidate["harness_metrics"],
            "bundle_score_after_round": bundle_state["score"],
            "dimension_scores": judge_result.get("dimension_scores", {}),
            "missing_dimensions": judge_result.get("missing_dimensions", []),
            "sample_bundle": _sample_findings(best_candidate["bundle"], limit=8),
            "rationale": judge_result.get("rationale", ""),
        })

        if bundle_state["score"] >= target_score:
            break
        if no_improvement_rounds >= 3:
            break

    baseline_best = None
    for round_item in rounds:
        for run in round_item["query_runs"]:
            if baseline_best is None or int(run["baseline_score"]) > int(baseline_best["baseline_score"]):
                baseline_best = run

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "goal_id": goal_case.get("id", ""),
        "problem": goal_case.get("problem", ""),
        "target_score": target_score,
        "providers_used": [platform["name"] for platform in platforms],
        "judge_model": bundle_state.get("judge", ""),
        "evaluation_harness": harness,
        "accepted_program": accepted_program,
        "warm_start": warm_start,
        "baseline_best": baseline_best,
        "bundle_final": {
            "score": bundle_state["score"],
            "dimension_scores": bundle_state.get("dimension_scores", {}),
            "missing_dimensions": bundle_state.get("missing_dimensions", []),
            "matched_dimensions": bundle_state.get("matched_dimensions", []),
            "accepted_query_count": len(bundle_state.get("accepted_queries", [])),
            "accepted_finding_count": len(bundle_state.get("accepted_findings", [])),
            "sample_findings": _sample_findings(bundle_state.get("accepted_findings", []), limit=10),
            "rationale": bundle_state.get("rationale", ""),
        },
        "improvement_vs_baseline": None,
        "rounds": rounds,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run bundle-scored goal loop")
    parser.add_argument(
        "--goal",
        type=str,
        required=True,
        help="Path to goal case JSON",
    )
    parser.add_argument("--max-rounds", type=int, default=8)
    args = parser.parse_args()

    goal_case = load_goal_case(Path(args.goal))
    result = run_goal_bundle_loop(goal_case, args.max_rounds)
    GOAL_RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    run_path = GOAL_RUNS_ROOT / (
        f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-{goal_case.get('id', 'bundle-goal')}-bundle.json"
    )
    run_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nRun: {run_path}")


if __name__ == "__main__":
    main()
