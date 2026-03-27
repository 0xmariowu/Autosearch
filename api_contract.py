"""Public API product contract for AutoSearch.

This module centralizes versioning, method metadata, and response envelopes for
the compatibility surface exposed by interface.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


API_NAME = "autosearch-public-api"
API_VERSION = "v1alpha1"
CONTRACT_REVISION = "2026-03-26"
DOC_PATH = "docs/2026-03-26-interface-contract.md"


@dataclass(frozen=True)
class APIMethodSpec:
    name: str
    stability: str
    result_kind: str
    summary: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


METHOD_SPECS: dict[str, APIMethodSpec] = {
    "api_info": APIMethodSpec(
        "api_info",
        "stable",
        "metadata",
        "Describe the public API product and method catalog.",
    ),
    "api_method": APIMethodSpec(
        "api_method", "stable", "metadata", "Describe one public API method contract."
    ),
    "doctor": APIMethodSpec(
        "doctor", "stable", "capability_report", "Return source capability state."
    ),
    "goal_capability_report": APIMethodSpec(
        "goal_capability_report",
        "stable",
        "capability_report",
        "Return goal-scoped capability state.",
    ),
    "goal_platforms": APIMethodSpec(
        "goal_platforms",
        "stable",
        "platforms",
        "Return effective goal-scoped provider configs.",
    ),
    "normalize_query": APIMethodSpec(
        "normalize_query",
        "stable",
        "query_spec",
        "Normalize a query into the public query shape.",
    ),
    "run_search_task": APIMethodSpec(
        "run_search_task",
        "stable",
        "search_run",
        "Run the plain engine search workflow.",
    ),
    "search_goal_query": APIMethodSpec(
        "search_goal_query",
        "stable",
        "query_execution",
        "Execute one goal-scoped query.",
    ),
    "replay_goal_queries": APIMethodSpec(
        "replay_goal_queries",
        "stable",
        "query_replay",
        "Replay multiple goal-scoped queries.",
    ),
    "fetch_document": APIMethodSpec(
        "fetch_document",
        "stable",
        "document",
        "Fetch one document through the acquisition pipeline.",
    ),
    "enrich_record": APIMethodSpec(
        "enrich_record", "stable", "enriched_record", "Enrich one evidence-like record."
    ),
    "build_markdown_views": APIMethodSpec(
        "build_markdown_views",
        "stable",
        "markdown_views",
        "Build clean and fitted markdown views.",
    ),
    "chunk_document": APIMethodSpec(
        "chunk_document",
        "stable",
        "chunk_ranking",
        "Return ranked chunks for one document.",
    ),
    "normalize_result_record": APIMethodSpec(
        "normalize_result_record",
        "stable",
        "evidence_record",
        "Normalize a raw search result.",
    ),
    "normalize_acquired_document": APIMethodSpec(
        "normalize_acquired_document",
        "stable",
        "evidence_record",
        "Normalize an acquired document.",
    ),
    "normalize_evidence_record": APIMethodSpec(
        "normalize_evidence_record",
        "stable",
        "evidence_record",
        "Normalize a dict-shaped evidence record.",
    ),
    "coerce_evidence_record": APIMethodSpec(
        "coerce_evidence_record",
        "stable",
        "evidence_record",
        "Coerce one item into an evidence record.",
    ),
    "coerce_evidence_records": APIMethodSpec(
        "coerce_evidence_records",
        "stable",
        "evidence_record_list",
        "Coerce a list of items into evidence records.",
    ),
    "build_research_plan": APIMethodSpec(
        "build_research_plan",
        "beta",
        "research_plan",
        "Build one round of research plans.",
    ),
    "execute_research_plan": APIMethodSpec(
        "execute_research_plan",
        "beta",
        "research_execution",
        "Execute one research plan.",
    ),
    "synthesize_research_round": APIMethodSpec(
        "synthesize_research_round",
        "beta",
        "research_round",
        "Synthesize one research round.",
    ),
    "build_routeable_output": APIMethodSpec(
        "build_routeable_output",
        "stable",
        "routeable_output",
        "Build the routeable handoff artifact.",
    ),
    "build_research_packet": APIMethodSpec(
        "build_research_packet",
        "stable",
        "research_packet",
        "Build the standalone research packet.",
    ),
    "run_goal_case": APIMethodSpec(
        "run_goal_case", "stable", "goal_run", "Run the full goal loop."
    ),
    "optimize_goal": APIMethodSpec(
        "optimize_goal", "stable", "goal_run", "Run a goal toward a target score."
    ),
    "run_goal_benchmark": APIMethodSpec(
        "run_goal_benchmark", "stable", "benchmark", "Run multiple goal cases."
    ),
    "optimize_goals": APIMethodSpec(
        "optimize_goals", "stable", "benchmark", "Run a target-oriented benchmark."
    ),
    "run_watch": APIMethodSpec(
        "run_watch", "stable", "watch_run", "Run one watch profile."
    ),
    "run_watches": APIMethodSpec(
        "run_watches", "stable", "watch_batch", "Run multiple watch profiles."
    ),
}


def method_spec(method: str) -> APIMethodSpec:
    return METHOD_SPECS[method]


def api_meta(method: str) -> dict[str, str]:
    spec = method_spec(method)
    return {
        "name": API_NAME,
        "version": API_VERSION,
        "revision": CONTRACT_REVISION,
        "method": spec.name,
        "stability": spec.stability,
        "result_kind": spec.result_kind,
        "doc_path": DOC_PATH,
    }


def with_api_meta(payload: dict[str, Any], method: str) -> dict[str, Any]:
    return {
        **dict(payload or {}),
        "_api": api_meta(method),
    }


def method_catalog() -> list[dict[str, str]]:
    return [spec.to_dict() for spec in METHOD_SPECS.values()]


def api_info_payload() -> dict[str, Any]:
    return with_api_meta(
        {
            "api_name": API_NAME,
            "api_version": API_VERSION,
            "contract_revision": CONTRACT_REVISION,
            "doc_path": DOC_PATH,
            "methods": method_catalog(),
        },
        "api_info",
    )


def api_method_payload(method: str) -> dict[str, Any]:
    spec = method_spec(method)
    return with_api_meta(
        {
            "method": spec.name,
            "stability": spec.stability,
            "result_kind": spec.result_kind,
            "summary": spec.summary,
            "doc_path": DOC_PATH,
        },
        "api_method",
    )


def serialize_acquired_document(document: Any) -> dict[str, Any]:
    return {
        "document_id": str(getattr(document, "document_id", "") or ""),
        "url": str(getattr(document, "url", "") or ""),
        "final_url": str(getattr(document, "final_url", "") or ""),
        "status_code": int(getattr(document, "status_code", 0) or 0),
        "content_type": str(getattr(document, "content_type", "") or ""),
        "fetch_method": str(getattr(document, "fetch_method", "") or ""),
        "title": str(getattr(document, "title", "") or ""),
        "text": str(getattr(document, "text", "") or ""),
        "raw_html_path": str(getattr(document, "raw_html_path", "") or ""),
        "clean_markdown": str(getattr(document, "clean_markdown", "") or ""),
        "fit_markdown": str(getattr(document, "fit_markdown", "") or ""),
        "chunk_scores": list(getattr(document, "chunk_scores", []) or []),
        "selected_chunks": list(getattr(document, "selected_chunks", []) or []),
        "references": list(getattr(document, "references", []) or []),
        "metadata": dict(getattr(document, "metadata", {}) or {}),
        "used_render_fallback": bool(getattr(document, "used_render_fallback", False)),
    }
