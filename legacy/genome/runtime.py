"""Genome Runtime — a generic interpreter that reads a Genome JSON and
executes its phases using registered Primitives.

The runtime contains NO strategy decisions.  All behavior comes from
the genome: which primitives to call, in what order, with what config.
The runtime is the "CPU"; the genome is the "program".

Target: ~200-400 lines.  If this file exceeds 400 lines, strategy
logic has leaked in and should move to the genome.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .primitives import call_primitive, list_primitives
from .schema import GenomeSchema, PhaseSpec

logger = logging.getLogger(__name__)


@dataclass
class PhaseResult:
    name: str
    hits: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    queries_used: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeResult:
    genome_id: str = ""
    task: str = ""
    intent: str = "research"
    evidence: list[dict[str, Any]] = field(default_factory=list)
    phase_results: list[PhaseResult] = field(default_factory=list)
    total_hits: int = 0
    unique_urls: int = 0
    rounds_completed: int = 0
    stale_rounds: int = 0
    elapsed_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "task": self.task,
            "intent": self.intent,
            "evidence_count": len(self.evidence),
            "evidence": self.evidence,
            "total_hits": self.total_hits,
            "unique_urls": self.unique_urls,
            "rounds_completed": self.rounds_completed,
            "stale_rounds": self.stale_rounds,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "phases": [
                {
                    "name": pr.name,
                    "hits": len(pr.hits),
                    "evidence": len(pr.evidence),
                    "queries": pr.queries_used,
                }
                for pr in self.phase_results
            ],
            "metadata": self.metadata,
        }


def execute(genome: GenomeSchema, task: str, **kwargs: Any) -> RuntimeResult:
    """Execute a search task using the given genome.

    Args:
        genome: The genome to interpret.
        task: Natural language task description.
        **kwargs: Optional overrides:
            platforms: list of platform dicts (skip health check)
            genes: dict of gene lists for query generation
            patterns: list of pattern dicts
            max_rounds: override genome.engine.max_rounds
            output_path: where to write findings JSONL

    Returns:
        RuntimeResult with collected evidence.
    """
    t0 = time.monotonic()
    result = RuntimeResult(
        genome_id=genome.genome_id,
        task=task,
    )

    # Classify intent
    result.intent = _classify_intent(task)
    logger.info("Task intent: %s", result.intent)

    # Resolve platforms
    platforms = kwargs.get("platforms") or _resolve_platforms(genome, result.intent)

    # Shared state across phases
    state = _RuntimeState(
        genome=genome,
        task=task,
        intent=result.intent,
        platforms=platforms,
        genes=kwargs.get("genes") or {},
        patterns=kwargs.get("patterns") or [],
        max_rounds=kwargs.get("max_rounds") or genome.engine.max_rounds,
        output_path=kwargs.get("output_path"),
    )

    # Execute phases
    for phase_spec in genome.phases:
        if not phase_spec.capabilities:
            continue
        phase_result = _execute_phase(phase_spec, state)
        result.phase_results.append(phase_result)
        state.accumulated_hits.extend(phase_result.hits)
        state.accumulated_evidence.extend(phase_result.evidence)

        # Stale detection between phases
        new_urls = {h.get("url", "") for h in phase_result.hits if h.get("url")}
        new_unique = new_urls - state.seen_urls
        state.seen_urls.update(new_urls)

        if len(new_unique) == 0 and phase_result.hits:
            state.stale_count += 1
        else:
            state.stale_count = 0

        if state.stale_count >= genome.thresholds.stagnation_window:
            logger.info(
                "Stale detection: %d rounds with no new URLs, stopping",
                state.stale_count,
            )
            break

    result.evidence = state.accumulated_evidence
    result.total_hits = len(state.accumulated_hits)
    result.unique_urls = len(state.seen_urls)
    result.rounds_completed = len(result.phase_results)
    result.stale_rounds = state.stale_count
    result.elapsed_seconds = time.monotonic() - t0

    # Write findings to output if requested
    if state.output_path and result.evidence:
        _write_findings(state.output_path, result.evidence)

    return result


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------


@dataclass
class _RuntimeState:
    genome: GenomeSchema
    task: str
    intent: str
    platforms: list[dict[str, Any]]
    genes: dict[str, list[str]]
    patterns: list[dict[str, Any]]
    max_rounds: int
    output_path: str | None = None
    accumulated_hits: list[dict[str, Any]] = field(default_factory=list)
    accumulated_evidence: list[dict[str, Any]] = field(default_factory=list)
    seen_urls: set[str] = field(default_factory=set)
    stale_count: int = 0
    round_number: int = 0


# ---------------------------------------------------------------------------
# Phase execution
# ---------------------------------------------------------------------------


def _execute_phase(phase: PhaseSpec, state: _RuntimeState) -> PhaseResult:
    """Execute a single phase from the genome."""
    pr = PhaseResult(name=phase.name)
    logger.info("Phase: %s (capabilities=%s)", phase.name, phase.capabilities)

    # Resolve input from previous phases
    input_hits = _resolve_input(phase, state)

    # Generate queries if phase needs them
    queries = _resolve_queries(phase, state)
    pr.queries_used = queries

    # Execute capabilities
    available = set(list_primitives())
    _QUERY_PRODUCERS = {"generate_queries"}
    _META_PRODUCERS = {"classify_intent", "synthesize", "report", "store"}

    for cap_name in phase.capabilities:
        if cap_name not in available:
            logger.warning("Skipping unknown primitive: %s", cap_name)
            continue

        try:
            cap_result = _dispatch_capability(cap_name, queries, input_hits, state)
            if cap_name in _QUERY_PRODUCERS and isinstance(cap_result, list):
                queries = cap_result
                pr.queries_used = cap_result
            elif cap_name in _META_PRODUCERS:
                if isinstance(cap_result, dict):
                    pr.metadata[cap_name] = cap_result
                elif isinstance(cap_result, (int, str)):
                    pr.metadata[cap_name] = cap_result
            elif isinstance(cap_result, list):
                pr.hits.extend(item for item in cap_result if isinstance(item, dict))
            elif isinstance(cap_result, dict):
                pr.metadata[cap_name] = cap_result
        except Exception as exc:
            logger.warning("Primitive %s failed: %s", cap_name, exc)

    # Score hits if we have any and score primitive exists
    if pr.hits and "score" in available:
        pr.hits = _apply_scoring(pr.hits, state)

    # Dedup hits
    if pr.hits and "dedup" in available:
        pr.hits = _apply_dedup(pr.hits, state)

    # Convert hits to evidence records
    pr.evidence = _hits_to_evidence(pr.hits, state)

    return pr


def _dispatch_capability(
    cap_name: str,
    queries: list[str],
    input_hits: list[dict[str, Any]],
    state: _RuntimeState,
) -> Any:
    """Call a primitive with appropriate inputs based on its type."""
    if cap_name == "search":
        return _run_search(queries, state)
    if cap_name == "generate_queries":
        return _run_generate_queries(state)
    if cap_name == "score":
        return []  # handled separately in _apply_scoring
    if cap_name == "dedup":
        return []  # handled separately in _apply_dedup
    if cap_name == "cross_ref":
        return call_primitive(
            "cross_ref",
            {
                "hits": input_hits or state.accumulated_hits[-200:],
                "jaccard_threshold": state.genome.thresholds.dedup_jaccard,
            },
        )
    if cap_name == "synthesize":
        return call_primitive(
            "synthesize",
            {
                "evidence": input_hits or state.accumulated_hits[-100:],
            },
        )
    if cap_name == "store":
        return call_primitive(
            "store",
            {
                "records": input_hits or state.accumulated_hits[-200:],
            },
        )
    if cap_name == "report":
        return call_primitive(
            "report",
            {
                "evidence": input_hits or state.accumulated_evidence[-100:],
                "template": state.intent,
            },
        )
    if cap_name == "extract_entities":
        texts = [
            h.get("title", "") + " " + h.get("snippet", "")
            for h in (input_hits or state.accumulated_hits[-50:])
        ]
        return call_primitive("extract_entities", {"texts": texts})
    if cap_name == "classify_intent":
        return call_primitive("classify_intent", {"query": state.task})
    if cap_name == "score_consensus":
        return call_primitive(
            "score_consensus",
            {
                "hits": input_hits or state.accumulated_hits[-200:],
            },
        )
    if cap_name == "evaluate_engagement":
        results = []
        formulas = state.genome.scoring.engagement_formulas
        for hit in input_hits or state.accumulated_hits[-100:]:
            platform = hit.get("source") or hit.get("provider") or ""
            score = call_primitive(
                "evaluate_engagement",
                {
                    "metrics": hit,
                    "platform": platform,
                    "formulas": formulas,
                },
            )
            results.append({**hit, "engagement_score": score})
        return results
    if cap_name == "fetch":
        urls = [h.get("url", "") for h in (input_hits or [])[:10] if h.get("url")]
        results = []
        for url in urls:
            try:
                doc = call_primitive("fetch", {"url": url})
                results.append(doc)
            except Exception as exc:
                logger.warning("fetch %s failed: %s", url, exc)
        return results

    # Generic fallback: try calling with input_hits
    return call_primitive(cap_name, {"input": input_hits})


# ---------------------------------------------------------------------------
# Search execution
# ---------------------------------------------------------------------------


def _run_search(queries: list[str], state: _RuntimeState) -> list[dict[str, Any]]:
    """Run search across platforms for all queries."""
    all_hits: list[dict[str, Any]] = []
    timeout = state.genome.orchestrator.search_timeout

    def _search_one(query: str, platform: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            return call_primitive(
                "search",
                {
                    "query": query,
                    "platform": platform,
                    "limit": state.genome.engine.queries_per_round,
                },
            )
        except Exception as exc:
            logger.warning(
                "search(%s, %s) failed: %s",
                query[:30],
                platform.get("name", "?"),
                exc,
            )
            return []

    tasks = [(q, p) for q in queries for p in state.platforms]

    if not tasks:
        return all_hits

    max_workers = min(len(tasks), 6)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_search_one, q, p): (q, p) for q, p in tasks}
        for future in as_completed(futures, timeout=timeout):
            try:
                hits = future.result()
                all_hits.extend(hits)
            except Exception:
                continue

    return all_hits


def _run_generate_queries(state: _RuntimeState) -> list[str]:
    """Generate queries using the primitive."""
    try:
        return call_primitive(
            "generate_queries",
            {
                "task": state.task,
                "genes": state.genes,
                "config": {
                    "queries_per_round": state.genome.engine.queries_per_round,
                    "llm_ratio": state.genome.engine.llm_ratio,
                    "pattern_ratio": state.genome.engine.pattern_ratio,
                    "gene_ratio": state.genome.engine.gene_ratio,
                    "patterns": state.patterns,
                },
            },
        )
    except Exception as exc:
        logger.warning("generate_queries failed: %s", exc)
        return [state.task]


# ---------------------------------------------------------------------------
# Scoring & dedup
# ---------------------------------------------------------------------------


def _apply_scoring(
    hits: list[dict[str, Any]], state: _RuntimeState
) -> list[dict[str, Any]]:
    """Score hits using genome.scoring config."""
    scoring = state.genome.scoring
    scored = call_primitive(
        "score",
        {
            "hits": hits,
            "query": state.task,
            "scoring_config": {
                "term_weights": scoring.term_weights,
                "preferred_content_types": None,
            },
        },
    )
    return sorted(scored, key=lambda h: h.get("score_hint", 0), reverse=True)


def _apply_dedup(
    hits: list[dict[str, Any]], state: _RuntimeState
) -> list[dict[str, Any]]:
    """Dedup hits using genome.thresholds."""
    return call_primitive(
        "dedup",
        {
            "hits": hits,
            "threshold": state.genome.thresholds.dedup_jaccard,
            "max_per_domain": state.genome.thresholds.per_domain_cap,
        },
    )


# ---------------------------------------------------------------------------
# Intent & platform routing
# ---------------------------------------------------------------------------


def _classify_intent(task: str) -> str:
    """Classify task intent using the primitive."""
    try:
        return call_primitive("classify_intent", {"query": task})
    except Exception:
        return "research"


def _resolve_platforms(genome: GenomeSchema, intent: str) -> list[dict[str, Any]]:
    """Pick platforms based on genome routing + intent."""
    routing = genome.platform_routing

    # Start with intent-specific platforms if available
    intent_platforms = routing.intent_routing.get(intent, [])
    if intent_platforms:
        platforms = [{"name": name} for name in intent_platforms]
    else:
        platforms = list(routing.default_providers)

    # Merge with defaults to ensure minimum coverage
    seen_names = {p.get("name", "") for p in platforms}
    for default in routing.default_providers:
        name = default.get("name", "")
        if name and name not in seen_names:
            platforms.append(default)
            seen_names.add(name)

    return platforms


# ---------------------------------------------------------------------------
# Input resolution
# ---------------------------------------------------------------------------


def _resolve_input(phase: PhaseSpec, state: _RuntimeState) -> list[dict[str, Any]]:
    """Resolve phase input from previous results."""
    if not phase.input_from:
        return []

    input_spec = phase.input_from
    # "top_k:20" — take top K from accumulated hits
    if input_spec.startswith("top_k:"):
        k = int(input_spec.split(":")[1])
        sorted_hits = sorted(
            state.accumulated_hits,
            key=lambda h: h.get("score_hint", 0),
            reverse=True,
        )
        return sorted_hits[:k]

    # "phase:explore" — take output from named phase
    if input_spec.startswith("phase:"):
        # Would need phase results stored by name
        return state.accumulated_hits

    return state.accumulated_hits


def _resolve_queries(phase: PhaseSpec, state: _RuntimeState) -> list[str]:
    """Determine queries for this phase."""
    # If phase has query_source, extract from previous results
    if phase.query_source:
        return _queries_from_source(phase.query_source, state)

    # If generate_queries is in capabilities, it will produce queries
    if "generate_queries" in phase.capabilities:
        return _run_generate_queries(state)

    # Default: use the task itself
    return [state.task]


def _queries_from_source(source: str, state: _RuntimeState) -> list[str]:
    """Extract queries from a source specification."""
    # "extract_entities_from_phase:explore" — entity-based reverse queries
    if source.startswith("extract_entities_from_phase:"):
        texts = [
            h.get("title", "") + " " + h.get("snippet", "")
            for h in state.accumulated_hits[-50:]
        ]
        try:
            entities = call_primitive("extract_entities", {"texts": texts})
            return [f"{state.task} {entity}" for entity in entities[:10]]
        except Exception:
            return [state.task]

    return [state.task]


# ---------------------------------------------------------------------------
# Evidence conversion
# ---------------------------------------------------------------------------


def _hits_to_evidence(
    hits: list[dict[str, Any]], state: _RuntimeState
) -> list[dict[str, Any]]:
    """Convert scored/deduped hits into evidence records."""
    evidence = []
    for hit in hits:
        url = hit.get("url", "")
        if not url:
            continue
        evidence.append(
            {
                "url": url,
                "title": hit.get("title", "")[:150],
                "snippet": hit.get("snippet", "")[:500],
                "source": hit.get("source") or hit.get("provider", ""),
                "query": hit.get("query", state.task),
                "score_hint": hit.get("score_hint", 0),
                "engagement_score": hit.get("engagement_score", 0),
                "backend": hit.get("backend", ""),
            }
        )
    return evidence


def _write_findings(output_path: str, evidence: list[dict[str, Any]]) -> None:
    """Write evidence to JSONL file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for record in evidence:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("Wrote %d findings to %s", len(evidence), path)
