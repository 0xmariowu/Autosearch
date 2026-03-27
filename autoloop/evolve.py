#!/usr/bin/env python3
"""Evolve — dual-layer AutoResearch loop for AI judge score 90+.

Inner loop: heuristic keep/discard (deterministic, fast)
Outer loop: AI judge feedback (identifies real gaps per dimension)

Usage:
  python3 autoloop/evolve.py
  python3 autoloop/evolve.py --target 95 --max-rounds 10
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation_harness import build_bundle
from acquisition import enrich_evidence_record
from evidence.normalize import coerce_evidence_records
from evidence_index import LocalEvidenceIndex
from goal_judge import (
    _bundle_dimensions,
    _bundle_sample,
    _finding_texts,
    _keyword_match,
    _normalize_bundle_result,
)
from goal_services import normalize_query_spec, search_query
from search_mesh.provider_policy import available_platforms as policy_available_platforms
from source_capability import refresh_source_capability

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
RELAXED_HARNESS = {"bundle_policy": {"per_query_cap": 999, "per_source_cap": 999, "per_domain_cap": 999}}

# Colors
GREEN = "\033[0;32m"
RED = "\033[0;31m"
YELLOW = "\033[0;33m"
BOLD = "\033[1m"
DIM = "\033[0;90m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[evolve]{NC} {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"{YELLOW}[evolve]{NC} {msg}", file=sys.stderr)


def load_goal_case() -> dict:
    return json.loads((REPO_ROOT / "goal_cases" / "atoms-auto-mining-perfect.json").read_text(encoding="utf-8"))


def get_index() -> LocalEvidenceIndex:
    return LocalEvidenceIndex(REPO_ROOT / "goal_cases" / "runtime" / "atoms-auto-mining-perfect" / "evidence-index.jsonl")


def ai_judge(goal_case: dict, bundle: list[dict], api_key: str, model: str) -> dict:
    """Call AI judge and get per-dimension scores + feedback."""
    dimensions = _bundle_dimensions(goal_case)
    sample = _bundle_sample(bundle, limit=18, per_query=3)
    sampled_bundle: list[dict[str, Any]] = []
    sample_counts: dict[tuple[str, str, str, str], int] = {}
    for item in sample:
        key = (
            str(item.get("title") or ""),
            str(item.get("url") or ""),
            str(item.get("source") or ""),
            str(item.get("query") or ""),
        )
        seen = sample_counts.get(key, 0)
        match_count = 0
        matched_item: dict[str, Any] | None = None
        for candidate in bundle:
            candidate_key = (
                str(candidate.get("title") or ""),
                str(candidate.get("url") or ""),
                str(candidate.get("source") or ""),
                str(candidate.get("query") or ""),
            )
            if candidate_key != key:
                continue
            if match_count == seen:
                matched_item = candidate
                break
            match_count += 1
        sampled_bundle.append(matched_item or item)
        sample_counts[key] = seen + 1

    rich_sample: list[dict[str, str]] = []
    for item in sampled_bundle:
        entry = {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "source": str(item.get("source") or ""),
            "body": str(item.get("body") or "")[:200],
        }
        for key in ("fit_markdown", "clean_markdown", "acquired_text"):
            content = str(item.get(key) or "").strip()
            if content:
                entry["content"] = content[:500]
                break
        rich_sample.append(entry)

    prompt = (
        "You are a scoring judge only. Do not suggest strategies.\n"
        "Score the cumulative evidence bundle for a concrete project problem.\n"
        f"Problem: {goal_case.get('problem', '')}\n"
        f"Context: {goal_case.get('context_notes', '')}\n"
        f"Dimensions: {json.dumps(dimensions, ensure_ascii=False)}\n"
        f"Evidence bundle ({len(rich_sample)} items): {json.dumps(rich_sample, ensure_ascii=False)}\n\n"
        "Use all available evidence fields, especially title, body, and content, when judging implementation quality.\n"
        "Return JSON with:\n"
        "- score: total 0-100\n"
        "- dimension_scores: {dim_id: 0-20}\n"
        "- dimension_gaps: {dim_id: [list of 2-3 specific, concrete search queries that would find the missing evidence]}\n"
        "  IMPORTANT: dimension_gaps values must be SEARCH QUERIES, not descriptions. Write them as you would type into Google.\n"
        "  Example: instead of 'Need fail-closed gate implementation', write 'github actions fail-closed validation gate dataset release'\n"
        "- rationale: brief summary\n"
        "Only include dimensions with score < 18 in dimension_gaps."
    )

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_API_URL,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}") + 1
    result = json.loads(content[start:end])
    result = _normalize_bundle_result(result, dimensions)
    result["judge"] = f"openrouter:{model}"
    return result


def search_for_gaps(
    gap_queries: list[str],
    platforms: list[dict],
    index: LocalEvidenceIndex,
) -> int:
    """Run targeted searches for AI-identified gaps. Returns count of new evidence added."""
    total_added = 0
    for query_text in gap_queries:
        spec = normalize_query_spec({"text": query_text, "platforms": []})
        try:
            result = search_query(spec, platforms, sampling_policy={"bundle_per_query_cap": 10})
        except Exception:
            continue
        findings = coerce_evidence_records(result.get("findings", []))
        enriched: list[dict[str, Any]] = []
        for finding in findings[:5]:
            try:
                enriched_finding = enrich_evidence_record(
                    finding,
                    timeout=8,
                    use_render_fallback=False,
                    query=query_text,
                )
                enriched.append(enriched_finding)
            except Exception:
                enriched.append(finding)
        if enriched:
            findings = enriched + findings[5:]
        added = index.add(findings)
        if added:
            log(f"  +{added} [{query_text[:60]}]")
        total_added += added
    return total_added


def evolve(
    target_score: int = 90,
    max_rounds: int = 8,
    api_key: str = "",
    model: str = "anthropic/claude-haiku-4.5",
) -> dict:
    goal_case = load_goal_case()
    index = get_index()
    capability_report = refresh_source_capability(goal_case.get("providers"))
    platforms = policy_available_platforms(goal_case, capability_report)
    if not platforms:
        platforms = [{"name": p, "limit": 5} for p in goal_case.get("providers", [])]

    results_log: list[dict] = []
    best_score = 0

    for round_idx in range(1, max_rounds + 1):
        log(f"\n{'='*60}")
        log(f"ROUND {round_idx}/{max_rounds}")

        # Build bundle from all accumulated evidence
        findings = index.load_all()
        bundle = build_bundle([], findings, RELAXED_HARNESS)
        log(f"Evidence: {len(findings)} total, bundle: {len(bundle)}")

        # AI judge scoring
        log("Asking AI judge...")
        try:
            judge_result = ai_judge(goal_case, bundle, api_key, model)
        except Exception as e:
            warn(f"AI judge failed: {e}")
            continue

        score = int(judge_result.get("score", 0))
        dim_scores = dict(judge_result.get("dimension_scores") or {})
        gaps = dict(judge_result.get("dimension_gaps") or {})

        log(f"Score: {BOLD}{score}{NC}/100 (best: {best_score})")
        for dim_id, ds in sorted(dim_scores.items(), key=lambda x: x[1]):
            status = f"{GREEN}✓{NC}" if ds >= 18 else f"{RED}gap{NC}"
            log(f"  {dim_id}: {ds}/20 {status}")

        results_log.append({
            "round": round_idx,
            "score": score,
            "dimension_scores": dim_scores,
            "gaps_found": {k: len(v) for k, v in gaps.items()},
            "evidence_count": len(findings),
            "timestamp": datetime.now().isoformat(),
        })

        if score > best_score:
            best_score = score
            log(f"{GREEN}New best: {score}{NC}")

        # Check if target reached
        if score >= target_score:
            log(f"\n{BOLD}{GREEN}TARGET {target_score} REACHED! Score: {score}{NC}")
            break

        # No gaps identified — AI thinks everything is fine but score is low
        if not gaps:
            warn("No dimension_gaps returned but score < target. Retrying with different prompt angle.")
            # Generate our own gap queries from low-scoring dimensions
            for dim_id, ds in sorted(dim_scores.items(), key=lambda x: x[1]):
                if ds < 18:
                    dim_keywords = []
                    for dim in goal_case.get("dimensions", []):
                        if dim.get("id") == dim_id:
                            dim_keywords = list(dim.get("keywords", []))[:3]
                            break
                    if dim_keywords:
                        gaps[dim_id] = [
                            f"{kw} open source implementation github" for kw in dim_keywords[:2]
                        ]
            if not gaps:
                warn("Cannot generate gap queries. Stopping.")
                break

        # Search for gaps (inner loop — heuristic keep/discard)
        weakest = sorted(gaps.keys(), key=lambda k: dim_scores.get(k, 0))
        for dim_id in weakest:
            gap_queries = list(gaps[dim_id])
            if not gap_queries:
                continue
            log(f"\nHunting {dim_id} ({dim_scores.get(dim_id, 0)}/20):")
            added = search_for_gaps(gap_queries, platforms, index)
            if added == 0:
                # Try broader search with dimension keywords
                for dim in goal_case.get("dimensions", []):
                    if dim.get("id") == dim_id:
                        for kw in list(dim.get("keywords", []))[:3]:
                            broader = [
                                f"{kw} concrete implementation",
                                f"{kw} github repository python",
                            ]
                            added += search_for_gaps(broader, platforms, index)
                        break

    # Final summary
    log(f"\n{'='*60}")
    log(f"EVOLUTION COMPLETE")
    log(f"Rounds: {len(results_log)}")
    log(f"Best score: {best_score}")
    log(f"Score trajectory: {[r['score'] for r in results_log]}")

    return {
        "best_score": best_score,
        "target": target_score,
        "reached": best_score >= target_score,
        "rounds": results_log,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evolve — AI judge driven evolution")
    parser.add_argument("--target", type=int, default=90)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--model", default="anthropic/claude-haiku-4.5")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("Error: OPENROUTER_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    result = evolve(
        target_score=args.target,
        max_rounds=args.max_rounds,
        api_key=api_key,
        model=args.model,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
