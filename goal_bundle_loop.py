#!/usr/bin/env python3
"""Bundle-scored goal loop with separate judge and searcher roles."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation_harness import build_bundle, bundle_metrics
from evidence.legacy_adapter import normalize_legacy_finding
from evidence_index import LocalEvidenceIndex
from goal_editor import GoalSearcher
from goal_judge import evaluate_goal_bundle
from goal_runtime import (
    archive_candidate_program,
    build_candidate_program,
    ensure_harness,
    load_accepted_program,
    save_population_snapshot,
    runtime_paths,
    save_accepted_program,
)
from goal_services import (
    available_platforms as _available_platforms,
    merge_findings as _merge_findings,
    normalize_query_spec as _normalize_query_spec,
    platforms_for_provider_mix as _platforms_for_provider_mix,
    query_key as _query_key,
    query_text as _query_text,
    replay_queries as _replay_queries,
    restrict_query_to_provider_mix as _restrict_query_to_provider_mix,
    sample_findings as _sample_findings,
    search_query as _search_query,
)
from research import build_research_plan, execute_research_plan, synthesize_research_round
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


def _normalized_findings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_legacy_finding(item) for item in list(items or [])]


def _harness_for_program(harness: dict[str, Any], program: dict[str, Any]) -> dict[str, Any]:
    effective = json.loads(json.dumps(harness))
    sampling_policy = dict(program.get("sampling_policy") or {})
    bundle_policy = dict(effective.get("bundle_policy") or {})
    if "bundle_per_query_cap" in sampling_policy:
        bundle_policy["per_query_cap"] = int(sampling_policy.get("bundle_per_query_cap") or bundle_policy.get("per_query_cap", 5))
    if "bundle_per_source_cap" in sampling_policy:
        bundle_policy["per_source_cap"] = int(sampling_policy.get("bundle_per_source_cap") or bundle_policy.get("per_source_cap", 18))
    if "bundle_per_domain_cap" in sampling_policy:
        bundle_policy["per_domain_cap"] = int(sampling_policy.get("bundle_per_domain_cap") or bundle_policy.get("per_domain_cap", 18))
    effective["bundle_policy"] = bundle_policy
    return effective


def _update_plateau_state(
    plateau_state: dict[str, Any],
    *,
    candidate_score: int,
    current_score: int,
    current_dimensions: dict[str, Any],
    candidate_dimensions: dict[str, Any],
) -> dict[str, Any]:
    next_state = dict(plateau_state or {})
    dimension_stagnation = {
        str(key): int(value or 0)
        for key, value in dict(next_state.get("dimension_stagnation") or {}).items()
    }
    improved = int(candidate_score or 0) > int(current_score or 0)
    next_state["best_score"] = max(int(next_state.get("best_score", 0) or 0), int(candidate_score or 0))
    next_state["stagnant_rounds"] = 0 if improved else int(next_state.get("stagnant_rounds", 0) or 0) + 1
    current_dimensions = dict(current_dimensions or {})
    candidate_dimensions = dict(candidate_dimensions or {})
    for dim_id in set(current_dimensions) | set(candidate_dimensions):
        previous = int(current_dimensions.get(dim_id, 0) or 0)
        current = int(candidate_dimensions.get(dim_id, 0) or 0)
        if current > previous:
            dimension_stagnation[dim_id] = 0
        else:
            dimension_stagnation[dim_id] = int(dimension_stagnation.get(dim_id, 0) or 0) + 1
    next_state["dimension_stagnation"] = dimension_stagnation
    if next_state["stagnant_rounds"] >= 3:
        next_state["practical_ceiling"] = int(next_state.get("best_score", candidate_score) or candidate_score)
    return next_state


def _updated_evolution_stats(
    current_program: dict[str, Any],
    *,
    population: list[dict[str, Any]],
    accepted: bool,
    accepted_program: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stats = dict(current_program.get("evolution_stats") or {})
    stats["accepted_rounds"] = int(stats.get("accepted_rounds", 0) or 0) + (1 if accepted else 0)
    stats["rejected_rounds"] = int(stats.get("rejected_rounds", 0) or 0) + (0 if accepted else 1)
    family_best_scores = dict(stats.get("family_best_scores") or {})
    if accepted_program is not None:
        family_id = str(accepted_program.get("family_id") or "")
        if family_id:
            family_best_scores[family_id] = max(
                int(family_best_scores.get(family_id, 0) or 0),
                int(accepted_program.get("score", 0) or 0),
            )
    stats["family_best_scores"] = family_best_scores
    stats["last_population_summary"] = {
        "population_size": len(population),
        "branch_counts": {
            str(item.get("branch_id") or ""): sum(
                1 for other in population if str(other.get("branch_id") or "") == str(item.get("branch_id") or "")
            )
            for item in population
            if str(item.get("branch_id") or "")
        },
        "family_counts": {
            str(item.get("family_id") or ""): sum(
                1 for other in population if str(other.get("family_id") or "") == str(item.get("family_id") or "")
            )
            for item in population
            if str(item.get("family_id") or "")
        },
    }
    return stats


def _selected_branch_id(round_item: dict[str, Any]) -> str:
    selected_program_id = str(round_item.get("selected_program_id") or "")
    for candidate in list(round_item.get("candidate_population") or []):
        if str(candidate.get("program_id") or "") == selected_program_id:
            return str(candidate.get("branch_id") or "")
    return ""


def _branch_stale_rounds(rounds: list[dict[str, Any]], branch_id: str) -> int:
    if not branch_id:
        return 0
    stale = 0
    for round_item in reversed(list(rounds or [])):
        if _selected_branch_id(round_item) != branch_id:
            continue
        if bool(round_item.get("accepted")):
            break
        stale += 1
    return stale


def _population_candidates(
    population: list[dict[str, Any]],
    *,
    prefer_diverse_branches: bool,
) -> list[dict[str, Any]]:
    ranked = sorted(population, key=candidate_rank, reverse=True)
    if not prefer_diverse_branches:
        return ranked
    best_by_branch: dict[str, dict[str, Any]] = {}
    fallback: list[dict[str, Any]] = []
    for item in ranked:
        branch_id = str(item.get("branch_id") or "")
        if not branch_id:
            fallback.append(item)
            continue
        best_by_branch.setdefault(branch_id, item)
    return list(best_by_branch.values()) + fallback

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
            current_program=accepted_program,
            candidate_program=candidate_program,
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
    effective_harness = _harness_for_program(harness, best["program"])
    replay_runs, replay_findings = _replay_queries(
        promoted_queries,
        platforms,
        sampling_policy=dict(best["program"].get("sampling_policy") or {}),
    )
    replay_bundle = build_bundle([], replay_findings, effective_harness)
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


def run_goal_bundle_loop(
    goal_case: dict[str, Any],
    max_rounds: int = 8,
    *,
    plan_count_override: int | None = None,
    max_queries_override: int | None = None,
    target_score_override: int | None = None,
    plateau_rounds_override: int | None = None,
) -> dict[str, Any]:
    capability_report = refresh_source_capability(goal_case.get("providers"))
    platforms = _available_platforms(goal_case, capability_report)
    harness = ensure_harness(goal_case)
    searcher = GoalSearcher(goal_case)
    available_provider_names = [platform["name"] for platform in platforms]
    accepted_program = load_accepted_program(goal_case, available_provider_names)
    index = LocalEvidenceIndex(runtime_paths(str(goal_case.get("id") or "goal"))["evidence_index"])
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
    target_score = int(target_score_override or goal_case.get("target_score", 100) or 100)

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
            effective_harness = _harness_for_program(harness, accepted_program)
            replay_runs, replay_findings = _replay_queries(
                prior_queries,
                platforms,
                sampling_policy=dict(accepted_program.get("sampling_policy") or {}),
            )
            replay_bundle = build_bundle([], replay_findings, effective_harness)
            replay_judge = evaluate_goal_bundle(goal_case, replay_bundle)
            bundle_state = {
                "accepted_findings": _normalized_findings(replay_bundle),
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
            index.add(list(bundle_state["accepted_findings"]))
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

    population_policy = dict(accepted_program.get("population_policy") or {})
    effective_plan_count = int(plan_count_override or population_policy.get("plan_count", accepted_program.get("plan_count", 3)) or 3)
    effective_max_queries = int(max_queries_override or population_policy.get("max_queries", accepted_program.get("max_queries", 5)) or 5)
    plateau_rounds_limit = int(
        plateau_rounds_override
        or (accepted_program.get("stop_rules") or {}).get("plateau_rounds", 3)
        or 3
    )
    stop_reason = "max_rounds_reached"

    for round_index in range(1, max_rounds + 1):
        if round_index == 1 and not bundle_state["accepted_queries"]:
            initial_queries = searcher.initial_queries()[:effective_max_queries]
            if initial_queries:
                candidate_plans = [{"label": "seed", "queries": initial_queries}]
            else:
                candidate_plans = build_research_plan(
                    searcher=searcher,
                    bundle_state=bundle_state,
                    judge_result=judge_result,
                    tried_queries=tried_queries,
                    available_providers=available_provider_names,
                    active_program=accepted_program,
                    round_history=rounds,
                    plan_count=effective_plan_count,
                    max_queries=effective_max_queries,
                    local_evidence_records=index.load_all(),
                )
        else:
            candidate_plans = build_research_plan(
                searcher=searcher,
                bundle_state=bundle_state,
                judge_result=judge_result,
                tried_queries=tried_queries,
                available_providers=available_provider_names,
                active_program=accepted_program,
                round_history=rounds,
                plan_count=effective_plan_count,
                max_queries=effective_max_queries,
                local_evidence_records=index.load_all(),
            )
        if not candidate_plans:
            break

        strategy_summaries: list[dict[str, Any]] = []
        best_candidate: dict[str, Any] | None = None
        population: list[dict[str, Any]] = []
        for plan_index, plan in enumerate(candidate_plans, start=1):
            candidate_program = build_candidate_program(
                goal_id=str(goal_case.get("id") or "goal"),
                parent_program=accepted_program,
                label=str(plan.get("label") or f"plan-{plan_index}"),
                queries=list(plan.get("queries") or []),
                provider_mix=available_provider_names,
                round_index=round_index,
                candidate_index=plan_index,
                program_overrides=dict(plan.get("program_overrides") or {}),
            )
            max_branch_depth = int(population_policy.get("max_branch_depth", 0) or 0)
            if max_branch_depth and int(candidate_program.get("branch_depth", 0) or 0) > max_branch_depth:
                strategy_summaries.append({
                    "label": plan.get("label", f"plan-{plan_index}"),
                    "program_id": candidate_program["program_id"],
                    "queries": plan.get("queries", []),
                    "graph_node": str(plan.get("graph_node") or ""),
                    "graph_edges": list(plan.get("graph_edges") or []),
                    "provider_mix": list(candidate_program.get("provider_mix") or []),
                    "query_runs": [],
                    "candidate_score": bundle_state["score"],
                    "matched_dimensions": list(bundle_state.get("matched_dimensions", [])),
                    "missing_dimensions": list(bundle_state.get("missing_dimensions", [])),
                    "sample_bundle": _sample_findings(bundle_state.get("accepted_findings", []), limit=6),
                    "rationale": "branch depth exceeds population policy",
                })
                continue
            stale_rounds_limit = int(population_policy.get("stale_branch_rounds", 0) or 0)
            if stale_rounds_limit and _branch_stale_rounds(rounds, str(candidate_program.get("branch_id") or "")) >= stale_rounds_limit:
                strategy_summaries.append({
                    "label": plan.get("label", f"plan-{plan_index}"),
                    "program_id": candidate_program["program_id"],
                    "queries": plan.get("queries", []),
                    "graph_node": str(plan.get("graph_node") or ""),
                    "graph_edges": list(plan.get("graph_edges") or []),
                    "provider_mix": list(candidate_program.get("provider_mix") or []),
                    "query_runs": [],
                    "candidate_score": bundle_state["score"],
                    "matched_dimensions": list(bundle_state.get("matched_dimensions", [])),
                    "missing_dimensions": list(bundle_state.get("missing_dimensions", [])),
                    "sample_bundle": _sample_findings(bundle_state.get("accepted_findings", []), limit=6),
                    "rationale": "branch retired by stale branch policy",
                })
                continue
            search_backends = list(candidate_program.get("search_backends") or candidate_program.get("provider_mix") or [])
            candidate_platforms = _platforms_for_provider_mix(platforms, search_backends)
            candidate_sampling_policy = {
                **dict(candidate_program.get("sampling_policy") or {}),
                **dict(candidate_program.get("acquisition_policy") or {}),
                **dict(candidate_program.get("evidence_policy") or {}),
            }
            execution = execute_research_plan(
                {
                    "label": plan.get("label", f"plan-{plan_index}"),
                    "intents": list(plan.get("queries") or []),
                    "role": plan.get("role", ""),
                    "stage": plan.get("stage", ""),
                    "graph_node": plan.get("graph_node", ""),
                    "graph_edges": list(plan.get("graph_edges") or []),
                    "branch_targets": list(plan.get("branch_targets") or []),
                    "local_evidence_records": list(plan.get("local_evidence_records") or []),
                },
                default_platforms=candidate_platforms,
                provider_mix=list(candidate_program.get("provider_mix") or []),
                backend_roles=dict(candidate_program.get("backend_roles") or {}),
                sampling_policy=candidate_sampling_policy,
                tried_queries=tried_queries,
                query_key_fn=_query_key,
                local_evidence_records=index.load_all(),
            )
            query_runs = list(execution["query_runs"])
            round_findings = _normalized_findings(list(execution["findings"]))
            plan_query_keys = list(execution["query_keys"])
            if not query_runs:
                strategy_summaries.append({
                    "label": plan.get("label", f"plan-{plan_index}"),
                    "program_id": candidate_program["program_id"],
                    "queries": plan.get("queries", []),
                    "graph_node": str(plan.get("graph_node") or ""),
                    "graph_edges": list(plan.get("graph_edges") or []),
                    "provider_mix": list(candidate_program.get("provider_mix") or []),
                    "query_runs": [],
                    "candidate_score": bundle_state["score"],
                    "matched_dimensions": list(bundle_state.get("matched_dimensions", [])),
                    "missing_dimensions": list(bundle_state.get("missing_dimensions", [])),
                    "sample_bundle": _sample_findings(bundle_state.get("accepted_findings", []), limit=6),
                    "rationale": "all plan queries already tried",
                })
                continue

            effective_harness = _harness_for_program(harness, candidate_program)
            synthesized = synthesize_research_round(
                goal_case,
                existing_findings=_normalized_findings(bundle_state["accepted_findings"]),
                round_findings=round_findings,
                harness=effective_harness,
            )
            candidate_bundle = list(synthesized["bundle"])
            plan_judge = dict(synthesized["judge_result"])
            harness_state = dict(synthesized["harness_metrics"])
            selection = evaluate_acceptance(
                current_state=bundle_state,
                candidate_score=int(plan_judge.get("score", 0) or 0),
                candidate_dimensions=plan_judge.get("dimension_scores", {}),
                candidate_metrics=harness_state,
                harness=effective_harness,
                candidate_finding_count=len(candidate_bundle),
                current_program=accepted_program,
                candidate_program=candidate_program,
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
                "graph_node": str(execution.get("graph_node") or ""),
                "graph_edges": list(execution.get("graph_edges") or []),
                "branch_targets": list(execution.get("branch_targets") or []),
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
                "graph_node": candidate.get("graph_node", ""),
                "graph_edges": candidate.get("graph_edges", []),
                "branch_targets": candidate.get("branch_targets", []),
                "provider_mix": list(candidate_program.get("provider_mix") or []),
                "query_runs": query_runs,
                "candidate_score": candidate["score"],
                "matched_dimensions": plan_judge.get("matched_dimensions", []),
                "missing_dimensions": plan_judge.get("missing_dimensions", []),
                "harness_metrics": harness_state,
                "selection": selection,
                "sample_bundle": _sample_findings(candidate_bundle, limit=6),
                "rationale": plan_judge.get("rationale", ""),
                "routeable_output": synthesized.get("routeable_output", {}),
            })
            population.append({
                "program_id": candidate_program["program_id"],
                "parent_program_id": candidate_program.get("parent_program_id"),
                "label": candidate["label"],
                "provider_mix": list(candidate_program.get("provider_mix") or []),
                "search_backends": list(candidate_program.get("search_backends") or []),
                "branch_id": str(candidate_program.get("branch_id") or ""),
                "family_id": str(candidate_program.get("family_id") or ""),
                "branch_root_program_id": str(candidate_program.get("branch_root_program_id") or ""),
                "branch_depth": int(candidate_program.get("branch_depth", 0) or 0),
                "repair_depth": int(candidate_program.get("repair_depth", 0) or 0),
                "mutation_kind": str(candidate_program.get("mutation_kind") or ""),
                "mutation_history": list(candidate_program.get("mutation_history") or []),
                "score": candidate["score"],
                "result": {
                    "score": candidate["score"],
                    "dimension_scores": dict(candidate["dimension_scores"]),
                },
                "dimension_scores": dict(candidate["dimension_scores"]),
                "selection": selection,
                "harness_metrics": harness_state,
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

        effective_population = _population_candidates(
            population,
            prefer_diverse_branches=bool(population_policy.get("prefer_diverse_branches", False)),
        )
        population_paths = save_population_snapshot(
            str(goal_case.get("id") or "goal"),
            round_index,
            effective_population,
        )

        for query_key in best_candidate["query_keys"]:
            tried_queries.add(query_key)

        judge_result = best_candidate["judge_result"]
        candidate_score = best_candidate["score"]
        accepted = bool(best_candidate["selection"]["accepted"])
        previous_score = int(bundle_state.get("score", 0) or 0)
        previous_dimensions = dict(bundle_state.get("dimension_scores") or {})
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
                "plateau_state": _update_plateau_state(
                    dict(accepted_program.get("plateau_state") or {}),
                    candidate_score=candidate_score,
                    current_score=previous_score,
                    current_dimensions=previous_dimensions,
                    candidate_dimensions=dict(judge_result.get("dimension_scores") or {}),
                ),
                "evolution_stats": _updated_evolution_stats(
                    accepted_program,
                    population=population,
                    accepted=True,
                    accepted_program={
                        **best_candidate["program"],
                        "score": candidate_score,
                    },
                ),
                "accepted_at": datetime.now().astimezone().isoformat(),
            }
            save_accepted_program(str(goal_case.get("id") or "goal"), accepted_program)
            index.add(list(bundle_state["accepted_findings"]))
            no_improvement_rounds = 0
        else:
            no_improvement_rounds += 1
            accepted_program = {
                **accepted_program,
                "plateau_state": _update_plateau_state(
                    dict(accepted_program.get("plateau_state") or {}),
                    candidate_score=candidate_score,
                    current_score=previous_score,
                    current_dimensions=previous_dimensions,
                    candidate_dimensions=dict(judge_result.get("dimension_scores") or {}),
                ),
                "evolution_stats": _updated_evolution_stats(
                    accepted_program,
                    population=population,
                    accepted=False,
                ),
            }

        rounds.append({
            "round": round_index,
            "queries": best_candidate["queries"],
            "accepted_program_id": accepted_program.get("program_id"),
            "selected_program_id": best_candidate["program"]["program_id"],
            "strategy_candidates": strategy_summaries,
            "candidate_population": effective_population,
            "population_snapshot": {key: str(value) for key, value in population_paths.items()},
            "editor_plans": strategy_summaries,
            "selected_plan_label": best_candidate["label"],
            "graph_node": str(best_candidate.get("graph_node") or ""),
            "graph_edges": list(best_candidate.get("graph_edges") or []),
            "branch_targets": list(best_candidate.get("branch_targets") or []),
            "query_runs": best_candidate["query_runs"],
            "added_finding_count": len(best_candidate["round_findings"]),
            "candidate_score": candidate_score,
            "accepted": accepted,
            "round_role": str((best_candidate["program"] or {}).get("current_role") or ""),
            "selection": best_candidate["selection"],
            "harness_metrics": best_candidate["harness_metrics"],
            "bundle_score_after_round": bundle_state["score"],
            "dimension_scores": judge_result.get("dimension_scores", {}),
            "missing_dimensions": judge_result.get("missing_dimensions", []),
            "sample_bundle": _sample_findings(best_candidate["bundle"], limit=8),
            "rationale": judge_result.get("rationale", ""),
            "routeable_output": next(
                (
                    summary.get("routeable_output", {})
                    for summary in strategy_summaries
                    if str(summary.get("program_id") or "") == str(best_candidate["program"]["program_id"] or "")
                ),
                {},
            ),
        })

        if bundle_state["score"] >= target_score:
            stop_reason = "target_score_reached"
            break
        if no_improvement_rounds >= plateau_rounds_limit:
            stop_reason = "plateau_detected"
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
        "plateau_rounds_limit": plateau_rounds_limit,
        "providers_used": [platform["name"] for platform in platforms],
        "judge_model": bundle_state.get("judge", ""),
        "evaluation_harness": harness,
        "accepted_program": accepted_program,
        "stop_reason": stop_reason,
        "plateau_state": dict(accepted_program.get("plateau_state") or {}),
        "practical_ceiling": (accepted_program.get("plateau_state") or {}).get("practical_ceiling"),
        "goal_reached": bool(bundle_state["score"] >= target_score),
        "score_gap": max(0, int(target_score) - int(bundle_state["score"])),
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
        "routeable_output": rounds[-1].get("routeable_output", {}) if rounds else {},
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
