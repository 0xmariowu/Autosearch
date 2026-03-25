#!/usr/bin/env python3
"""Stable interface layer for reusing AutoSearch from other projects."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from engine import Engine, EngineConfig
from goal_benchmark import run_benchmark
from goal_bundle_loop import GOAL_RUNS_ROOT, load_goal_case, run_goal_bundle_loop
from goal_editor import GoalSearcher
from goal_judge import evaluate_goal_bundle
from goal_services import (
    available_platforms,
    normalize_query_spec,
    platforms_for_provider_mix,
    restrict_query_to_provider_mix,
    sample_findings,
    search_query,
)
from source_capability import load_source_capability_report, refresh_source_capability

__all__ = [
    "AutoSearchInterface",
    "SearcherJudgeSession",
    "default_interface",
]


class SearcherJudgeSession:
    """Explicit searcher/judge roles for external projects."""

    def __init__(self, goal_case: dict[str, Any]):
        self.goal_case = dict(goal_case)
        self.capability_report = refresh_source_capability(self.goal_case.get("providers"))
        self.platforms = available_platforms(self.goal_case, self.capability_report)
        self.searcher = GoalSearcher(self.goal_case)

    def _goal_axes(self) -> list[str]:
        dimension_ids = [str(dim.get("id") or "") for dim in self.goal_case.get("dimensions", []) if str(dim.get("id") or "")]
        if dimension_ids:
            return dimension_ids
        template_ids = [str(key) for key in dict(self.goal_case.get("dimension_queries") or {}).keys() if str(key)]
        if template_ids:
            return template_ids
        rubric_ids = [
            str(item.get("id") or f"criterion_{index}")
            for index, item in enumerate(self.goal_case.get("rubric", []), start=1)
        ]
        return [item for item in rubric_ids if item]

    def initial_queries(self) -> list[dict[str, Any]]:
        return [normalize_query_spec(query) for query in self.searcher.initial_queries()]

    def searcher_propose(
        self,
        *,
        bundle_state: dict[str, Any] | None = None,
        judge_result: dict[str, Any] | None = None,
        tried_queries: set[str] | None = None,
        active_program: dict[str, Any] | None = None,
        round_history: list[dict[str, Any]] | None = None,
        plan_count: int = 3,
        max_queries: int = 5,
    ) -> list[dict[str, Any]]:
        goal_axes = self._goal_axes()
        bundle_state = dict(bundle_state or {
            "accepted_findings": [],
            "score": 0,
            "dimension_scores": {},
            "missing_dimensions": goal_axes,
        })
        judge_result = dict(judge_result or {
            "score": 0,
            "dimension_scores": {},
            "missing_dimensions": list(bundle_state.get("missing_dimensions", []) or goal_axes),
            "matched_dimensions": [],
            "rationale": "empty bundle",
        })
        return self.searcher.candidate_plans(
            bundle_state=bundle_state,
            judge_result=judge_result,
            tried_queries=set(tried_queries or set()),
            available_providers=[platform["name"] for platform in self.platforms],
            active_program=dict(active_program or {}),
            round_history=list(round_history or []),
            plan_count=plan_count,
            max_queries=max_queries,
        ) or (
            [{"label": "seed", "queries": self.initial_queries()[:max_queries], "program_overrides": {}}]
            if not list(bundle_state.get("accepted_findings") or [])
            else []
        )

    def searcher_execute(
        self,
        queries: list[dict[str, Any]],
        *,
        sampling_policy: dict[str, Any] | None = None,
        provider_mix: list[str] | None = None,
    ) -> dict[str, Any]:
        effective_platforms = platforms_for_provider_mix(self.platforms, provider_mix)
        query_runs: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        for query in queries:
            effective_query = restrict_query_to_provider_mix(query, provider_mix)
            run = search_query(effective_query, effective_platforms, sampling_policy=sampling_policy)
            query_runs.append({
                "query": run["query"],
                "query_spec": run["query_spec"],
                "baseline_score": run["baseline_score"],
                "finding_count": len(run["findings"]),
                "sample_findings": sample_findings(run["findings"], limit=5),
            })
            findings.extend(run["findings"])
        return {
            "queries": [normalize_query_spec(query) for query in queries],
            "query_runs": query_runs,
            "findings": findings,
        }

    def judge_bundle(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        return evaluate_goal_bundle(self.goal_case, list(findings))

    def run_searcher_round(
        self,
        *,
        bundle_state: dict[str, Any] | None = None,
        judge_result: dict[str, Any] | None = None,
        tried_queries: set[str] | None = None,
        active_program: dict[str, Any] | None = None,
        round_history: list[dict[str, Any]] | None = None,
        plan_count: int = 3,
        max_queries: int = 5,
    ) -> dict[str, Any]:
        plans = self.searcher_propose(
            bundle_state=bundle_state,
            judge_result=judge_result,
            tried_queries=tried_queries,
            active_program=active_program,
            round_history=round_history,
            plan_count=plan_count,
            max_queries=max_queries,
        )
        plan_results: list[dict[str, Any]] = []
        for plan in plans:
            program_overrides = dict(plan.get("program_overrides") or {})
            execution = self.searcher_execute(
                list(plan.get("queries") or []),
                sampling_policy=dict(program_overrides.get("sampling_policy") or {}),
                provider_mix=list(program_overrides.get("provider_mix") or []),
            )
            judged = self.judge_bundle(execution["findings"])
            plan_results.append({
                "label": str(plan.get("label") or ""),
                "program_overrides": program_overrides,
                "queries": execution["queries"],
                "query_runs": execution["query_runs"],
                "finding_count": len(execution["findings"]),
                "judge_result": judged,
            })
        return {
            "goal_id": str(self.goal_case.get("id") or ""),
            "plans": plan_results,
            "capability_report": self.capability_report,
        }


class AutoSearchInterface:
    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent
        self.goal_cases_root = self.base_dir / "goal_cases"
        self.goal_runs_root = GOAL_RUNS_ROOT

    def list_goal_cases(self) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for path in sorted(self.goal_cases_root.glob("*.json")):
            payload = load_goal_case(path)
            items.append({
                "id": str(payload.get("id") or path.stem),
                "path": str(path),
                "project": str(payload.get("project") or ""),
                "problem": str(payload.get("problem") or ""),
            })
        return items

    def resolve_goal_case(self, goal_case: str | Path | dict[str, Any]) -> dict[str, Any]:
        if isinstance(goal_case, dict):
            return dict(goal_case)

        path = Path(goal_case)
        if path.exists():
            return load_goal_case(path)

        candidate = self.goal_cases_root / f"{goal_case}.json"
        if candidate.exists():
            return load_goal_case(candidate)

        for path in self.goal_cases_root.glob("*.json"):
            payload = load_goal_case(path)
            if str(payload.get("id") or "") == str(goal_case):
                return payload

        raise FileNotFoundError(f"Goal case not found: {goal_case}")

    def build_searcher_judge_session(self, goal_case: str | Path | dict[str, Any]) -> SearcherJudgeSession:
        return SearcherJudgeSession(self.resolve_goal_case(goal_case))

    def run_goal_case(
        self,
        goal_case: str | Path | dict[str, Any],
        *,
        max_rounds: int = 8,
        plan_count: int | None = None,
        max_queries: int | None = None,
        target_score: int | None = None,
        plateau_rounds: int | None = None,
        persist_run: bool = True,
    ) -> dict[str, Any]:
        payload = self.resolve_goal_case(goal_case)
        result = run_goal_bundle_loop(
            payload,
            max_rounds=max_rounds,
            plan_count_override=plan_count,
            max_queries_override=max_queries,
            target_score_override=target_score,
            plateau_rounds_override=plateau_rounds,
        )
        if persist_run:
            self.goal_runs_root.mkdir(parents=True, exist_ok=True)
            run_path = self.goal_runs_root / (
                f"{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-{payload.get('id', 'bundle-goal')}-bundle.json"
            )
            run_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = {**result, "run_path": str(run_path)}
        return result

    def run_goal_benchmark(
        self,
        goals: list[str | Path | dict[str, Any]],
        *,
        max_rounds: int = 1,
        plan_count: int = 1,
        max_queries: int = 1,
        target_score: int | None = None,
        plateau_rounds: int | None = None,
    ) -> dict[str, Any]:
        goal_paths: list[Path] = []
        for goal in goals:
            if isinstance(goal, dict):
                raise TypeError("run_goal_benchmark currently accepts goal ids or paths, not inline dict goal cases")
            path = Path(goal)
            if path.exists():
                goal_paths.append(path)
            else:
                resolved = self.resolve_goal_case(goal)
                goal_paths.append(Path(self.goal_cases_root / f"{resolved.get('id')}.json"))
        benchmark = run_benchmark(
            goal_paths,
            max_rounds=max_rounds,
            plan_count=plan_count,
            max_queries=max_queries,
            target_score=target_score,
            plateau_rounds=plateau_rounds,
        )
        return benchmark["payload"]

    def run_search_task(
        self,
        *,
        genes: dict[str, list[str]],
        platforms: list[dict[str, Any]],
        target_spec: str,
        task_name: str = "autosearch",
        output_path: str = "/tmp/autosearch-findings.jsonl",
        max_rounds: int = 15,
        llm_model: str = "claude-haiku-4-5-20251001",
    ) -> dict[str, Any]:
        config = EngineConfig(
            genes=genes,
            platforms=platforms,
            target_spec=target_spec,
            task_name=task_name,
            output_path=output_path,
            max_rounds=max_rounds,
            llm_model=llm_model,
            capability_report=load_source_capability_report(),
        )
        return Engine(config, self.base_dir).run()

    def doctor(self, providers: list[str] | None = None) -> dict[str, Any]:
        return refresh_source_capability(providers)


def default_interface() -> AutoSearchInterface:
    return AutoSearchInterface()
