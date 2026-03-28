"""Genome loading, merging, and validation for AutoSearch AVO evolution.

Public API:
    load_genome(path)       → GenomeSchema from a JSON file
    merge_genome(base, ovr) → GenomeSchema with overrides applied
    validate_genome(genome) → list of error strings (empty = valid)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import GenomeSchema


GENOME_DEFAULTS_DIR = Path(__file__).resolve().parent / "defaults"


def load_genome(path: str | Path) -> GenomeSchema:
    """Load a genome from a JSON file.  Missing sections use defaults."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Genome file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Genome file must contain a JSON object: {p}")
    return GenomeSchema.from_dict(data)


def load_default_genome() -> GenomeSchema:
    """Build the default genome by merging all genome/defaults/*.json files."""
    merged: dict[str, Any] = {}
    section_files = {
        "engine": "engine.json",
        "orchestrator": "orchestrator.json",
        "modes": "modes.json",
        "scoring": "scoring.json",
        "platform_routing": "platform_routing.json",
        "thresholds": "thresholds.json",
        "synthesis": "synthesis.json",
        "query_generation": "query_generation.json",
    }
    for section, filename in section_files.items():
        fp = GENOME_DEFAULTS_DIR / filename
        if fp.exists():
            merged[section] = json.loads(fp.read_text(encoding="utf-8"))
    return GenomeSchema.from_dict(merged)


def merge_genome(base: GenomeSchema, overrides: dict[str, Any]) -> GenomeSchema:
    """Deep-merge *overrides* into *base*, returning a new GenomeSchema.

    Only keys present in *overrides* are replaced; everything else
    carries over from *base*.
    """
    base_dict = base.to_dict()
    _deep_merge(base_dict, overrides)
    return GenomeSchema.from_dict(base_dict)


def validate_genome(genome: GenomeSchema) -> list[str]:
    """Return a list of validation errors.  Empty list = valid."""
    errors: list[str] = []

    # Required metadata
    if not genome.version:
        errors.append("Missing version")

    # Engine bounds
    e = genome.engine
    if e.max_rounds < 1:
        errors.append(f"engine.max_rounds must be >= 1, got {e.max_rounds}")
    if e.max_stale < 1:
        errors.append(f"engine.max_stale must be >= 1, got {e.max_stale}")
    if not (0 <= e.llm_ratio <= 1):
        errors.append(f"engine.llm_ratio must be in [0,1], got {e.llm_ratio}")
    if not (0 <= e.pattern_ratio <= 1):
        errors.append(f"engine.pattern_ratio must be in [0,1], got {e.pattern_ratio}")
    if not (0 <= e.gene_ratio <= 1):
        errors.append(f"engine.gene_ratio must be in [0,1], got {e.gene_ratio}")
    ratio_sum = e.llm_ratio + e.pattern_ratio + e.gene_ratio
    if abs(ratio_sum - 1.0) > 0.01:
        errors.append(f"engine ratios must sum to ~1.0, got {ratio_sum:.2f}")

    # Orchestrator bounds
    o = genome.orchestrator
    if o.max_steps < 1:
        errors.append(f"orchestrator.max_steps must be >= 1, got {o.max_steps}")
    if o.temperature < 0:
        errors.append(f"orchestrator.temperature must be >= 0, got {o.temperature}")

    # Scoring: term_weights must have title/snippet/url/source
    for key in ("title", "snippet", "url", "source"):
        if key not in genome.scoring.term_weights:
            errors.append(f"scoring.term_weights missing key: {key}")

    # Thresholds: concentrations in [0,1]
    t = genome.thresholds
    if not (0 <= t.max_source_concentration <= 1):
        errors.append(
            f"thresholds.max_source_concentration must be in [0,1], got {t.max_source_concentration}"
        )
    if not (0 <= t.max_query_concentration <= 1):
        errors.append(
            f"thresholds.max_query_concentration must be in [0,1], got {t.max_query_concentration}"
        )
    if t.stagnation_window < 1:
        errors.append(
            f"thresholds.stagnation_window must be >= 1, got {t.stagnation_window}"
        )
    if t.stagnation_threshold < 1.0:
        errors.append(
            f"thresholds.stagnation_threshold must be >= 1.0, got {t.stagnation_threshold}"
        )

    # Modes: must have at least balanced
    if "balanced" not in genome.modes:
        errors.append("modes must include 'balanced'")

    # Phases: capabilities must be non-empty strings
    for i, phase in enumerate(genome.phases):
        if not phase.name:
            errors.append(f"phases[{i}] missing name")
        for j, cap in enumerate(phase.capabilities):
            if not str(cap).strip():
                errors.append(f"phases[{i}].capabilities[{j}] is empty")
    from .primitives import list_primitives

    registered = set(list_primitives())
    for i, phase in enumerate(genome.phases):
        for j, cap in enumerate(phase.capabilities):
            if cap and cap not in registered:
                errors.append(
                    f"phases[{i}].capabilities[{j}]: unknown primitive '{cap}'"
                )

    # Engagement formulas: validate syntax (not runtime values)
    from .safe_eval import SafeEvalError, safe_eval

    dummy_vars = {
        "score": 1,
        "comments": 1,
        "awards": 1,
        "stars": 1,
        "forks": 1,
        "watchers": 1,
    }
    for platform, formula in genome.scoring.engagement_formulas.items():
        try:
            safe_eval(formula, dummy_vars)
        except SafeEvalError as exc:
            errors.append(f"scoring.engagement_formulas.{platform}: {exc}")

    return errors


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Recursively merge *overrides* into *base* in place."""
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
