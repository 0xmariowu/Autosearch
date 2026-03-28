"""Genome variation operators for AVO evolution.

Implements Vary(P_t) = Agent(P_t, K, f) from the AVO paper:
  - P_t: population of (genome, score) pairs
  - K: knowledge (Armory patterns, search history)
  - f: goal_judge score (fixed contract)

Five mutation types:
  micro_mutation      — change one numeric value
  structural_mutation — add/remove/reorder phases
  crossover           — combine two parent genomes
  supervisor_redirect — LLM-driven full genome rewrite
  knowledge_injection — inject winning patterns from patterns.jsonl
"""

from __future__ import annotations

import copy
import logging
import random
from typing import Any

from .schema import GenomeSchema, PhaseSpec

logger = logging.getLogger(__name__)

# Numeric fields eligible for micro-mutation, grouped by section
_MUTABLE_NUMERICS: dict[str, list[tuple[str, float, float]]] = {
    "engine": [
        ("max_rounds", 3, 50),
        ("queries_per_round", 5, 40),
        ("max_stale", 2, 10),
        ("llm_ratio", 0.0, 0.50),
        ("pattern_ratio", 0.0, 0.50),
        ("gene_ratio", 0.20, 1.0),
    ],
    "orchestrator": [
        ("max_steps", 10, 100),
        ("temperature", 0.0, 1.0),
        ("search_timeout", 10, 60),
    ],
    "thresholds": [
        ("per_query_cap", 2, 20),
        ("per_source_cap", 5, 50),
        ("per_domain_cap", 5, 50),
        ("max_source_concentration", 0.50, 0.95),
        ("max_query_concentration", 0.40, 0.90),
        ("stagnation_threshold", 1.001, 1.10),
        ("dedup_jaccard", 0.50, 0.98),
    ],
    "scoring": [
        ("content_type_bonus", 0, 5),
        ("harmonic_divisor", 5, 20),
        ("generic_cap", 1, 10),
        ("cross_source_bonus", 0.5, 3.0),
    ],
}

# Primitives that can appear in phases
_KNOWN_PRIMITIVES = [
    "search",
    "score",
    "dedup",
    "generate_queries",
    "cross_ref",
    "synthesize",
    "store",
    "report",
    "extract_entities",
    "classify_intent",
    "score_consensus",
    "evaluate_engagement",
    "fetch",
]


def vary_genome(
    parent: GenomeSchema,
    population: list[dict[str, Any]],
    knowledge: list[dict[str, Any]],
    diagnosis: str = "",
) -> tuple[GenomeSchema, str, str]:
    """Create a new genome by mutating *parent*.

    Args:
        parent: The genome to mutate.
        population: List of evolution.jsonl entries (for crossover).
        knowledge: List of pattern dicts from patterns.jsonl.
        diagnosis: Stagnation diagnosis string (guides mutation choice).

    Returns:
        (new_genome, mutation_type, mutation_detail)
    """
    # Choose mutation type based on context
    mutation_type = _choose_mutation_type(parent, population, diagnosis)

    if mutation_type == "micro_mutation":
        child, detail = _micro_mutation(parent)
    elif mutation_type == "structural_mutation":
        child, detail = _structural_mutation(parent)
    elif mutation_type == "crossover":
        child, detail = _crossover(parent, population)
    elif mutation_type == "supervisor_redirect":
        child, detail = _supervisor_redirect(parent, population, diagnosis)
    elif mutation_type == "knowledge_injection":
        child, detail = _knowledge_injection(parent, knowledge)
    else:
        child, detail = _micro_mutation(parent)
        mutation_type = "micro_mutation"

    return child, mutation_type, detail


def _choose_mutation_type(
    parent: GenomeSchema,
    population: list[dict[str, Any]],
    diagnosis: str,
) -> str:
    """Choose mutation type based on context."""
    if diagnosis:
        # Stagnation → try structural or supervisor redirect
        return random.choice(["structural_mutation", "supervisor_redirect"])
    if len(population) >= 2 and random.random() < 0.25:
        return "crossover"
    # Default distribution
    return random.choices(
        ["micro_mutation", "structural_mutation", "knowledge_injection"],
        weights=[0.50, 0.30, 0.20],
        k=1,
    )[0]


# ---------------------------------------------------------------------------
# Mutation operators
# ---------------------------------------------------------------------------


def _micro_mutation(parent: GenomeSchema) -> tuple[GenomeSchema, str]:
    """Change one numeric value within bounds."""
    child = GenomeSchema.from_dict(parent.to_dict())

    # Pick a random section and field
    section_name = random.choice(list(_MUTABLE_NUMERICS.keys()))
    fields = _MUTABLE_NUMERICS[section_name]
    field_name, lo, hi = random.choice(fields)

    section = getattr(child, section_name)
    old_value = getattr(section, field_name)

    # Perturb by ±10-30%
    scale = random.uniform(0.7, 1.3)
    if isinstance(old_value, int):
        new_value = max(int(lo), min(int(hi), int(round(old_value * scale))))
    else:
        new_value = max(lo, min(hi, round(old_value * scale, 4)))

    setattr(section, field_name, new_value)

    # Re-normalize ratios if engine ratios were mutated
    if section_name == "engine" and field_name in (
        "llm_ratio",
        "pattern_ratio",
        "gene_ratio",
    ):
        _normalize_ratios(child)

    detail = f"{section_name}.{field_name}: {old_value} → {new_value}"
    logger.info("micro_mutation: %s", detail)
    return child, detail


def _structural_mutation(parent: GenomeSchema) -> tuple[GenomeSchema, str]:
    """Modify the phase structure: insert, remove, or reorder."""
    child = GenomeSchema.from_dict(parent.to_dict())
    phases = list(child.phases)

    if not phases:
        # No phases → insert one
        new_phase = PhaseSpec(
            name="auto_search",
            capabilities=["generate_queries", "search", "score", "dedup"],
        )
        child.phases = [new_phase]
        return child, "inserted phase: auto_search"

    op = random.choice(["insert", "remove", "reorder", "split"])

    if op == "insert" or len(phases) <= 1:
        # Insert a new phase between existing ones
        new_caps = random.sample(
            _KNOWN_PRIMITIVES,
            k=min(random.randint(2, 4), len(_KNOWN_PRIMITIVES)),
        )
        new_name = f"auto_{random.choice(['explore', 'refine', 'verify', 'expand'])}"
        insert_at = random.randint(0, len(phases))
        new_phase = PhaseSpec(name=new_name, capabilities=new_caps)
        phases.insert(insert_at, new_phase)
        child.phases = phases
        return child, f"inserted phase {new_name} at position {insert_at}"

    if op == "remove" and len(phases) > 1:
        idx = random.randint(0, len(phases) - 1)
        removed = phases.pop(idx)
        child.phases = phases
        return child, f"removed phase {removed.name} from position {idx}"

    if op == "reorder" and len(phases) > 1:
        i, j = random.sample(range(len(phases)), 2)
        name_i, name_j = phases[i].name, phases[j].name
        phases[i], phases[j] = phases[j], phases[i]
        child.phases = phases
        return child, f"swapped phases {name_i} and {name_j}"

    if op == "split" and len(phases) >= 1:
        idx = random.randint(0, len(phases) - 1)
        source = phases[idx]
        if len(source.capabilities) >= 4:
            mid = len(source.capabilities) // 2
            p1 = PhaseSpec(
                name=f"{source.name}_a",
                capabilities=source.capabilities[:mid],
            )
            p2 = PhaseSpec(
                name=f"{source.name}_b",
                capabilities=source.capabilities[mid:],
                input_from=f"phase:{source.name}_a",
            )
            phases[idx : idx + 1] = [p1, p2]
            child.phases = phases
            return child, f"split phase {source.name} into {p1.name} + {p2.name}"

    # Fallback: re-roll as micro_mutation (return correct type)
    child, detail = _micro_mutation(parent)
    return child, f"structural_fallback→{detail}"


def _crossover(
    parent: GenomeSchema, population: list[dict[str, Any]]
) -> tuple[GenomeSchema, str]:
    """Combine sections from parent and another genome in the population."""
    # Filter to entries that have genome files
    genome_entries = [p for p in population[-10:] if p.get("genome_path")]
    if len(genome_entries) < 1:
        child, detail = _micro_mutation(parent)
        return child, f"crossover_fallback→{detail}"

    other_entry = random.choice(genome_entries)
    other_genome_path = other_entry.get("genome_path", "")
    try:
        from . import load_genome

        other = load_genome(other_genome_path)
    except Exception:
        child, detail = _micro_mutation(parent)
        return child, f"crossover_fallback→{detail}"

    child_dict = parent.to_dict()
    other_dict = other.to_dict()

    # Swap a random section
    swappable = ["scoring", "thresholds", "query_generation", "platform_routing"]
    section = random.choice(swappable)
    child_dict[section] = copy.deepcopy(other_dict.get(section, child_dict[section]))

    child = GenomeSchema.from_dict(child_dict)
    detail = f"swapped {section} from genome {other_entry.get('genome_id', '?')}"
    logger.info("crossover: %s", detail)
    return child, detail


def _supervisor_redirect(
    parent: GenomeSchema,
    population: list[dict[str, Any]],
    diagnosis: str,
) -> tuple[GenomeSchema, str]:
    """LLM-guided genome modification based on stagnation diagnosis."""
    child = GenomeSchema.from_dict(parent.to_dict())

    if not diagnosis:
        return _structural_mutation(parent)

    # Parse diagnosis for section hints
    diagnosis_lower = diagnosis.lower()
    if "quantity" in diagnosis_lower or "urls" in diagnosis_lower:
        # Need more results: increase rounds, add platforms
        child.engine.max_rounds = min(child.engine.max_rounds + 5, 50)
        child.engine.queries_per_round = min(child.engine.queries_per_round + 5, 40)
        detail = "supervisor: increased rounds/queries for quantity"
    elif "diversity" in diagnosis_lower:
        # Need more diversity: widen platform routing
        child.thresholds.max_source_concentration = max(
            child.thresholds.max_source_concentration - 0.10, 0.50
        )
        child.thresholds.per_domain_cap = max(child.thresholds.per_domain_cap - 3, 3)
        detail = "supervisor: loosened concentration limits for diversity"
    elif "relevance" in diagnosis_lower:
        # Need better relevance: tighten scoring
        tw = child.scoring.term_weights
        tw["title"] = min(tw.get("title", 4) + 1, 8)
        detail = "supervisor: increased title weight for relevance"
    elif "efficiency" in diagnosis_lower:
        # Need better efficiency: reduce steps
        child.orchestrator.max_steps = max(child.orchestrator.max_steps - 10, 10)
        detail = "supervisor: reduced max_steps for efficiency"
    else:
        # Generic redirect: structural mutation
        return _structural_mutation(parent)

    logger.info("supervisor_redirect: %s", detail)
    return child, detail


def _knowledge_injection(
    parent: GenomeSchema, knowledge: list[dict[str, Any]]
) -> tuple[GenomeSchema, str]:
    """Inject winning patterns from patterns.jsonl into genome config."""
    child = GenomeSchema.from_dict(parent.to_dict())

    if not knowledge:
        return _micro_mutation(parent)

    # Pick a recent winning pattern
    winning = [
        p
        for p in knowledge
        if "winning" in str(p.get("pattern", "")).lower()
        or "success" in str(p.get("finding", "")).lower()
    ]
    pattern = random.choice(winning) if winning else random.choice(knowledge)

    finding = str(pattern.get("finding", ""))

    # Inject: add pattern's winning words as query generation hints
    if finding:
        words = [w for w in finding.split() if len(w) > 4][:5]
        existing = child.query_generation.generic_anchor_tokens
        for w in words:
            if w.lower() not in {t.lower() for t in existing}:
                existing.append(w)

    detail = f"injected pattern: {str(pattern.get('pattern', ''))[:50]}"
    logger.info("knowledge_injection: %s", detail)
    return child, detail


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_ratios(genome: GenomeSchema) -> None:
    """Ensure engine ratios sum to 1.0."""
    e = genome.engine
    total = e.llm_ratio + e.pattern_ratio + e.gene_ratio
    if total > 0 and abs(total - 1.0) > 0.01:
        e.llm_ratio = round(e.llm_ratio / total, 4)
        e.pattern_ratio = round(e.pattern_ratio / total, 4)
        e.gene_ratio = round(1.0 - e.llm_ratio - e.pattern_ratio, 4)
