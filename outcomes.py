#!/usr/bin/env python3
"""
Outcome tracking for the AutoSearch feedback loop.

Two functions:
1. record_intakes() — called after auto-intake, records {query, repo, intake_date}
2. track_outcomes() — called weekly, measures WHEN/USE production per repo
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


HOME = Path.home()


# Support env var overrides (for launchd rsync mode)
ARMORY_ROOT = Path(os.environ.get(
    "ARMORY_ROOT", "/Volumes/4TB/Armory"))
SCOUT_DIR = Path(os.environ.get(
    "SCOUT_DIR", str(ARMORY_ROOT / "scripts/scout")))
AUTOSEARCH_DIR = Path(__file__).parent

OUTCOMES_PATH = AUTOSEARCH_DIR / "outcomes.jsonl"
EVOLUTION_PATH = AUTOSEARCH_DIR / "evolution.jsonl"
STATE_PATH = SCOUT_DIR / "state.json"
ARMORY_INDEX = ARMORY_ROOT / "armory-index.json"
WHEN_BLOCKS = ARMORY_ROOT / "when-blocks.jsonl"
PATTERNS_PATH = AUTOSEARCH_DIR / "patterns.jsonl"


def record_intakes():
    """After auto-intake, record new {query → repo} links in outcomes.jsonl.

    Reads state.json for newly intaked repos (status=intaked),
    cross-references evolution.jsonl to find which query discovered them.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # Load state.json
    try:
        state = json.loads(STATE_PATH.read_text())
    except Exception as e:
        print(f"[Outcome] Cannot read state.json: {e}")
        return 0

    # Find intaked repos
    intaked = {
        url: info for url, info in state.get("seen_urls", {}).items()
        if info.get("status") == "intaked"
    }

    # Load already-recorded outcomes
    recorded_repos: set[str] = set()
    if OUTCOMES_PATH.exists():
        for line in OUTCOMES_PATH.read_text().splitlines():
            if line.strip():
                try:
                    entry = json.loads(line)
                    recorded_repos.add(entry.get("repo", ""))
                except json.JSONDecodeError:
                    pass

    # Find new intakes (not yet in outcomes.jsonl)
    new_intakes = {
        url: info for url, info in intaked.items()
        if url not in recorded_repos
    }

    if not new_intakes:
        return 0

    query_provenance = _load_query_provenance()

    # Record outcomes
    count = 0
    with open(OUTCOMES_PATH, "a") as f:
        for repo_url, info in new_intakes.items():
            # Try to find source query
            source_query, query_family = _find_source_provenance(
                repo_url, info, query_provenance)

            outcome = {
                "repo": repo_url,
                "intake_date": info.get("first_seen", today),
                "score": info.get("score", 0),
                "source_query": source_query,
                "query_family": query_family,
                "when_use_count": 0,  # filled by track_outcomes later
                "outcome_score": 0,   # filled by track_outcomes later
                "recorded": today,
            }
            f.write(json.dumps(outcome, ensure_ascii=False) + "\n")
            count += 1
            print(f"[Outcome] Recorded: {repo_url} "
                  f"(query: {source_query or 'unknown'})")

    return count


def _load_query_provenance() -> dict[str, dict[str, Any]]:
    """Load strong and weak provenance hints from evolution.jsonl."""
    provenance: dict[str, dict[str, Any]] = {}
    if not EVOLUTION_PATH.exists():
        return provenance

    for line in EVOLUTION_PATH.read_text().splitlines():
        if not line.strip():
            continue
        try:
            exp = json.loads(line)
        except json.JSONDecodeError:
            continue

        query = str(exp.get("query", "") or "")
        if not query:
            continue
        record = provenance.setdefault(
            query,
            {
                "query_family": str(exp.get("query_family") or "unknown"),
                "harvested_urls": set(),
                "repo_slugs": set(),
            },
        )
        query_family = str(exp.get("query_family") or "")
        if query_family:
            record["query_family"] = query_family

        for url in exp.get("harvested_urls", []) or []:
            if isinstance(url, str) and url:
                record["harvested_urls"].add(url.lower())
                if "github.com/" in url.lower():
                    record["repo_slugs"].add(url.lower().replace("https://", "").replace("http://", "").replace("www.", "").replace("github.com/", ""))

        for title in exp.get("sample_titles", []) or []:
            if isinstance(title, str) and "/" in title:
                record["repo_slugs"].add(title.split()[0].lower())

    return provenance


def _find_source_provenance(
    repo_url: str, info: dict,
    query_provenance: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    """Try to find which query and query_family led to discovering this repo."""
    # Extract slug from URL: "github.com/owner/repo" -> "owner/repo"
    slug = repo_url.replace("github.com/", "").lower()
    normalized_repo_url = repo_url.lower()

    # Strongest signal: exact harvested URL match from Phase 2 harvest.
    for query, record in query_provenance.items():
        if normalized_repo_url in record.get("harvested_urls", set()):
            return query, str(record.get("query_family") or "unknown")

    # Fallback: title-derived repo slug match from exploration samples.
    for query, record in query_provenance.items():
        for title in record.get("repo_slugs", set()):
            if slug in title or title in slug:
                return query, str(record.get("query_family") or "unknown")

    return "", "unknown"


def track_outcomes():
    """Weekly: check WHEN/USE production for each intaked repo.

    Reads armory-index.json and when-blocks.jsonl to count
    how many WHEN/USE blocks each repo produced.
    """
    if not OUTCOMES_PATH.exists():
        print("[Outcome] No outcomes.jsonl yet")
        return

    # Load armory index to count entries per repo
    repo_entry_count: dict[str, int] = {}
    try:
        index = json.loads(ARMORY_INDEX.read_text())
        for entry in index.get("entries", []):
            repo = entry.get("repo", "")
            if repo:
                key = "github.com/" + repo.replace("_", "/").lower()
                # Count WHEN blocks in entry
                when_count = len(entry.get("when_blocks", []))
                repo_entry_count[key] = when_count
    except Exception as e:
        print(f"[Outcome] Cannot read armory-index.json: {e}")

    # Load when-blocks.jsonl for total block count per repo
    # when-blocks.jsonl format: {"repo": "owner_name", ...}
    repo_when_blocks: dict[str, int] = {}
    if WHEN_BLOCKS.exists():
        for line in WHEN_BLOCKS.read_text().splitlines():
            if not line.strip():
                continue
            try:
                block = json.loads(line)
                repo_field = block.get("repo", "")
                if repo_field:
                    # Convert "owner_name" to "github.com/owner/name"
                    key = "github.com/" + repo_field.replace(
                        "_", "/", 1).lower()
                    repo_when_blocks[key] = (
                        repo_when_blocks.get(key, 0) + 1)
            except json.JSONDecodeError:
                pass

    # Update outcomes with WHEN/USE counts
    updated_lines = []
    changes = 0
    for line in OUTCOMES_PATH.read_text().splitlines():
        if not line.strip():
            continue
        try:
            outcome = json.loads(line)
            repo = outcome.get("repo", "")
            new_count = repo_when_blocks.get(repo, 0)
            if new_count != outcome.get("when_use_count", 0):
                outcome["when_use_count"] = new_count
                # Outcome score: when_use_count is the primary signal
                outcome["outcome_score"] = (
                    min(100, new_count * 5))  # 20 blocks = max score
                outcome["last_tracked"] = (
                    datetime.now().strftime("%Y-%m-%d"))
                changes += 1
            updated_lines.append(json.dumps(outcome, ensure_ascii=False))
        except json.JSONDecodeError:
            updated_lines.append(line)

    if changes > 0:
        OUTCOMES_PATH.write_text("\n".join(updated_lines) + "\n")
        print(f"[Outcome] Updated {changes} outcome records")

    # Write outcome scores back to patterns.jsonl
    _update_pattern_weights()

    return changes


def _update_pattern_weights():
    """Write outcome-weighted boosts to patterns.jsonl.

    High-outcome queries get boosted in future sessions.
    """
    if not OUTCOMES_PATH.exists():
        return

    # Collect queries with their outcome scores
    query_outcomes: dict[str, list[int]] = {}
    for line in OUTCOMES_PATH.read_text().splitlines():
        if not line.strip():
            continue
        try:
            outcome = json.loads(line)
            query = outcome.get("source_query", "")
            score = outcome.get("outcome_score", 0)
            if query and score > 0:
                if query not in query_outcomes:
                    query_outcomes[query] = []
                query_outcomes[query].append(score)
        except json.JSONDecodeError:
            pass

    if not query_outcomes:
        return

    # Write a single outcome pattern with top queries
    timestamp = datetime.now().strftime("%Y-%m-%d")
    top_queries = sorted(
        query_outcomes.items(),
        key=lambda x: max(x[1]),
        reverse=True,
    )[:10]

    pattern = {
        "pattern": f"outcome_boost_{timestamp}",
        "platform": "all",
        "finding": (
            "Queries with proven outcome (intake → WHEN/USE blocks): "
            + ", ".join(f'"{q}" (score={max(scores)})'
                        for q, scores in top_queries[:5])
        ),
        "impact": "These queries led to repos that produced "
                  "real WHEN/USE blocks. Boost in future sessions.",
        "validated": timestamp,
        "auto_generated": True,
        "outcome_scores": {q: max(s) for q, s in top_queries},
    }

    with open(PATTERNS_PATH, "a") as f:
        f.write(json.dumps(pattern, ensure_ascii=False) + "\n")

    print(f"[Outcome] Wrote outcome boost pattern with "
          f"{len(top_queries)} queries")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "track":
        track_outcomes()
    else:
        count = record_intakes()
        print(f"[Outcome] {count} new intakes recorded")
