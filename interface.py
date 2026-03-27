#!/usr/bin/env python3
"""Stable interface layer for reusing AutoSearch from other projects."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from acquisition import (
    build_markdown_views as _build_markdown_views,
    chunk_document as _chunk_document,
    enrich_evidence_record as _enrich_evidence_record,
    fetch_document as _fetch_document,
)
from api_contract import (
    api_info_payload,
    api_method_payload,
    with_api_meta,
    serialize_acquired_document,
)
from engine import Engine, EngineConfig
from evidence import (
    coerce_evidence_record as _coerce_evidence_record,
    coerce_evidence_records as _coerce_evidence_records,
    normalize_acquired_document as _normalize_acquired_document,
    normalize_evidence_record as _normalize_evidence_record,
    normalize_result_record as _normalize_result_record,
)
from goal_benchmark import run_benchmark
from goal_bundle_loop import GOAL_RUNS_ROOT, load_goal_case, run_goal_bundle_loop
from goal_editor import GoalSearcher
from goal_judge import evaluate_goal_bundle
from goal_services import (
    available_platforms,
    normalize_query_spec,
    query_key,
    platforms_for_provider_mix,
    replay_queries,
    restrict_query_to_provider_mix,
    sample_findings,
    search_query,
)
from research import (
    build_research_packet,
    build_research_plan,
    build_routeable_output,
    execute_research_plan,
    synthesize_research_round,
)
from source_capability import load_source_capability_report, refresh_source_capability
from watch.runtime import run_watch as _run_watch, run_watches as _run_watches

__all__ = [
    "AutoSearchInterface",
    "SearcherJudgeSession",
    "default_interface",
]


class SearcherJudgeSession:
    """Explicit searcher/judge roles for external projects.

    This session exposes a stable split between query proposal/execution and
    bundle evaluation without requiring callers to wire internal goal-loop
    modules directly.
    """

    def __init__(self, goal_case: dict[str, Any]):
        self.goal_case = dict(goal_case)
        self.capability_report = refresh_source_capability(
            self.goal_case.get("providers")
        )
        self.platforms = available_platforms(self.goal_case, self.capability_report)
        self.searcher = GoalSearcher(self.goal_case)

    def _goal_axes(self) -> list[str]:
        dimension_ids = [
            str(dim.get("id") or "")
            for dim in self.goal_case.get("dimensions", [])
            if str(dim.get("id") or "")
        ]
        if dimension_ids:
            return dimension_ids
        template_ids = [
            str(key)
            for key in dict(self.goal_case.get("dimension_queries") or {}).keys()
            if str(key)
        ]
        if template_ids:
            return template_ids
        rubric_ids = [
            str(item.get("id") or f"criterion_{index}")
            for index, item in enumerate(self.goal_case.get("rubric", []), start=1)
        ]
        return [item for item in rubric_ids if item]

    def initial_queries(self) -> list[dict[str, Any]]:
        """Return normalized seed queries for the goal case."""
        return [
            normalize_query_spec(query) for query in self.searcher.initial_queries()
        ]

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
        """Return candidate search plans from the searcher role."""
        goal_axes = self._goal_axes()
        bundle_state = dict(
            bundle_state
            or {
                "accepted_findings": [],
                "score": 0,
                "dimension_scores": {},
                "missing_dimensions": goal_axes,
            }
        )
        judge_result = dict(
            judge_result
            or {
                "score": 0,
                "dimension_scores": {},
                "missing_dimensions": list(
                    bundle_state.get("missing_dimensions", []) or goal_axes
                ),
                "matched_dimensions": [],
                "rationale": "empty bundle",
            }
        )
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
            [
                {
                    "label": "seed",
                    "queries": self.initial_queries()[:max_queries],
                    "program_overrides": {},
                }
            ]
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
        """Execute queries and return sampled run summaries plus raw findings."""
        effective_platforms = platforms_for_provider_mix(self.platforms, provider_mix)
        query_runs: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        for query in queries:
            effective_query = restrict_query_to_provider_mix(query, provider_mix)
            run = search_query(
                effective_query, effective_platforms, sampling_policy=sampling_policy
            )
            query_runs.append(
                {
                    "query": run["query"],
                    "query_spec": run["query_spec"],
                    "baseline_score": run["baseline_score"],
                    "finding_count": len(run["findings"]),
                    "sample_findings": sample_findings(run["findings"], limit=5),
                }
            )
            findings.extend(run["findings"])
        return {
            "queries": [normalize_query_spec(query) for query in queries],
            "query_runs": query_runs,
            "findings": findings,
        }

    def judge_bundle(self, findings: list[dict[str, Any]]) -> dict[str, Any]:
        """Score a bundle of findings against the goal rubric/dimensions."""
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
        """Run one propose/execute/judge cycle and return per-plan summaries."""
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
            plan_results.append(
                {
                    "label": str(plan.get("label") or ""),
                    "program_overrides": program_overrides,
                    "queries": execution["queries"],
                    "query_runs": execution["query_runs"],
                    "finding_count": len(execution["findings"]),
                    "judge_result": judged,
                }
            )
        return {
            "goal_id": str(self.goal_case.get("id") or ""),
            "plans": plan_results,
            "capability_report": self.capability_report,
        }


class AutoSearchInterface:
    """Stable public facade for AutoSearch.

    Compatibility is measured against this class and SearcherJudgeSession,
    not against internal goal-loop helpers.
    """

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent
        self.goal_cases_root = self.base_dir / "goal_cases"
        self.goal_runs_root = GOAL_RUNS_ROOT

    def _api_payload(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return with_api_meta(payload, method)

    def _goal_platform_list(
        self, goal_case: str | Path | dict[str, Any]
    ) -> list[dict[str, Any]]:
        payload = self.resolve_goal_case(goal_case)
        capability_report = refresh_source_capability(payload.get("providers"))
        return available_platforms(payload, capability_report)

    def api_info(self) -> dict[str, Any]:
        """Describe the public API product and method catalog."""
        return api_info_payload()

    def api_method(self, method: str) -> dict[str, Any]:
        """Describe one public API method contract."""
        return api_method_payload(method)

    def list_goal_cases(self) -> list[dict[str, str]]:
        """List goal cases discoverable from goal_cases_root."""
        items: list[dict[str, str]] = []
        for path in sorted(self.goal_cases_root.glob("*.json")):
            payload = load_goal_case(path)
            items.append(
                {
                    "id": str(payload.get("id") or path.stem),
                    "path": str(path),
                    "project": str(payload.get("project") or ""),
                    "problem": str(payload.get("problem") or ""),
                }
            )
        return items

    def resolve_goal_case(
        self, goal_case: str | Path | dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve a goal id, path, or inline payload into a goal-case dict."""
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

    def build_searcher_judge_session(
        self, goal_case: str | Path | dict[str, Any]
    ) -> SearcherJudgeSession:
        """Build a stable searcher/judge session for a single goal case."""
        return SearcherJudgeSession(self.resolve_goal_case(goal_case))

    def goal_capability_report(
        self, goal_case: str | Path | dict[str, Any]
    ) -> dict[str, Any]:
        """Return the refreshed capability report for one goal case."""
        payload = self.resolve_goal_case(goal_case)
        return self._api_payload(
            "goal_capability_report",
            {"capability_report": refresh_source_capability(payload.get("providers"))},
        )

    def goal_platforms(self, goal_case: str | Path | dict[str, Any]) -> dict[str, Any]:
        """Return the effective platform configs for one goal case."""
        return self._api_payload(
            "goal_platforms",
            {"platforms": self._goal_platform_list(goal_case)},
        )

    def normalize_query(self, query: Any) -> dict[str, Any]:
        """Normalize a query into the stable query-spec shape."""
        return self._api_payload(
            "normalize_query",
            {"query_spec": normalize_query_spec(query)},
        )

    def search_goal_query(
        self,
        goal_case: str | Path | dict[str, Any],
        query: Any,
        *,
        sampling_policy: dict[str, Any] | None = None,
        provider_mix: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute one query against the goal-scoped platform set."""
        platforms = self._goal_platform_list(goal_case)
        effective_platforms = platforms_for_provider_mix(platforms, provider_mix)
        effective_query = restrict_query_to_provider_mix(query, provider_mix)
        return self._api_payload(
            "search_goal_query",
            search_query(
                effective_query,
                effective_platforms,
                sampling_policy=sampling_policy,
            ),
        )

    def replay_goal_queries(
        self,
        goal_case: str | Path | dict[str, Any],
        queries: list[dict[str, Any]],
        *,
        sampling_policy: dict[str, Any] | None = None,
        provider_mix: list[str] | None = None,
    ) -> dict[str, Any]:
        """Replay multiple goal-scoped queries and return runs plus findings."""
        platforms = self._goal_platform_list(goal_case)
        effective_platforms = platforms_for_provider_mix(platforms, provider_mix)
        effective_queries = [
            restrict_query_to_provider_mix(query, provider_mix)
            for query in list(queries or [])
        ]
        query_runs, findings = replay_queries(
            effective_queries,
            effective_platforms,
            sampling_policy=sampling_policy,
        )
        return self._api_payload(
            "replay_goal_queries",
            {
                "queries": [normalize_query_spec(query) for query in effective_queries],
                "query_runs": query_runs,
                "findings": findings,
            },
        )

    def fetch_document(
        self,
        url: str,
        *,
        query: str = "",
        timeout: int = 10,
        use_render_fallback: bool = False,
        use_crawl4ai: bool = False,
    ) -> dict[str, Any]:
        """Fetch one document through the acquisition pipeline."""
        document = _fetch_document(
            url,
            query=query,
            timeout=timeout,
            use_render_fallback=use_render_fallback,
            use_crawl4ai=use_crawl4ai,
        )
        return self._api_payload(
            "fetch_document",
            {"document": serialize_acquired_document(document)},
        )

    def enrich_record(
        self,
        record: dict[str, Any],
        *,
        timeout: int = 10,
        use_render_fallback: bool = False,
        use_crawl4ai_adapter: bool = False,
        query: str = "",
    ) -> dict[str, Any]:
        """Enrich one evidence-like record through acquisition."""
        return self._api_payload(
            "enrich_record",
            _enrich_evidence_record(
                record,
                timeout=timeout,
                use_render_fallback=use_render_fallback,
                use_crawl4ai_adapter=use_crawl4ai_adapter,
                query=query,
            ),
        )

    def build_markdown_views(
        self, text: str, *, query: str = "", max_chars: int = 2400
    ) -> dict[str, Any]:
        """Build clean/fit markdown plus ranked chunk metadata."""
        return self._api_payload(
            "build_markdown_views",
            _build_markdown_views(text, query=query, max_chars=max_chars),
        )

    def chunk_document(
        self, text: str, *, query: str = "", limit: int = 4
    ) -> dict[str, Any]:
        """Return ranked chunks for a document-like text blob."""
        return self._api_payload(
            "chunk_document",
            {"chunks": _chunk_document(text, query=query, limit=limit)},
        )

    def normalize_result_record(self, result: Any, query: str) -> dict[str, Any]:
        """Normalize a raw search result into an evidence record."""
        return self._api_payload(
            "normalize_result_record",
            {"record": _normalize_result_record(result, query)},
        )

    def normalize_acquired_document(
        self,
        document: Any,
        *,
        source: str,
        query: str,
    ) -> dict[str, Any]:
        """Normalize an acquired document into an evidence record."""
        return self._api_payload(
            "normalize_acquired_document",
            {
                "record": _normalize_acquired_document(
                    document, source=source, query=query
                )
            },
        )

    def normalize_evidence_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Normalize a dict-shaped evidence record."""
        return self._api_payload(
            "normalize_evidence_record",
            {"record": _normalize_evidence_record(record)},
        )

    def coerce_evidence_record(self, item: Any) -> dict[str, Any]:
        """Coerce a mixed-shape item into a stable evidence record."""
        return self._api_payload(
            "coerce_evidence_record",
            {"record": _coerce_evidence_record(item)},
        )

    def coerce_evidence_records(self, items: list[Any] | None) -> dict[str, Any]:
        """Coerce a list of mixed-shape items into evidence records."""
        return self._api_payload(
            "coerce_evidence_records",
            {"records": _coerce_evidence_records(items)},
        )

    def build_research_plan(
        self,
        goal_case: str | Path | dict[str, Any],
        *,
        bundle_state: dict[str, Any] | None = None,
        judge_result: dict[str, Any] | None = None,
        tried_queries: set[str] | None = None,
        active_program: dict[str, Any] | None = None,
        round_history: list[dict[str, Any]] | None = None,
        plan_count: int = 3,
        max_queries: int = 5,
        local_evidence_records: list[dict[str, Any]] | None = None,
        gap_queue: list[dict[str, Any]] | None = None,
        diary_summary: list[str] | None = None,
        action_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build one round of research plans for a goal case."""
        session = self.build_searcher_judge_session(goal_case)
        plans = build_research_plan(
            searcher=session.searcher,
            bundle_state=dict(bundle_state or {"accepted_findings": []}),
            judge_result=dict(judge_result or {}),
            tried_queries=set(tried_queries or set()),
            available_providers=[platform["name"] for platform in session.platforms],
            active_program=dict(active_program or {}),
            round_history=list(round_history or []),
            plan_count=plan_count,
            max_queries=max_queries,
            local_evidence_records=list(local_evidence_records or []),
            gap_queue=list(gap_queue or []),
            diary_summary=list(diary_summary or []),
            action_policy=dict(action_policy or {}),
        )
        return self._api_payload("build_research_plan", {"plans": plans})

    def execute_research_plan(
        self,
        goal_case: str | Path | dict[str, Any],
        plan: dict[str, Any],
        *,
        provider_mix: list[str] | None = None,
        sampling_policy: dict[str, Any] | None = None,
        local_evidence_records: list[dict[str, Any]] | None = None,
        backend_roles: dict[str, Any] | None = None,
        tried_queries: set[str] | None = None,
    ) -> dict[str, Any]:
        """Execute one research plan against the goal-scoped platform set."""
        platforms = self._goal_platform_list(goal_case)
        result = execute_research_plan(
            dict(plan or {}),
            default_platforms=platforms,
            provider_mix=provider_mix,
            query_key_fn=query_key,
            sampling_policy=sampling_policy,
            local_evidence_records=list(local_evidence_records or []),
            backend_roles=dict(backend_roles or {}),
            tried_queries=set(tried_queries or set()),
        )
        return self._api_payload("execute_research_plan", result)

    def synthesize_research_round(
        self,
        goal_case: str | Path | dict[str, Any],
        *,
        existing_findings: list[dict[str, Any]],
        round_findings: list[dict[str, Any]],
        harness: dict[str, Any],
        graph_plan: dict[str, Any] | None = None,
        gap_queue: list[dict[str, Any]] | None = None,
        planning_ops: list[dict[str, Any]] | None = None,
        effective_target_score: int | None = None,
    ) -> dict[str, Any]:
        """Synthesize one research round into bundle, graph, and routeable outputs."""
        payload = self.resolve_goal_case(goal_case)
        result = synthesize_research_round(
            payload,
            existing_findings=list(existing_findings or []),
            round_findings=list(round_findings or []),
            harness=dict(harness or {}),
            graph_plan=dict(graph_plan or {}),
            gap_queue=list(gap_queue or []),
            planning_ops=list(planning_ops or []),
            effective_target_score=effective_target_score,
        )
        return self._api_payload("synthesize_research_round", result)

    def build_routeable_output(
        self,
        goal_case: str | Path | dict[str, Any],
        *,
        bundle: list[dict[str, Any]],
        judge_result: dict[str, Any],
        effective_target_score: int | None = None,
        repair_hints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build the routeable handoff artifact from a bundle and judge result."""
        payload = self.resolve_goal_case(goal_case)
        result = build_routeable_output(
            payload,
            bundle=list(bundle or []),
            judge_result=dict(judge_result or {}),
            effective_target_score=effective_target_score,
            repair_hints=dict(repair_hints or {}),
        )
        return self._api_payload("build_routeable_output", result)

    def build_research_packet(
        self,
        goal_case: str | Path | dict[str, Any],
        *,
        bundle: list[dict[str, Any]],
        judge_result: dict[str, Any],
        cross_verification: dict[str, Any] | None = None,
        next_actions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build the standalone routeable research packet."""
        payload = self.resolve_goal_case(goal_case)
        result = build_research_packet(
            goal_case=payload,
            bundle=list(bundle or []),
            judge_result=dict(judge_result or {}),
            cross_verification=dict(cross_verification or {}),
            next_actions=list(next_actions or []),
        ).to_dict()
        return self._api_payload("build_research_packet", result)

    def run_goal_case(
        self,
        goal_case: str | Path | dict[str, Any],
        *,
        mode: str | None = None,
        max_rounds: int = 8,
        plan_count: int | None = None,
        max_queries: int | None = None,
        target_score: int | None = None,
        plateau_rounds: int | None = None,
        persist_run: bool = True,
    ) -> dict[str, Any]:
        """Run the full goal loop and return the stable result payload.

        The returned payload mirrors the goal-loop artifact and also promotes
        `routeable_output.research_packet` to a top-level `research_packet`
        convenience field when present.
        """
        payload = self.resolve_goal_case(goal_case)
        if mode:
            payload["mode"] = str(mode).strip()
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
            run_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = {**result, "run_path": str(run_path)}
        routeable_output = dict(result.get("routeable_output") or {})
        if routeable_output.get("research_packet"):
            result = {
                **result,
                "research_packet": dict(routeable_output.get("research_packet") or {}),
            }
        return self._api_payload("run_goal_case", result)

    def optimize_goal(
        self,
        goal_case: str | Path | dict[str, Any],
        *,
        mode: str | None = None,
        target_score: int = 100,
        max_rounds: int = 8,
        plateau_rounds: int = 3,
        plan_count: int | None = None,
        max_queries: int | None = None,
        persist_run: bool = True,
    ) -> dict[str, Any]:
        """Run one goal toward a target score using the full goal loop."""
        return self.run_goal_case(
            goal_case,
            mode=mode,
            max_rounds=max_rounds,
            plan_count=plan_count,
            max_queries=max_queries,
            target_score=target_score,
            plateau_rounds=plateau_rounds,
            persist_run=persist_run,
        )

    def run_goal_benchmark(
        self,
        goals: list[str | Path | dict[str, Any]],
        *,
        mode: str | None = None,
        max_rounds: int = 1,
        plan_count: int = 1,
        max_queries: int = 1,
        target_score: int | None = None,
        plateau_rounds: int | None = None,
        include_results: bool = False,
    ) -> dict[str, Any]:
        """Run multiple goal cases and return the benchmark payload.

        `goals` currently accepts goal ids or file paths. Inline goal-case
        dicts are intentionally rejected here to keep benchmark inputs
        path-addressable.
        """
        goal_paths: list[Path] = []
        temp_goal_paths: list[Path] = []
        for goal in goals:
            if isinstance(goal, dict):
                raise TypeError(
                    "run_goal_benchmark currently accepts goal ids or paths, not inline dict goal cases"
                )
            path = Path(goal)
            if path.exists():
                goal_paths.append(path)
            else:
                resolved = self.resolve_goal_case(goal)
                if mode:
                    resolved["mode"] = str(mode).strip()
                    with tempfile.NamedTemporaryFile(
                        mode="w",
                        suffix=".json",
                        prefix=f"benchmark-{resolved.get('id')}-",
                        dir=self.goal_cases_root,
                        delete=False,
                        encoding="utf-8",
                    ) as handle:
                        handle.write(
                            json.dumps(resolved, ensure_ascii=False, indent=2) + "\n"
                        )
                        benchmark_path = Path(handle.name)
                    temp_goal_paths.append(benchmark_path)
                    goal_paths.append(benchmark_path)
                    continue
                goal_paths.append(
                    Path(self.goal_cases_root / f"{resolved.get('id')}.json")
                )
        try:
            benchmark = run_benchmark(
                goal_paths,
                max_rounds=max_rounds,
                plan_count=plan_count,
                max_queries=max_queries,
                target_score=target_score,
                plateau_rounds=plateau_rounds,
            )
        finally:
            for path in temp_goal_paths:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    continue
        if include_results:
            return self._api_payload("run_goal_benchmark", benchmark)
        return self._api_payload("run_goal_benchmark", benchmark["payload"])

    def optimize_goals(
        self,
        goals: list[str | Path | dict[str, Any]],
        *,
        mode: str | None = None,
        target_score: int = 100,
        max_rounds: int = 8,
        plateau_rounds: int = 3,
        plan_count: int = 1,
        max_queries: int = 1,
        include_results: bool = False,
    ) -> dict[str, Any]:
        """Run a benchmark with target-oriented defaults for all goals."""
        return self.run_goal_benchmark(
            goals,
            mode=mode,
            max_rounds=max_rounds,
            plan_count=plan_count,
            max_queries=max_queries,
            target_score=target_score,
            plateau_rounds=plateau_rounds,
            include_results=include_results,
        )

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
        """Run the plain engine search task interface."""
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
        return self._api_payload("run_search_task", Engine(config, self.base_dir).run())

    def doctor(self, providers: list[str] | None = None) -> dict[str, Any]:
        """Return the current source capability report."""
        return self._api_payload("doctor", refresh_source_capability(providers))

    def run_watch(self, watch: dict[str, Any]) -> dict[str, Any]:
        """Run one scheduled goal watch profile."""
        return self._api_payload(
            "run_watch",
            _run_watch(
                watch,
                resolve_goal_case=self.resolve_goal_case,
                optimize_goal=self.optimize_goal,
            ),
        )

    def run_watches(self, watches: list[dict[str, Any]]) -> dict[str, Any]:
        """Run multiple independent goal watches and aggregate the results."""
        return self._api_payload(
            "run_watches",
            _run_watches(
                list(watches or []),
                resolve_goal_case=self.resolve_goal_case,
                optimize_goal=self.optimize_goal,
            ),
        )

    def run_orchestrated(
        self,
        task_spec: str,
        *,
        max_steps: int = 50,
        budget: dict[str, Any] | None = None,
        mode: str = "balanced",
        model: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run an AI-orchestrated search task using the capabilities system.

        The orchestrator reads capability descriptions, uses LLM to plan and
        execute search steps, and returns collected evidence with learnings.
        """
        from orchestrator import run_task
        return run_task(
            task_spec,
            max_steps=max_steps,
            budget=budget,
            mode=mode,
            model=model,
            dry_run=dry_run,
        )


def default_interface() -> AutoSearchInterface:
    """Return an AutoSearchInterface rooted at the repository base dir."""
    return AutoSearchInterface()
