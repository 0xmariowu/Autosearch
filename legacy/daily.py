#!/usr/bin/env python3
"""
AutoSearch Daily Mode — scheduled discovery run.

Reads queries.json topic groups as seed genes, uses the AutoSearch engine
for self-evolving query generation + LLM relevance evaluation.

Replaces Scout's fixed-query search layer while preserving the same
discovery breadth (15 topic groups × all platforms).

Usage:
  python daily.py                          # default queries.json + all platforms
  python daily.py --queries path/to.json   # custom queries file
  python daily.py --dry-run                # show config without running
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from engine import Engine, EngineConfig
from control_plane import CONTROL_PLANE_PATH, refresh_control_plane
from project_experience import (
    EXPERIENCE_HEALTH_PATH,
    load_project_experience_policy,
    refresh_project_experience,
)
from source_capability import (
    LATEST_CAPABILITY_PATH,
    format_source_capability_report,
    get_source_decision,
    load_source_capability_report,
    refresh_source_capability,
)


# Scout-compatible platform set: repos + xreach + exa + exa-site variants.
# Note: queries.json seeds were authored for Scout's platform names
# (github, twitter, exa, reddit) but are platform-agnostic search terms
# that work across all these connectors.
DAILY_PLATFORMS = [
    {"name": "github_repos", "limit": 5, "min_stars": 100},
    {"name": "github_issues", "limit": 5},
    {"name": "twitter_xreach", "limit": 10},
    {"name": "exa", "limit": 5},
    {"name": "reddit_exa", "limit": 5},
    {"name": "hn_exa", "limit": 5},
]

# Daily mode uses Sonnet for higher-quality relevance judgment
DAILY_LLM_MODEL = "claude-sonnet-4-6-20250514"

# Daily runs are shorter (3 rounds) — broad discovery, not deep research
DAILY_MAX_ROUNDS = 3
DAILY_QUERIES_PER_ROUND = 20


def load_queries_data(queries_path: Path) -> dict:
    """Load queries.json once. Returns parsed JSON."""
    try:
        with open(queries_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {queries_path}: {e}", file=sys.stderr)
        sys.exit(1)


def extract_genes(data: dict) -> dict:
    """Convert queries.json topic groups into gene pool for the engine.

    Strategy: extract unique meaningful words from all query strings
    across all topic groups, categorized by their role:
    - entity: product/tool names (Claude, LLM, MCP, etc.)
    - object: what's being searched (framework, agent, server, etc.)
    - context: domain qualifiers (production, TypeScript, 2026, etc.)
    - pain_verb/symptom: kept empty — daily mode is discovery, not pain-search
    """
    # Collect all unique query strings (deduplicated)
    seen_queries: set[str] = set()
    all_queries: list[str] = []
    for group in data.get("topic_groups", []):
        for _platform, queries in group.get("queries", {}).items():
            for q in queries:
                if q not in seen_queries:
                    seen_queries.add(q)
                    all_queries.append(q)

    # Extract unique words (3+ chars)
    all_words: set[str] = set()
    for q in all_queries:
        for w in q.split():
            if len(w) >= 3:
                all_words.add(w)

    # Categorize by role (heuristic)
    entities: set[str] = set()
    objects: set[str] = set()
    contexts: set[str] = set()

    entity_indicators = {
        "claude",
        "llm",
        "mcp",
        "ai",
        "openai",
        "anthropic",
        "gpt",
        "cursor",
        "copilot",
        "aider",
        "codex",
    }
    context_indicators = {
        "2025",
        "2026",
        "production",
        "typescript",
        "python",
        "best",
        "practices",
        "techniques",
        "advanced",
        "new",
        "comparison",
        "tips",
        "recommendation",
        "release",
        "launch",
    }

    for w in all_words:
        wl = w.lower()
        if wl in entity_indicators:
            entities.add(w)
        elif wl in context_indicators:
            contexts.add(w)
        else:
            objects.add(w)

    # Topic group IDs go to objects (domain nouns, not product names)
    for group in data.get("topic_groups", []):
        for part in group["id"].split("-"):
            if len(part) >= 3:
                objects.add(part)

    return {
        "entity": sorted(entities),
        "pain_verb": [],  # daily mode = discovery, not pain-search
        "object": sorted(objects),
        "symptom": [],
        "context": sorted(contexts),
    }


def extract_seed_queries(data: dict) -> list[str]:
    """Extract unique fixed queries from queries.json.

    These are injected as seed queries (separate from LLM suggestions,
    never subject to recency cap) so the engine always covers all
    topic groups across multiple rounds.
    """
    seeds: list[str] = []
    seen: set[str] = set()
    for group in data.get("topic_groups", []):
        for _platform, queries in group.get("queries", {}).items():
            for q in queries:
                if q not in seen:
                    seen.add(q)
                    seeds.append(q)
    return seeds


def extract_query_family_maps(
    data: dict,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Build exact-query and word-vote maps for query family inference."""
    query_family_map: dict[str, str] = {}
    word_map: dict[str, list[str]] = {}
    for group in data.get("topic_groups", []):
        group_id = group.get("id", "unknown")
        for _platform, queries in group.get("queries", {}).items():
            for query in queries:
                query_family_map[query] = group_id
                for word in query.lower().split():
                    if len(word) <= 3:
                        continue
                    if word not in word_map:
                        word_map[word] = []
                    if group_id not in word_map[word]:
                        word_map[word].append(group_id)
    return query_family_map, word_map


def main(genome_path: str = ""):
    # Optional: use orchestrator mode
    if os.environ.get("AUTOSEARCH_USE_ORCHESTRATOR", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        from orchestrator import run_task

        task_spec = "Daily discovery: find new AI repositories, tools, and articles across all configured topics"
        result = run_task(task_spec, max_steps=30, genome_path=genome_path)
        # Write results to standard daily output path
        output_path = (
            f"/tmp/autosearch-daily-orchestrated-{time.strftime('%Y%m%d')}.json"
        )
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(
            f"Orchestrated daily run: {result.get('collected_count', 0)} items -> {output_path}"
        )
        sys.exit(0)

    parser = argparse.ArgumentParser(
        description="AutoSearch Daily — scheduled discovery run",
    )
    parser.add_argument(
        "--queries",
        type=str,
        help="Path to queries.json (default: Armory/scripts/scout/queries.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSONL path (default: /tmp/autosearch-daily-YYYY-MM-DD.jsonl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show config and genes without running",
    )
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip platform pre-flight checks",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        help="Override round count for smoke tests or shorter runs",
    )
    parser.add_argument(
        "--queries-per-round",
        type=int,
        help="Override queries per round for smoke tests or shorter runs",
    )
    parser.add_argument(
        "--genome",
        type=str,
        help="Optional genome JSON path for loading daily config",
    )
    args = parser.parse_args()

    selected_genome_path = genome_path or args.genome or ""
    genome = None
    daily_platforms = list(DAILY_PLATFORMS)
    daily_llm_model = DAILY_LLM_MODEL
    max_rounds_default = DAILY_MAX_ROUNDS
    queries_per_round_default = DAILY_QUERIES_PER_ROUND
    if selected_genome_path:
        from genome import load_genome

        genome = load_genome(selected_genome_path)
        daily_platforms = list(
            getattr(genome.platform_routing, "default_providers", DAILY_PLATFORMS)
            or DAILY_PLATFORMS
        )
        daily_llm_model = str(genome.engine.llm_model or DAILY_LLM_MODEL)
        max_rounds_default = int(genome.engine.max_rounds or DAILY_MAX_ROUNDS)
        queries_per_round_default = int(
            genome.engine.queries_per_round or DAILY_QUERIES_PER_ROUND
        )

    max_rounds = args.max_rounds or max_rounds_default
    queries_per_round = args.queries_per_round or queries_per_round_default

    # Locate queries.json
    if args.queries:
        queries_path = Path(args.queries)
    else:
        armory_root = Path(os.environ.get("ARMORY_ROOT", "/Users/vimala/Armory"))
        queries_path = armory_root / "scripts" / "scout" / "queries.json"

    if not queries_path.exists():
        print(f"Error: queries file not found: {queries_path}", file=sys.stderr)
        sys.exit(1)

    # Load once, extract both genes and seeds from same data
    data = load_queries_data(queries_path)
    genes = extract_genes(data)
    seed_queries = extract_seed_queries(data)

    now = datetime.now().astimezone()
    today = now.strftime("%Y-%m-%d")
    run_id = now.strftime("%Y-%m-%d-daily-%H%M%S")
    output_path = args.output or f"/tmp/autosearch-daily-{today}.jsonl"
    query_family_map, query_family_word_map = extract_query_family_maps(data)
    experience_policy = load_project_experience_policy()
    capability_names = [str(p.get("name") or "") for p in daily_platforms]
    capability_report = (
        load_source_capability_report()
        if args.skip_health_check
        else refresh_source_capability(capability_names)
    )
    refresh_control_plane(
        target_spec=(
            "Repositories, articles, discussions, or tools related to "
            "AI agent development, coding agents, context engineering, "
            "MCP servers, prompt engineering, evaluation frameworks, "
            "or harness/devtool configurations. High-quality means: "
            "learnable architecture, real usage evidence, or novel approach."
        ),
        capability_report=capability_report,
        experience_policy=experience_policy,
        run_id=run_id,
    )

    config_kwargs = {
        "genes": genes,
        "platforms": daily_platforms,
        "target_spec": (
            "Repositories, articles, discussions, or tools related to "
            "AI agent development, coding agents, context engineering, "
            "MCP servers, prompt engineering, evaluation frameworks, "
            "or harness/devtool configurations. High-quality means: "
            "learnable architecture, real usage evidence, or novel approach."
        ),
        "task_name": run_id,
        "run_id": run_id,
        "output_path": output_path,
        "query_family_map": query_family_map,
        "query_family_word_map": query_family_word_map,
        "experience_policy": experience_policy,
        "capability_report": capability_report,
        "max_rounds": max_rounds,
        "queries_per_round": queries_per_round,
        "llm_model": daily_llm_model,
    }
    config = (
        EngineConfig.from_genome(genome, **config_kwargs)
        if genome is not None
        else EngineConfig(**config_kwargs)
    )

    if args.dry_run:
        print("=== Daily Mode Config ===")
        print(f"Queries file: {queries_path}")
        print(f"Output: {output_path}")
        print(f"LLM model: {daily_llm_model}")
        print(f"Run ID: {run_id}")
        print(f"Rounds: {max_rounds}")
        print(f"Queries/round: {queries_per_round}")
        print(f"\nPlatforms ({len(daily_platforms)}):")
        for p in daily_platforms:
            print(f"  {p['name']}")
        print("\nGenes:")
        for cat, words in genes.items():
            print(
                f"  {cat}: {len(words)} words"
                f" — {', '.join(words[:8])}"
                f"{'...' if len(words) > 8 else ''}"
            )
        print(f"\nSeed queries: {len(seed_queries)}")
        for q in seed_queries[:10]:
            print(f"  {q}")
        if len(seed_queries) > 10:
            print(f"  ... and {len(seed_queries) - 10} more")
        return

    # Pre-flight platform health checks
    if not args.skip_health_check:
        print(format_source_capability_report(capability_report))
        print()

    # Clear output file for this day (avoid duplicates on re-run)
    Path(output_path).write_text("")

    # Run engine
    base_dir = Path(__file__).parent
    engine = Engine(config, base_dir)

    # Inject seed queries via dedicated method (no recency cap)
    engine.query_gen.add_seed_queries(seed_queries)

    print(f"=== AutoSearch Daily Run: {today} ===")
    print(f"  Seed queries: {len(seed_queries)} from queries.json")
    print(f"  Gene pool: {sum(len(v) for v in genes.values())} words")
    print(f"  LLM model: {daily_llm_model}")
    print()

    summary = engine.run()
    experience_thresholds = (
        dict(getattr(genome, "thresholds").__dict__) if genome is not None else None
    )
    experience = refresh_project_experience(
        list(engine.search_events),
        thresholds=experience_thresholds,
    )
    experience_policy = experience.get("policy") or load_project_experience_policy()
    control_plane = refresh_control_plane(
        target_spec=config.target_spec,
        capability_report=capability_report,
        experience_policy=experience_policy,
        run_id=run_id,
    )
    summary["experience_health"] = str(EXPERIENCE_HEALTH_PATH)
    summary["capability_health"] = str(LATEST_CAPABILITY_PATH)
    summary["control_plane"] = str(CONTROL_PLANE_PATH)
    summary["experience_events"] = len(engine.search_events)
    summary["cooldown_providers"] = (
        ((experience.get("health") or {}).get("aspects") or {}).get("search") or {}
    ).get("cooldown_providers", [])
    summary["unavailable_providers"] = [
        p["name"]
        for p in daily_platforms
        if get_source_decision(capability_report, str(p.get("name") or ""))[
            "should_skip"
        ]
    ]
    summary["top_runtime_providers"] = (control_plane.get("runtime") or {}).get(
        "top_providers"
    ) or []

    print("\n--- Daily Summary ---")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nFindings: {output_path}")


if __name__ == "__main__":
    main()


def run_with_genome(genome_path: str, task: str, **kwargs) -> dict:
    """Execute daily discovery using a genome instead of hardcoded config."""
    from genome import load_genome
    from genome.runtime import execute

    genome = load_genome(genome_path)
    result = execute(genome, task, **kwargs)
    return result.to_dict()
