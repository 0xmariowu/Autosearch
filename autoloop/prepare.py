#!/usr/bin/env python3
"""Frozen evaluation harness — the prepare.py equivalent.

DO NOT MODIFY THIS FILE. This is the frozen environment.
It loads search_program.py, executes all queries, scores the bundle,
and prints the result. The AI must not change this file.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation_harness import build_bundle
from evidence.normalize import coerce_evidence_records
from goal_judge import evaluate_goal_bundle, _heuristic_bundle_dimension_score, _dimension_keywords as _judge_dimension_keywords
from goal_services import search_query, normalize_query_spec
from search_mesh.provider_policy import available_platforms as policy_available_platforms
from source_capability import refresh_source_capability


def load_search_program() -> dict:
    spec = importlib.util.spec_from_file_location("search_program", REPO_ROOT / "autoloop" / "search_program.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {
        "goal_case_id": getattr(mod, "GOAL_CASE", ""),
        "queries": [str(q).strip() for q in getattr(mod, "QUERIES", []) if str(q).strip()],
        "providers": [str(p).strip() for p in getattr(mod, "PROVIDERS", []) if str(p).strip()],
        "per_query_cap": int(getattr(mod, "PER_QUERY_CAP", 5)),
    }


def load_goal_case(goal_case_id: str) -> dict:
    goal_cases_dir = REPO_ROOT / "goal_cases"
    path = goal_cases_dir / f"{goal_case_id}.json"
    if not path.exists():
        for candidate in goal_cases_dir.glob("*.json"):
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if payload.get("id") == goal_case_id:
                return payload
        raise FileNotFoundError(f"Goal case not found: {goal_case_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def run_search(queries: list[str], providers: list[str], per_query_cap: int, goal_case: dict) -> list[dict]:
    capability_report = refresh_source_capability(providers)
    platforms = policy_available_platforms(goal_case, capability_report)
    if not platforms:
        platforms = [{"name": p, "limit": per_query_cap} for p in providers]

    all_findings = []
    seen_urls = set()
    for query_text in queries:
        query_spec = normalize_query_spec({"text": query_text, "platforms": []})
        try:
            results = search_query(query_spec, platforms, sampling_policy={"bundle_per_query_cap": per_query_cap})
        except Exception:
            continue
        for finding in results.get("findings", []):
            url = str(finding.get("url") or "").strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_findings.append(finding)
    return coerce_evidence_records(all_findings)


def score(goal_case: dict, findings: list[dict]) -> dict:
    harness = {"bundle_policy": {"per_query_cap": 5, "per_source_cap": 18, "per_domain_cap": 18}}
    bundle = build_bundle([], findings, harness)
    judge_result = evaluate_goal_bundle(goal_case, bundle)

    dimensions = list(goal_case.get("dimensions") or [])
    keyword_detail = {}
    for dim in dimensions:
        dim_id = str(dim.get("id") or "")
        keywords = [str(kw) for kw in list(dim.get("keywords") or []) + list(dim.get("aliases") or []) if str(kw).strip()]
        _, hits = _heuristic_bundle_dimension_score(dim, bundle)
        matched_set = {str(h).strip().lower() for h in hits}
        misses = [kw for kw in keywords if kw.lower() not in matched_set]
        keyword_detail[dim_id] = {"hits": list(hits), "misses": misses}

    return {
        "score": int(judge_result.get("score", 0)),
        "dimension_scores": dict(judge_result.get("dimension_scores") or {}),
        "keyword_detail": keyword_detail,
        "finding_count": len(bundle),
        "query_count": len(set(str(f.get("query") or "") for f in findings)),
    }


def main():
    program = load_search_program()
    goal_case = load_goal_case(program["goal_case_id"])

    print(f"goal_case: {program['goal_case_id']}", file=sys.stderr)
    print(f"queries: {len(program['queries'])}", file=sys.stderr)
    print(f"providers: {program['providers']}", file=sys.stderr)

    findings = run_search(program["queries"], program["providers"], program["per_query_cap"], goal_case)
    result = score(goal_case, findings)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    print(f"\n--- SUMMARY ---", file=sys.stderr)
    print(f"score: {result['score']}", file=sys.stderr)
    for dim_id, detail in result["keyword_detail"].items():
        dim_score = result["dimension_scores"].get(dim_id, 0)
        print(f"  {dim_id}: {dim_score}/20  hits={detail['hits']}  misses={detail['misses']}", file=sys.stderr)


if __name__ == "__main__":
    main()
