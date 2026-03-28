"""Genome schema definition for AutoSearch AVO evolution.

A Genome is a complete, JSON-serializable strategy description that the
AVO controller can evolve.  It contains NO executable code — only data
that the Runtime interprets and Primitives execute.

Sections:
  engine           – search tuning (rounds, ratios, stale detection)
  orchestrator     – ReAct-loop parameters (steps, temperature, model)
  modes            – research mode policies (speed / balanced / deep)
  scoring          – lexical weights, engagement formulas, generic filters
  platform_routing – provider selection, tier priority, intent routing
  thresholds       – caps, concentration limits, stagnation detection
  synthesis        – claim terms, cluster limits, report templates
  query_generation – anchor tokens, evidence types, mutation weights
  phases           – ordered list of phase specs (primitives + wiring)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Section dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EngineSection:
    max_stale: int = 5
    max_rounds: int = 15
    queries_per_round: int = 15
    harvest_since: str = "2025-10-01"
    llm_ratio: float = 0.20
    pattern_ratio: float = 0.20
    gene_ratio: float = 0.60
    llm_model: str = "claude-haiku-4-5-20251001"


@dataclass
class OrchestratorSection:
    max_steps: int = 50
    temperature: float = 0.3
    max_tokens: int = 2048
    model: str = "google/gemini-2.5-flash"
    stuck_detect_interval: int = 3
    search_timeout: int = 25
    system_prompt_file: str = "genome/defaults/orchestrator-system-prompt.txt"


@dataclass
class ModeSection:
    name: str = "balanced"
    enable_planning: bool = True
    enable_cross_verification: bool = True
    enable_acquisition: bool = True
    enable_recursive_repair: bool = True
    emit_research_packet: bool = True
    max_branch_depth: int = 3
    max_plan_count: int = 3
    max_queries: int = 5
    page_fetch_limit: int = 2
    prefer_acquired_text: bool = False
    rerank_profile: str = "hybrid"
    branch_budget_per_round: dict[str, int] = field(
        default_factory=lambda: {
            "breadth": 1,
            "repair": 2,
            "followup": 1,
            "probe": 1,
            "research": 1,
        }
    )
    plateau_rounds: int = 3
    stop_on_saturated: bool = False
    max_findings_before_search_disable: int = 40
    disabled_actions: list[str] = field(default_factory=list)


@dataclass
class ScoringSection:
    term_weights: dict[str, int] = field(
        default_factory=lambda: {
            "title": 4,
            "snippet": 2,
            "url": 1,
            "source": 1,
        }
    )
    content_type_bonus: int = 2
    harmonic_divisor: int = 10
    stop_words: list[str] = field(
        default_factory=lambda: [
            "the",
            "and",
            "for",
            "with",
            "that",
            "this",
            "from",
            "into",
            "after",
            "before",
            "what",
            "when",
            "where",
            "which",
            "about",
            "have",
            "has",
            "will",
            "your",
        ]
    )
    tracking_params: list[str] = field(
        default_factory=lambda: [
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "gclsrc",
            "dclid",
            "msclkid",
            "ref",
            "ref_src",
            "ref_url",
            "mc_cid",
            "mc_eid",
            "oly_enc_id",
            "oly_anon_id",
            "_ga",
            "_gl",
            "_hsenc",
            "_hsmi",
            "vero_id",
            "mkt_tok",
        ]
    )
    generic_tokens: list[str] = field(default_factory=list)
    generic_cap: int = 3
    engagement_formulas: dict[str, str] = field(
        default_factory=lambda: {
            "reddit": "0.50*log1p(score) + 0.35*log1p(comments) + 0.15*log1p(awards)",
            "github": "0.40*log1p(stars) + 0.35*log1p(forks) + 0.25*log1p(watchers)",
            "hn": "0.60*log1p(score) + 0.40*log1p(comments)",
        }
    )
    cross_source_bonus: float = 1.0
    consensus_formula: str = "original_score * max(1, provider_count)"


@dataclass
class PlatformRoutingSection:
    status_priority: dict[str, int] = field(
        default_factory=lambda: {
            "ok": 0,
            "warn": 1,
            "off": 9,
            "error": 9,
        }
    )
    tier_priority: dict[str, int] = field(
        default_factory=lambda: {
            "free_default": 0,
            "specialized_free": 1,
            "premium_fallback": 3,
        }
    )
    default_providers: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"name": "github_repos"},
            {"name": "github_issues"},
            {"name": "searxng"},
            {"name": "ddgs"},
            {"name": "reddit", "sub": "all"},
            {"name": "hn"},
        ]
    )
    premium_providers: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"name": "exa"},
            {"name": "tavily"},
            {"name": "twitter_xreach"},
            {"name": "huggingface_datasets"},
        ]
    )
    intent_routing: dict[str, list[str]] = field(
        default_factory=lambda: {
            "how_to": ["github_repos", "searxng", "ddgs"],
            "comparison": ["searxng", "ddgs", "reddit", "hn"],
            "opinion": ["reddit", "hn", "twitter_xreach"],
            "debug": ["github_issues", "searxng", "ddgs"],
            "breaking": ["twitter_xreach", "hn", "reddit"],
            "research": ["github_repos", "searxng", "semantic_scholar"],
            "prediction": ["twitter_xreach", "reddit", "hn"],
        }
    )


@dataclass
class ThresholdsSection:
    # project_experience.py
    recent_run_window: int = 12
    preferred_min_attempts: int = 8
    cooldown_min_attempts: int = 8
    high_value_new_url_rate: float = 0.08
    cooldown_error_rate: float = 0.70
    # evaluation_harness.py / goal_runtime.py
    per_query_cap: int = 5
    per_source_cap: int = 18
    per_domain_cap: int = 18
    # goal_runtime.py anti-cheat
    max_source_concentration: float = 0.82
    max_query_concentration: float = 0.70
    min_new_unique_urls: int = 1
    min_novelty_ratio: float = 0.01
    min_source_diversity: float = 0.15
    # avo.py stagnation
    stagnation_window: int = 3
    stagnation_threshold: float = 1.01
    # dedup / convergence
    dedup_jaccard: float = 0.85
    convergence_jaccard: float = 0.42
    relevance_min: float = 0.0


@dataclass
class SynthesisSection:
    positive_claim_terms: list[str] = field(
        default_factory=lambda: [
            "works",
            "working",
            "passes",
            "passed",
            "verified",
            "reliable",
            "success",
            "successful",
            "stable",
        ]
    )
    negative_claim_terms: list[str] = field(
        default_factory=lambda: [
            "fails",
            "failed",
            "failing",
            "broken",
            "issue",
            "issues",
            "bug",
            "bugs",
            "limitation",
            "limitations",
            "criticism",
            "tradeoff",
            "tradeoffs",
            "regression",
        ]
    )
    claim_stop_words: list[str] = field(
        default_factory=lambda: [
            "the",
            "and",
            "with",
            "that",
            "this",
            "from",
            "into",
            "using",
            "implementation",
            "system",
            "approach",
            "method",
            "results",
            "result",
            "page",
            "report",
            "study",
        ]
    )
    query_cluster_limit: int = 8
    domain_cluster_limit: int = 8
    multi_source_threshold: int = 2
    intent_templates: dict[str, dict[str, Any]] = field(default_factory=dict)
    report_sections: list[str] = field(
        default_factory=lambda: [
            "summary",
            "findings",
            "claim_alignment",
            "clusters",
            "gaps",
        ]
    )


@dataclass
class QueryGenerationSection:
    generic_anchor_tokens: list[str] = field(
        default_factory=lambda: [
            "https",
            "http",
            "github",
            "issue",
            "issues",
            "about",
            "using",
            "validation",
            "report",
            "implementation",
            "details",
            "failure",
            "modes",
            "dataset",
            "public",
            "release",
        ]
    )
    strong_evidence_types: list[str] = field(
        default_factory=lambda: [
            "code",
            "repository",
            "issue",
            "reference",
            "web",
        ]
    )
    anchor_token_limit: int = 4
    recursive_depth_limit: int = 4
    branch_budget_defaults: dict[str, int] = field(
        default_factory=lambda: {
            "breadth": 1,
            "repair": 2,
            "followup": 1,
            "probe": 1,
            "research": 1,
        }
    )
    intent_patterns: dict[str, str] = field(
        default_factory=lambda: {
            "how_to": r"(?i)\b(how\s+to|setup|install|configure|deploy)\b",
            "comparison": r"(?i)\b(vs\.?|versus|compared?\s+to|alternative)\b",
            "opinion": r"(?i)\b(best|worst|review|recommend|should\s+i)\b",
            "debug": r"(?i)\b(error|bug|fix|crash|traceback|exception|fail)\b",
            "breaking": r"(?i)\b(new|launch|announce|release|breaking)\b",
            "research": r"(?i)\b(paper|study|survey|benchmark|evaluation)\b",
            "prediction": r"(?i)\b(future|predict|trend|forecast|roadmap)\b",
        }
    )
    mutation_kinds: dict[str, float] = field(
        default_factory=lambda: {
            "breadth": 0.30,
            "repair": 0.25,
            "followup": 0.20,
            "probe": 0.15,
            "research": 0.10,
        }
    )
    entity_extraction: dict[str, Any] = field(
        default_factory=lambda: {
            "handle_pattern": r"@[\w]+",
            "org_pattern": r"(?:by|from|at)\s+([A-Z][\w]+(?:\s+[A-Z][\w]+)*)",
            "subreddit_pattern": r"r/[\w]+",
        }
    )


@dataclass
class PhaseSpec:
    name: str
    capabilities: list[str] = field(default_factory=list)
    parallel: bool = False
    input_from: str | None = None
    query_source: str | None = None


# ---------------------------------------------------------------------------
# Top-level Genome
# ---------------------------------------------------------------------------


@dataclass
class GenomeSchema:
    version: str = "1.0"
    genome_id: str = ""
    parent_id: str = ""

    engine: EngineSection = field(default_factory=EngineSection)
    orchestrator: OrchestratorSection = field(default_factory=OrchestratorSection)
    modes: dict[str, ModeSection] = field(
        default_factory=lambda: {
            "speed": ModeSection(
                name="speed",
                enable_planning=False,
                enable_cross_verification=False,
                enable_acquisition=False,
                enable_recursive_repair=False,
                emit_research_packet=False,
                max_branch_depth=1,
                max_plan_count=1,
                max_queries=3,
                page_fetch_limit=0,
                prefer_acquired_text=False,
                rerank_profile="lexical",
                branch_budget_per_round={
                    "breadth": 1,
                    "repair": 1,
                    "followup": 0,
                    "probe": 0,
                    "research": 0,
                },
                plateau_rounds=1,
                stop_on_saturated=True,
                max_findings_before_search_disable=18,
                disabled_actions=["cross_verify"],
            ),
            "balanced": ModeSection(),
            "deep": ModeSection(
                name="deep",
                max_branch_depth=5,
                max_plan_count=5,
                max_queries=7,
                page_fetch_limit=4,
                prefer_acquired_text=True,
                branch_budget_per_round={
                    "breadth": 1,
                    "repair": 3,
                    "followup": 2,
                    "probe": 2,
                    "research": 2,
                },
                plateau_rounds=4,
                max_findings_before_search_disable=80,
            ),
        }
    )
    scoring: ScoringSection = field(default_factory=ScoringSection)
    platform_routing: PlatformRoutingSection = field(
        default_factory=PlatformRoutingSection,
    )
    thresholds: ThresholdsSection = field(default_factory=ThresholdsSection)
    synthesis: SynthesisSection = field(default_factory=SynthesisSection)
    query_generation: QueryGenerationSection = field(
        default_factory=QueryGenerationSection,
    )
    phases: list[PhaseSpec] = field(default_factory=list)

    # -- Factory -----------------------------------------------------------

    @classmethod
    def default(cls) -> GenomeSchema:
        return cls()

    # -- Serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomeSchema:
        def _section(klass: type, raw: Any) -> Any:
            if isinstance(raw, dict):
                known = {f.name for f in klass.__dataclass_fields__.values()}
                unknown = set(raw) - known
                if unknown:
                    logger.warning(
                        "Genome %s: dropping unknown keys %s",
                        klass.__name__,
                        sorted(unknown),
                    )
                return klass(**{k: v for k, v in raw.items() if k in known})
            return klass()

        modes_raw = data.get("modes") or {}
        modes = {
            name: _section(ModeSection, mode_data)
            for name, mode_data in modes_raw.items()
        }

        phases_raw = data.get("phases") or []
        phases = [_section(PhaseSpec, p) for p in phases_raw]

        return cls(
            version=str(data.get("version", "1.0")),
            genome_id=str(data.get("genome_id", "")),
            parent_id=str(data.get("parent_id", "")),
            engine=_section(EngineSection, data.get("engine")),
            orchestrator=_section(OrchestratorSection, data.get("orchestrator")),
            modes=modes,
            scoring=_section(ScoringSection, data.get("scoring")),
            platform_routing=_section(
                PlatformRoutingSection, data.get("platform_routing")
            ),
            thresholds=_section(ThresholdsSection, data.get("thresholds")),
            synthesis=_section(SynthesisSection, data.get("synthesis")),
            query_generation=_section(
                QueryGenerationSection, data.get("query_generation")
            ),
            phases=phases,
        )

    # -- JSON Schema export ------------------------------------------------

    @classmethod
    def json_schema(cls) -> dict[str, Any]:
        """Export a JSON Schema describing the genome structure."""

        def _type_for(annotation: Any) -> dict[str, Any]:
            if annotation is int:
                return {"type": "integer"}
            if annotation is float:
                return {"type": "number"}
            if annotation is str:
                return {"type": "string"}
            if annotation is bool:
                return {"type": "boolean"}
            origin = getattr(annotation, "__origin__", None)
            if origin is list:
                return {"type": "array"}
            if origin is dict:
                return {"type": "object"}
            return {"type": "object"}

        _STR_TYPE_MAP = {
            "int": {"type": "integer"},
            "float": {"type": "number"},
            "str": {"type": "string"},
            "bool": {"type": "boolean"},
        }

        def _resolve_annotation(ann: str) -> dict[str, Any]:
            # Strip Optional / union-with-None: "str | None" → "str"
            cleaned = ann.replace(" ", "")
            if "|None" in cleaned or "None|" in cleaned:
                parts = [p.strip() for p in ann.split("|") if p.strip() != "None"]
                if len(parts) == 1:
                    return _resolve_annotation(parts[0])
            if ann in _STR_TYPE_MAP:
                return _STR_TYPE_MAP[ann]
            if "list" in ann.lower():
                return {"type": "array"}
            if "dict" in ann.lower():
                return {"type": "object"}
            return {"type": "object"}

        def _schema_for(klass: type) -> dict[str, Any]:
            props: dict[str, Any] = {}
            for name, fld in klass.__dataclass_fields__.items():
                props[name] = _resolve_annotation(str(fld.type))
            return {"type": "object", "properties": props}

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "AutoSearch Genome",
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "genome_id": {"type": "string"},
                "parent_id": {"type": "string"},
                "engine": _schema_for(EngineSection),
                "orchestrator": _schema_for(OrchestratorSection),
                "modes": {
                    "type": "object",
                    "additionalProperties": _schema_for(ModeSection),
                },
                "scoring": _schema_for(ScoringSection),
                "platform_routing": _schema_for(PlatformRoutingSection),
                "thresholds": _schema_for(ThresholdsSection),
                "synthesis": _schema_for(SynthesisSection),
                "query_generation": _schema_for(QueryGenerationSection),
                "phases": {
                    "type": "array",
                    "items": _schema_for(PhaseSpec),
                },
            },
        }
