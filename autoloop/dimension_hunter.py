#!/usr/bin/env python3
"""Dimension Hunter — per-dimension AutoResearch loops.

For each dimension below max score, runs a tight loop:
  1. Identify missing keywords
  2. Generate targeted queries for the most searchable missing keyword
  3. Search through the full AutoSearch stack
  4. Check if any result contains the keyword
  5. If found → save to evidence-index, move to next keyword
  6. If not → try a different query variation
  7. Repeat until all keywords found or max attempts reached

Usage:
  python3 autoloop/dimension_hunter.py                    # hunt all weak dimensions
  python3 autoloop/dimension_hunter.py extraction_completeness  # hunt one dimension
  python3 autoloop/dimension_hunter.py --max-attempts 10  # limit attempts per keyword
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation_harness import build_bundle
from evidence.normalize import coerce_evidence_records
from evidence_index import LocalEvidenceIndex
from goal_judge import (
    _finding_texts,
    _heuristic_bundle_dimension_score,
    _keyword_match,
    evaluate_goal_bundle,
)
from goal_services import normalize_query_spec, search_query
from search_mesh.provider_policy import available_platforms as policy_available_platforms
from source_capability import refresh_source_capability


HARNESS = {"bundle_policy": {"per_query_cap": 5, "per_source_cap": 18, "per_domain_cap": 18}}


def load_goal_case(goal_case_id: str = "atoms-auto-mining-perfect") -> dict:
    path = REPO_ROOT / "goal_cases" / f"{goal_case_id}.json"
    if not path.exists():
        for candidate in (REPO_ROOT / "goal_cases").glob("*.json"):
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            if payload.get("id") == goal_case_id:
                return payload
        raise FileNotFoundError(f"Goal case not found: {goal_case_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_index(goal_case_id: str = "atoms-auto-mining-perfect") -> LocalEvidenceIndex:
    index_dir = REPO_ROOT / "goal_cases" / "runtime" / goal_case_id
    index_dir.mkdir(parents=True, exist_ok=True)
    return LocalEvidenceIndex(index_dir / "evidence-index.jsonl")


def current_keyword_state(goal_case: dict, index: LocalEvidenceIndex) -> dict[str, dict]:
    findings = index.load_all()
    bundle = build_bundle([], findings, HARNESS)
    texts = _finding_texts(bundle)
    state = {}
    for dim in goal_case.get("dimensions", []):
        dim_id = dim["id"]
        keywords = [str(kw) for kw in list(dim.get("keywords", [])) + list(dim.get("aliases", [])) if str(kw).strip()]
        weight = int(dim.get("weight", 20))
        need = max(2, len(keywords) // 2)
        hits = [kw for kw in keywords if _keyword_match(kw, texts)]
        misses = [kw for kw in keywords if not _keyword_match(kw, texts)]
        score, _ = _heuristic_bundle_dimension_score(dim, bundle)
        state[dim_id] = {
            "score": score,
            "weight": weight,
            "need": need,
            "hits": hits,
            "misses": misses,
            "gap": max(0, need - len(hits)),
        }
    return state


def query_variations(keyword: str, dim_id: str, attempt: int) -> list[str]:
    """Generate query variations for a keyword. Different attempts try different angles."""
    base = keyword.lower()
    dim_text = dim_id.replace("_", " ")

    variations_pool = [
        # Attempt 0: exact keyword + context
        [
            f"{keyword}",
            f"{keyword} open source",
            f"{keyword} github",
            f"{keyword} python",
            f"{keyword} implementation",
        ],
        # Attempt 1: keyword + dimension context
        [
            f"{keyword} {dim_text}",
            f"{keyword} dataset",
            f"{keyword} library",
            f"{keyword} tool",
            f"{keyword} framework",
        ],
        # Attempt 2: keyword + specific tech angles
        [
            f"{keyword} python library github",
            f"{keyword} open source project",
            f"{keyword} research paper",
            f"{keyword} benchmark",
            f"{keyword} tutorial",
        ],
        # Attempt 3: keyword fragments + broader search
        [
            f'"{keyword}"',
            f"{keyword} algorithm",
            f"{keyword} comparison",
            f"{keyword} best practices",
            f"{keyword} real world",
        ],
        # Attempt 4: completely different angles
        [
            f"{keyword} case study",
            f"{keyword} production",
            f"{keyword} example code",
            f"{keyword} documentation",
            f"{keyword} npm pypi crate",
        ],
    ]

    idx = attempt % len(variations_pool)
    return variations_pool[idx]


def search_for_keyword(
    keyword: str,
    dim_id: str,
    platforms: list[dict],
    attempt: int,
) -> list[dict]:
    """Run searches for a specific keyword. Returns findings that contain the keyword."""
    queries = query_variations(keyword, dim_id, attempt)
    matched_findings = []
    for query_text in queries:
        spec = normalize_query_spec({"text": query_text, "platforms": []})
        try:
            result = search_query(spec, platforms, sampling_policy={"bundle_per_query_cap": 5})
        except Exception:
            continue
        findings = coerce_evidence_records(list(result.get("findings", [])))
        texts = _finding_texts(findings)
        if _keyword_match(keyword, texts):
            matched_findings.extend(findings)
    return matched_findings


def hunt_dimension(
    goal_case: dict,
    dim_id: str,
    index: LocalEvidenceIndex,
    platforms: list[dict],
    max_attempts: int = 5,
) -> dict:
    """AutoResearch loop for one dimension. Returns summary."""
    state = current_keyword_state(goal_case, index)
    dim_state = state.get(dim_id)
    if not dim_state:
        return {"dim_id": dim_id, "error": "dimension not found"}
    if dim_state["gap"] <= 0:
        return {"dim_id": dim_id, "status": "already_full", "score": dim_state["score"]}

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"HUNTING: {dim_id} ({dim_state['score']}/{dim_state['weight']})", file=sys.stderr)
    print(f"  need {dim_state['gap']} more keyword(s)", file=sys.stderr)
    print(f"  hits:   {dim_state['hits']}", file=sys.stderr)
    print(f"  misses: {dim_state['misses']}", file=sys.stderr)

    keywords_found = []
    keywords_failed = []

    for keyword in dim_state["misses"]:
        if dim_state["gap"] - len(keywords_found) <= 0:
            print(f"  gap filled, skipping remaining keywords", file=sys.stderr)
            break

        found = False
        for attempt in range(max_attempts):
            print(f"  [{keyword}] attempt {attempt+1}/{max_attempts}...", file=sys.stderr, end=" ")
            matched = search_for_keyword(keyword, dim_id, platforms, attempt)
            if matched:
                added = index.add(matched)
                print(f"FOUND! ({len(matched)} findings, {added} new)", file=sys.stderr)
                keywords_found.append(keyword)
                found = True
                break
            else:
                print(f"miss", file=sys.stderr)

        if not found:
            keywords_failed.append(keyword)

    # Re-score after hunting
    new_state = current_keyword_state(goal_case, index)
    new_dim = new_state.get(dim_id, {})
    return {
        "dim_id": dim_id,
        "status": "improved" if keywords_found else "no_improvement",
        "score_before": dim_state["score"],
        "score_after": new_dim.get("score", dim_state["score"]),
        "keywords_found": keywords_found,
        "keywords_failed": keywords_failed,
        "new_hits": new_dim.get("hits", []),
        "remaining_misses": new_dim.get("misses", []),
        "remaining_gap": new_dim.get("gap", 0),
    }


def hunt_all(goal_case: dict, max_attempts: int = 5, target_dims: list[str] | None = None, goal_case_id: str = "atoms-auto-mining-perfect") -> dict:
    """Run dimension hunters for all weak dimensions."""
    index = get_index(goal_case_id)
    capability_report = refresh_source_capability(goal_case.get("providers"))
    platforms = policy_available_platforms(goal_case, capability_report)
    if not platforms:
        platforms = [{"name": p, "limit": 5} for p in goal_case.get("providers", [])]

    state = current_keyword_state(goal_case, index)
    weak_dims = [
        (dim_id, info)
        for dim_id, info in sorted(state.items(), key=lambda x: x[1]["score"])
        if info["gap"] > 0
    ]

    if target_dims:
        weak_dims = [(d, i) for d, i in weak_dims if d in target_dims]

    if not weak_dims:
        print("All dimensions at max score!", file=sys.stderr)
        return {"status": "all_full", "state": state}

    print(f"\nDimension Hunter — {len(weak_dims)} dimension(s) to fix", file=sys.stderr)
    for dim_id, info in weak_dims:
        print(f"  {dim_id}: {info['score']}/{info['weight']} (gap={info['gap']})", file=sys.stderr)

    results = []
    for dim_id, _ in weak_dims:
        result = hunt_dimension(goal_case, dim_id, index, platforms, max_attempts)
        results.append(result)

    # Final composite score
    final_state = current_keyword_state(goal_case, index)
    total_score = sum(info["score"] for info in final_state.values())

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"FINAL SCORE: {total_score}/100", file=sys.stderr)
    for dim_id, info in sorted(final_state.items(), key=lambda x: x[1]["score"]):
        status = "✅" if info["gap"] <= 0 else f"gap={info['gap']}"
        print(f"  {dim_id}: {info['score']}/{info['weight']} {status}", file=sys.stderr)

    return {
        "total_score": total_score,
        "dimension_results": results,
        "final_state": {k: v for k, v in final_state.items()},
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Dimension Hunter — per-dimension keyword search")
    parser.add_argument("dimensions", nargs="*", help="Specific dimensions to hunt (default: all weak)")
    parser.add_argument("--goal-case", default="atoms-auto-mining-perfect", help="Goal case ID")
    parser.add_argument("--max-attempts", type=int, default=5, help="Max search attempts per keyword")
    args = parser.parse_args()

    goal_case = load_goal_case(args.goal_case)
    goal_case_id = str(goal_case.get("id") or args.goal_case)
    target_dims = args.dimensions or None
    result = hunt_all(goal_case, max_attempts=args.max_attempts, target_dims=target_dims, goal_case_id=goal_case_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
