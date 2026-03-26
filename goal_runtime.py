"""Project-agnostic runtime state for autoresearch-style goal loops."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from research.mode_policy import apply_mode_policy


REPO_ROOT = Path(__file__).resolve().parent
GOAL_CASES_ROOT = REPO_ROOT / "goal_cases"
GOAL_RUNTIME_ROOT = GOAL_CASES_ROOT / "runtime"

DEFAULT_HARNESS = {
    "version": 1,
    "bundle_policy": {
        "per_query_cap": 5,
        "per_source_cap": 18,
        "per_domain_cap": 18,
    },
    "anti_cheat": {
        "min_new_unique_urls": 1,
        "min_novelty_ratio": 0.01,
        "min_source_diversity": 0.15,
        "max_source_concentration": 0.82,
        "max_query_concentration": 0.70,
        "min_new_sources_when_score_improves": 0,
    },
}


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default or {})
    return payload if isinstance(payload, dict) else dict(default or {})


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def runtime_paths(goal_id: str) -> dict[str, Path]:
    runtime_root = GOAL_RUNTIME_ROOT / goal_id
    return {
        "runtime_root": runtime_root,
        "accepted_program": runtime_root / "accepted-program.json",
        "harness": runtime_root / "evaluation-harness.json",
        "evidence_index": runtime_root / "evidence-index.jsonl",
        "program_archive": runtime_root / "program-archive",
        "latest_population": runtime_root / "latest-population.json",
        "population_history": runtime_root / "population-history",
        "latest_lineage": runtime_root / "latest-lineage.json",
        "lineage_history": runtime_root / "lineage-history",
    }


def ensure_harness(goal_case: dict[str, Any]) -> dict[str, Any]:
    goal_id = str(goal_case.get("id") or "goal")
    paths = runtime_paths(goal_id)
    payload = _read_json(paths["harness"])
    if not payload:
        payload = {
            "goal_id": goal_id,
            "created_at": datetime.now().astimezone().isoformat(),
            **DEFAULT_HARNESS,
        }
        _write_json(paths["harness"], payload)
    return payload


def _normalize_query_spec(query: Any) -> dict[str, Any]:
    if isinstance(query, dict):
        return {
            "text": str(query.get("text") or "").strip(),
            "platforms": list(query.get("platforms") or []),
        }
    return {"text": str(query or "").strip(), "platforms": []}


def _default_search_backends(available_providers: list[str]) -> list[str]:
    preferred = ["searxng", "ddgs", "exa", "tavily"]
    selected = [provider for provider in preferred if provider in available_providers]
    return selected or list(available_providers)


def _default_backend_roles(available_providers: list[str]) -> dict[str, list[str]]:
    roles = {
        "breadth": _default_search_backends(available_providers),
        "repos": [provider for provider in ["github_repos"] if provider in available_providers],
        "discussion": [provider for provider in ["github_issues"] if provider in available_providers],
        "code": [provider for provider in ["github_code"] if provider in available_providers],
        "datasets": [provider for provider in ["huggingface_datasets"] if provider in available_providers],
        "social": [provider for provider in ["twitter_xreach"] if provider in available_providers],
    }
    return roles


def _mutation_kind(label: str) -> str:
    lowered = str(label or "").strip().lower()
    if "anchored" in lowered:
        return "anchor_followup"
    if "frontier" in lowered or "orthogonal" in lowered:
        return "frontier_probe"
    if "repair" in lowered or "heuristic" in lowered:
        return "dimension_repair"
    if "seed" in lowered or "primary" in lowered:
        return "broad_recall"
    return "mutation"


def _normalize_topic_frontier(frontier: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in list(frontier or []):
        if isinstance(item, dict):
            topic_id = str(item.get("id") or item.get("topic_id") or item.get("label") or "").strip()
            topic = dict(item)
            if topic_id:
                topic["id"] = topic_id
            normalized.append(topic)
            continue
        topic_id = str(item or "").strip()
        if topic_id:
            normalized.append({"id": topic_id, "queries": []})
    return normalized


def default_program(goal_case: dict[str, Any], available_providers: list[str]) -> dict[str, Any]:
    # Default programs always pass through mode policy resolution so mode behavior
    # is applied before any loop or selector logic reads the program.
    queries = [
        _normalize_query_spec(query)
        for query in list(goal_case.get("seed_queries") or [])
        if _normalize_query_spec(query)["text"]
    ]
    query_templates = {
        str(key): list(value or [])
        for key, value in dict(goal_case.get("dimension_queries") or {}).items()
    }
    dimension_strategies = {
        dimension_id: {
            "queries": [
                _normalize_query_spec(query)
                for query in list(template_queries or [])
                if _normalize_query_spec(query)["text"]
            ],
            "preferred_providers": sorted({
                str((platform or {}).get("name") or "").strip()
                for query in list(template_queries or [])
                for platform in list((_normalize_query_spec(query).get("platforms") or []))
                if str((platform or {}).get("name") or "").strip() in available_providers
            }),
        }
        for dimension_id, template_queries in query_templates.items()
    }
    program = {
        "program_id": "seed-program",
        "goal_id": str(goal_case.get("id") or ""),
        "parent_program_id": None,
        "label": "seed-program",
        "branch_id": "seed",
        "family_id": "seed-family",
        "branch_depth": 0,
        "mutation_kind": "seed",
        "created_at": datetime.now().astimezone().isoformat(),
        "queries": queries,
        "provider_mix": list(available_providers),
        "topic_frontier": _normalize_topic_frontier(goal_case.get("topic_frontier") or []),
        "query_templates": query_templates,
        "dimension_strategies": dimension_strategies,
        "mode": str(goal_case.get("mode") or "balanced"),
        "mode_policy_overrides": dict(goal_case.get("mode_policy_overrides") or {}),
        "round_roles": list(goal_case.get("round_roles") or ["broad_recall", "dimension_repair", "orthogonal_probe"]),
        "current_role": "broad_recall",
        "search_backends": list(goal_case.get("search_backends") or _default_search_backends(available_providers)),
        "backend_roles": dict(goal_case.get("backend_roles") or _default_backend_roles(available_providers)),
        "acquisition_policy": dict(goal_case.get("acquisition_policy") or {
            "acquire_pages": False,
            "page_fetch_limit": 2,
            "use_render_fallback": False,
        }),
        "evidence_policy": dict(goal_case.get("evidence_policy") or {
            "preferred_content_types": [],
            "prefer_acquired_text": False,
        }),
        "repair_policy": dict(goal_case.get("repair_policy") or {
            "target_weak_dimensions": 2,
            "anchor_followups": True,
            "prefer_backend_rotation": True,
        }),
        "population_policy": dict(goal_case.get("population_policy") or {
            "plan_count": 3,
            "max_queries": 5,
            "max_branch_depth": 4,
            "recursive_depth_limit": 4,
            "stale_branch_rounds": 3,
            "prefer_diverse_branches": True,
            "retire_family_after_rejections": 3,
            "branch_budget_per_round": {
                "breadth": 1,
                "repair": 2,
                "followup": 2,
                "probe": 1,
                "research": 1,
            },
        }),
        "explore_budget": float(goal_case.get("explore_budget", 0.4) or 0.4),
        "exploit_budget": float(goal_case.get("exploit_budget", 0.6) or 0.6),
        "sampling_policy": dict(goal_case.get("sampling_policy") or {
            "bundle_per_query_cap": 5,
            "rank_by_relevance": True,
            "anchor_followups": True,
        }),
        "budget_policy": dict(goal_case.get("budget_policy") or {
            "explore_budget_pct": 0.85,
            "answer_budget_pct": 0.15,
            "provider_timeout_seconds": 10,
            "parallel_provider_limit": 6,
        }),
        "stop_rules": {
            "plateau_rounds": int(goal_case.get("plateau_rounds", 3) or 3),
            "target_score": int(goal_case.get("target_score", 100) or 100),
        },
        "plateau_state": {
            "stagnant_rounds": 0,
            "best_score": 0,
            "practical_ceiling": None,
            "dimension_stagnation": {},
        },
        "plan_count": 3,
        "max_queries": 5,
        "mutation_history": [],
        "evolution_stats": {
            "accepted_rounds": 0,
            "rejected_rounds": 0,
            "family_best_scores": {"seed-family": 0},
            "mutation_acceptance": {},
            "mutation_rejection_streaks": {},
            "family_rejection_streaks": {},
            "retired_families": [],
            "retired_mutation_kinds": [],
            "last_population_summary": {},
        },
        "score": 0,
        "dimension_scores": {},
    }
    return apply_mode_policy(program)


def load_accepted_program(goal_case: dict[str, Any], available_providers: list[str]) -> dict[str, Any]:
    goal_id = str(goal_case.get("id") or "goal")
    paths = runtime_paths(goal_id)
    payload = _read_json(paths["accepted_program"])
    if payload:
        goal_mode = str(goal_case.get("mode") or "").strip()
        if goal_mode:
            payload["mode"] = goal_mode
        elif "mode" not in payload:
            payload["mode"] = "balanced"
        goal_mode_overrides = dict(goal_case.get("mode_policy_overrides") or {})
        if goal_mode_overrides:
            payload["mode_policy_overrides"] = goal_mode_overrides
        else:
            payload.setdefault("mode_policy_overrides", {})
        payload["topic_frontier"] = _normalize_topic_frontier(payload.get("topic_frontier") or [])
        return apply_mode_policy(payload)
    return default_program(goal_case, available_providers)


def save_accepted_program(goal_id: str, program: dict[str, Any]) -> Path:
    paths = runtime_paths(goal_id)
    payload = dict(program)
    payload["topic_frontier"] = _normalize_topic_frontier(payload.get("topic_frontier") or [])
    _write_json(paths["accepted_program"], payload)
    return paths["accepted_program"]


def build_candidate_program(
    *,
    goal_id: str,
    parent_program: dict[str, Any],
    label: str,
    queries: list[dict[str, Any]],
    provider_mix: list[str],
    round_index: int,
    candidate_index: int,
    program_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = datetime.now().astimezone().isoformat()
    run_token = datetime.now().strftime("%H%M%S%f")
    max_branch_depth = int(((parent_program.get("population_policy") or {}).get("max_branch_depth", 0)) or 0)
    next_branch_depth = int(parent_program.get("branch_depth", 0) or 0) + 1
    if max_branch_depth > 0:
        next_branch_depth = min(next_branch_depth, max_branch_depth)
    candidate = {
        "program_id": f"{goal_id}-r{round_index}-c{candidate_index}-{run_token}",
        "goal_id": goal_id,
        "parent_program_id": parent_program.get("program_id"),
        "label": label,
        "branch_id": str(parent_program.get("branch_id") or _mutation_kind(label)),
        "family_id": str(parent_program.get("family_id") or f"{_mutation_kind(label)}-family"),
        "branch_root_program_id": str(parent_program.get("branch_root_program_id") or parent_program.get("program_id") or "seed-program"),
        "branch_depth": next_branch_depth,
        "repair_depth": int(parent_program.get("repair_depth", 0) or 0) + (1 if _mutation_kind(label) == "dimension_repair" else 0),
        "mutation_kind": _mutation_kind(label),
        "created_at": created_at,
        "queries": list(queries),
        "provider_mix": list(provider_mix),
        "topic_frontier": _normalize_topic_frontier(parent_program.get("topic_frontier") or []),
        "query_templates": dict(parent_program.get("query_templates") or {}),
        "dimension_strategies": dict(parent_program.get("dimension_strategies") or {}),
        "mode": str(parent_program.get("mode") or "balanced"),
        "mode_policy_overrides": dict(parent_program.get("mode_policy_overrides") or {}),
        "round_roles": list(parent_program.get("round_roles") or ["broad_recall", "dimension_repair", "orthogonal_probe"]),
        "current_role": str(parent_program.get("current_role") or "dimension_repair"),
        "search_backends": list(parent_program.get("search_backends") or []),
        "backend_roles": dict(parent_program.get("backend_roles") or {}),
        "acquisition_policy": dict(parent_program.get("acquisition_policy") or {}),
        "evidence_policy": dict(parent_program.get("evidence_policy") or {}),
        "repair_policy": dict(parent_program.get("repair_policy") or {}),
        "population_policy": dict(parent_program.get("population_policy") or {}),
        "explore_budget": float(parent_program.get("explore_budget", 0.4) or 0.4),
        "exploit_budget": float(parent_program.get("exploit_budget", 0.6) or 0.6),
        "sampling_policy": dict(parent_program.get("sampling_policy") or {}),
        "stop_rules": dict(parent_program.get("stop_rules") or {}),
        "plateau_state": dict(parent_program.get("plateau_state") or {}),
        "plan_count": int(parent_program.get("plan_count", 3) or 3),
        "max_queries": int(parent_program.get("max_queries", 5) or 5),
        "mutation_history": list(parent_program.get("mutation_history") or []) + [label],
        "evolution_stats": dict(parent_program.get("evolution_stats") or {}),
        "score": int(parent_program.get("score", 0) or 0),
        "dimension_scores": dict(parent_program.get("dimension_scores") or {}),
    }
    for key, value in dict(program_overrides or {}).items():
        if key == "topic_frontier" and isinstance(value, list):
            candidate[key] = _normalize_topic_frontier(value)
        elif key in {"search_backends"} and isinstance(value, list):
            candidate[key] = list(value)
        elif key in {
            "query_templates",
            "sampling_policy",
            "dimension_strategies",
            "stop_rules",
            "plateau_state",
            "backend_roles",
            "acquisition_policy",
            "evidence_policy",
            "repair_policy",
            "population_policy",
        } and isinstance(value, dict):
            candidate[key] = dict(value)
        elif key in {"round_roles"} and isinstance(value, list):
            candidate[key] = list(value)
        else:
            candidate[key] = value
    return apply_mode_policy(candidate)

def archive_candidate_program(
    goal_id: str,
    candidate_program: dict[str, Any],
    *,
    result: dict[str, Any],
) -> Path:
    paths = runtime_paths(goal_id)
    archive_dir = paths["program_archive"]
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{candidate_program['program_id']}.json"
    payload = {
        "candidate_program": candidate_program,
        "result": result,
    }
    _write_json(archive_path, payload)
    return archive_path


def _population_lineage_summary(population: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "population_size": len(population),
        "program_ids": [str(item.get("program_id") or "") for item in population],
        "parent_program_ids": sorted({
            str(item.get("parent_program_id") or "")
            for item in population
            if str(item.get("parent_program_id") or "")
        }),
        "branch_ids": sorted({
            str(item.get("branch_id") or "")
            for item in population
            if str(item.get("branch_id") or "")
        }),
        "branch_root_program_ids": sorted({
            str(item.get("branch_root_program_id") or "")
            for item in population
            if str(item.get("branch_root_program_id") or "")
        }),
        "family_ids": sorted({
            str(item.get("family_id") or "")
            for item in population
            if str(item.get("family_id") or "")
        }),
        "accepted_candidates": [
            str(item.get("program_id") or "")
            for item in population
            if bool((item.get("selection") or {}).get("accepted"))
        ],
        "top_score": max((int(item.get("score", 0) or 0) for item in population), default=0),
        "labels": [str(item.get("label") or "") for item in population],
        "mutation_fields": sorted({
            field
            for item in population
            for field in list((item.get("selection") or {}).get("program_change_fields") or [])
        }),
        "mutation_kinds": sorted({
            str(item.get("mutation_kind") or "")
            for item in population
            if str(item.get("mutation_kind") or "")
        }),
        "branch_counts": {
            branch_id: sum(1 for item in population if str(item.get("branch_id") or "") == branch_id)
            for branch_id in sorted({
                str(item.get("branch_id") or "")
                for item in population
                if str(item.get("branch_id") or "")
            })
        },
        "branch_best_scores": {
            branch_id: max(
                int(item.get("score", 0) or 0)
                for item in population
                if str(item.get("branch_id") or "") == branch_id
            )
            for branch_id in sorted({
                str(item.get("branch_id") or "")
                for item in population
                if str(item.get("branch_id") or "")
            })
        },
        "family_counts": {
            family_id: sum(1 for item in population if str(item.get("family_id") or "") == family_id)
            for family_id in sorted({
                str(item.get("family_id") or "")
                for item in population
                if str(item.get("family_id") or "")
            })
        },
        "family_best_scores": {
            family_id: max(
                int(item.get("score", 0) or 0)
                for item in population
                if str(item.get("family_id") or "") == family_id
            )
            for family_id in sorted({
                str(item.get("family_id") or "")
                for item in population
                if str(item.get("family_id") or "")
            })
        },
        "mutation_kind_counts": {
            kind: sum(1 for item in population if str(item.get("mutation_kind") or "") == kind)
            for kind in sorted({
                str(item.get("mutation_kind") or "")
                for item in population
                if str(item.get("mutation_kind") or "")
            })
        },
        "planning_op_counts": {
            op_name: sum(
                1
                for item in population
                for op in list(item.get("planning_ops") or [])
                if str((op or {}).get("op") or "") == op_name
            )
            for op_name in sorted({
                str((op or {}).get("op") or "")
                for item in population
                for op in list(item.get("planning_ops") or [])
                if str((op or {}).get("op") or "")
            })
        },
        "planning_op_history": [
            {
                "program_id": str(item.get("program_id") or ""),
                "label": str(item.get("label") or ""),
                "branch_id": str(item.get("branch_id") or ""),
                "family_id": str(item.get("family_id") or ""),
                "ops": [
                    {
                        "op": str((op or {}).get("op") or ""),
                        "target": str((op or {}).get("target") or ""),
                        "mode": str((op or {}).get("mode") or ""),
                    }
                    for op in list(item.get("planning_ops") or [])
                    if str((op or {}).get("op") or "")
                ],
            }
            for item in population
            if list(item.get("planning_ops") or [])
        ],
        "deepest_branch_depth": max((int(item.get("branch_depth", 0) or 0) for item in population), default=0),
        "max_repair_depth": max((int(item.get("repair_depth", 0) or 0) for item in population), default=0),
    }
    return summary


def save_population_snapshot(goal_id: str, round_index: int, population: list[dict[str, Any]]) -> dict[str, Path]:
    paths = runtime_paths(goal_id)
    payload = {
        "goal_id": goal_id,
        "round": int(round_index),
        "generated_at": datetime.now().astimezone().isoformat(),
        "population": list(population),
    }
    lineage_payload = {
        "goal_id": goal_id,
        "round": int(round_index),
        "generated_at": payload["generated_at"],
        "summary": _population_lineage_summary(population),
    }
    latest_path = paths["latest_population"]
    history_dir = paths["population_history"]
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"round-{int(round_index):03d}.json"
    latest_lineage = paths["latest_lineage"]
    lineage_history_dir = paths["lineage_history"]
    lineage_history_dir.mkdir(parents=True, exist_ok=True)
    lineage_history_path = lineage_history_dir / f"round-{int(round_index):03d}.json"
    _write_json(latest_path, payload)
    _write_json(history_path, payload)
    _write_json(latest_lineage, lineage_payload)
    _write_json(lineage_history_path, lineage_payload)
    return {
        "latest": latest_path,
        "history": history_path,
        "latest_lineage": latest_lineage,
        "lineage_history": lineage_history_path,
    }
