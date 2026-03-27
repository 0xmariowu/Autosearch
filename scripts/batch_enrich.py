#!/usr/bin/env python3
"""Batch-enrich evidence records that lack page content.

Loads evidence-index.jsonl, finds records without acquired content,
enriches the most keyword-relevant ones, and writes back.

Usage:
  python3 scripts/batch_enrich.py
  python3 scripts/batch_enrich.py --goal-case atoms-auto-mining-perfect --limit 60
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from acquisition import enrich_evidence_record
from evidence import build_evidence_record
from goal_judge import _dimension_keywords, _finding_texts, _keyword_match

GREEN = "\033[0;32m"
YELLOW = "\033[0;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[batch_enrich]{NC} {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"{YELLOW}[batch_enrich]{NC} {msg}", file=sys.stderr)


def load_goal_case(name: str) -> dict[str, Any]:
    """Load goal case definition by name."""
    path = REPO_ROOT / "goal_cases" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_evidence_index(name: str) -> tuple[Path, list[dict[str, Any]]]:
    """Load evidence-index.jsonl and return (path, records)."""
    path = REPO_ROOT / "goal_cases" / "runtime" / name / "evidence-index.jsonl"
    if not path.exists():
        return path, []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return path, records


def keyword_coverage_score(
    record: dict[str, Any], dimensions: list[dict[str, Any]]
) -> int:
    """Count total keyword hits across all dimensions for a record."""
    texts = _finding_texts([record])
    total = 0
    for dim in dimensions:
        keywords = _dimension_keywords(dim)
        for kw in keywords:
            if _keyword_match(kw, texts):
                total += 1
    return total


def enrich_and_rebuild(
    record: dict[str, Any], prefer_acquired_text: bool
) -> dict[str, Any]:
    """Enrich a record with page content and optionally rebuild body."""
    query = str(record.get("query") or "")
    enriched = enrich_evidence_record(record, timeout=12, query=query)

    if prefer_acquired_text and enriched.get("acquired_text"):
        rebuilt = build_evidence_record(
            title=str(enriched.get("acquired_title") or enriched.get("title") or ""),
            url=str(enriched.get("url") or ""),
            body=str(enriched.get("acquired_text") or ""),
            source=str(enriched.get("source") or ""),
            query=query,
            clean_markdown=str(enriched.get("clean_markdown") or ""),
            fit_markdown=str(enriched.get("fit_markdown") or ""),
            references=list(enriched.get("references") or []),
        )
        rebuilt["acquired"] = True
        rebuilt["acquired_text"] = str(enriched.get("acquired_text") or "")
        return rebuilt

    return enriched


def save_evidence_index(path: Path, records: list[dict[str, Any]]) -> None:
    """Write records back to evidence-index.jsonl atomically."""
    import os

    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-enrich evidence records")
    parser.add_argument(
        "--goal-case",
        default="atoms-auto-mining-perfect",
        help="Goal case name (default: atoms-auto-mining-perfect)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=60,
        help="Max records to enrich (default: 60)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be enriched without fetching",
    )
    args = parser.parse_args()

    goal_case = load_goal_case(args.goal_case)
    dimensions = list(goal_case.get("dimensions") or [])
    prefer_acquired_text = bool(
        (goal_case.get("evidence_policy") or {}).get("prefer_acquired_text", False)
    )

    index_path, records = load_evidence_index(args.goal_case)
    if not records:
        warn(f"No evidence records found for {args.goal_case}")
        sys.exit(1)

    unenriched = [(i, r) for i, r in enumerate(records) if not r.get("acquired")]
    log(f"Total: {len(records)}, unenriched: {len(unenriched)}")

    scored = [(i, r, keyword_coverage_score(r, dimensions)) for i, r in unenriched]
    scored.sort(key=lambda x: x[2], reverse=True)

    candidates = scored[: args.limit]
    log(f"Will enrich top {len(candidates)} by keyword coverage")

    if args.dry_run:
        for _, record, score in candidates:
            title = str(record.get("title") or "")[:80]
            log(f"  [{score} hits] {title}")
        return

    enriched_count = 0
    failed_count = 0
    for idx, (record_index, record, score) in enumerate(candidates):
        title = str(record.get("title") or "")[:60]
        try:
            updated = enrich_and_rebuild(record, prefer_acquired_text)
            if updated.get("acquired") or updated.get("fit_markdown"):
                records[record_index] = updated
                enriched_count += 1
                log(f"  [{idx + 1}/{len(candidates)}] OK: {title}")
            else:
                log(f"  [{idx + 1}/{len(candidates)}] no content: {title}")
        except Exception as e:
            failed_count += 1
            warn(f"  [{idx + 1}/{len(candidates)}] FAIL: {title} — {e}")

    save_evidence_index(index_path, records)
    log(
        f"\nDone: {enriched_count} enriched, {failed_count} failed, saved to {index_path}"
    )


if __name__ == "__main__":
    main()
