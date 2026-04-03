"""Primitive registry for thin, strategy-free AutoSearch AVO wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Callable


@dataclass
class PrimitiveSpec:
    name: str
    input_schema: dict[str, Any]
    output_type: str
    fn: Callable[..., Any]


_REGISTRY: dict[str, PrimitiveSpec] = {}

_DEFAULT_ENGAGEMENT_FORMULAS = {
    "reddit": "0.50*log1p(score) + 0.35*log1p(comments) + 0.15*log1p(awards)",
    "github": "0.40*log1p(stars) + 0.35*log1p(forks) + 0.25*log1p(watchers)",
    "hn": "0.60*log1p(score) + 0.40*log1p(comments)",
}

_ENTITY_PATTERNS = (
    re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,32}"),
    re.compile(r"(?<!\w)r/[A-Za-z0-9_]{2,32}"),
    # Multi-word proper nouns (2+ capitalized words): "OpenAI GPT-5", "Hugging Face"
    re.compile(r"\b[A-Z][A-Za-z0-9+.-]+(?:\s+[A-Z][A-Za-z0-9+.-]+){1,3}\b"),
    # Single-word product names with tech suffixes
    re.compile(r"\b[A-Z][A-Za-z0-9]*(?:\.js|\.py|\.ai|AI|OS|DB|ML|IO)\b"),
)

_INTENT_PATTERNS = (
    ("how_to", re.compile(r"(?i)\b(how\s+to|setup|install|configure|deploy)\b")),
    ("comparison", re.compile(r"(?i)\b(vs\.?|versus|compared?\s+to|alternative)\b")),
    ("opinion", re.compile(r"(?i)\b(best|worst|review|recommend|should\s+i)\b")),
    ("debug", re.compile(r"(?i)\b(error|bug|fix|crash|traceback|exception|fail)\b")),
    ("breaking", re.compile(r"(?i)\b(new|launch|announce|release|breaking)\b")),
    ("research", re.compile(r"(?i)\b(paper|study|survey|benchmark|evaluation)\b")),
    ("prediction", re.compile(r"(?i)\b(future|predict|trend|forecast|roadmap)\b")),
)


def register_primitive(
    name: str,
    input_schema: dict[str, Any],
    output_type: str,
    fn: Callable[..., Any],
) -> PrimitiveSpec:
    spec = PrimitiveSpec(
        name=str(name).strip(),
        input_schema=dict(input_schema or {}),
        output_type=str(output_type or "").strip(),
        fn=fn,
    )
    if not spec.name:
        raise ValueError("Primitive name is required")
    _REGISTRY[spec.name] = spec
    return spec


def call_primitive(name: str, inputs: dict[str, Any]) -> Any:
    spec = _REGISTRY.get(str(name).strip())
    if spec is None:
        raise KeyError(f"Unknown primitive: {name}")
    if not isinstance(inputs, dict):
        raise TypeError("Primitive inputs must be a dict")
    required = list(spec.input_schema.get("required") or [])
    missing = [key for key in required if key not in inputs]
    if missing:
        raise ValueError(
            f"Missing required inputs for {spec.name}: {', '.join(missing)}"
        )
    return spec.fn(**inputs)


def list_primitives() -> list[str]:
    return sorted(_REGISTRY)


def _coerce_platform(
    platform: str | dict[str, Any], limit: int | None
) -> dict[str, Any]:
    payload = {"name": platform} if isinstance(platform, str) else dict(platform or {})
    if limit is not None:
        payload.setdefault("limit", int(limit))
        payload.setdefault("max_results", int(limit))
    return payload


def _coerce_hit(payload: dict[str, Any], query: str = "") -> Any:
    from search_mesh.models import SearchHit

    return SearchHit.from_mapping(
        dict(payload or {}),
        provider=str(payload.get("provider") or payload.get("source") or "unknown"),
        query=str(payload.get("query") or query or ""),
        rank=int(payload.get("rank") or 0),
        backend=str(payload.get("backend") or ""),
        query_family=str(payload.get("query_family") or "unknown"),
    )


def _hit_to_dict(hit: Any) -> dict[str, Any]:
    return {
        "hit_id": hit.hit_id,
        "url": hit.url,
        "title": hit.title,
        "snippet": hit.snippet,
        "source": hit.source,
        "provider": hit.provider,
        "query": hit.query,
        "query_family": hit.query_family,
        "backend": hit.backend,
        "rank": hit.rank,
        "score_hint": hit.score_hint,
    }


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item.lower() in seen:
            continue
        seen.add(item.lower())
        ordered.append(item)
    return ordered


def _filter_records(
    records: list[dict[str, Any]], filters: dict[str, Any]
) -> list[dict[str, Any]]:
    if not filters:
        return records
    matched: list[dict[str, Any]] = []
    for record in records:
        keep = True
        for key, expected in filters.items():
            actual = record.get(key)
            if isinstance(expected, list):
                keep = actual in expected
            else:
                keep = str(actual or "") == str(expected or "")
            if not keep:
                break
        if keep:
            matched.append(record)
    return matched


def _mutation_query_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    from research.planner import _decomposition_followups, _follow_up_queries

    mode = str(
        config.get("mutation_mode")
        or config.get("mutation_kind")
        or config.get("role")
        or ""
    ).lower()
    common = {
        "goal_case": dict(config.get("goal_case") or {}),
        "local_evidence_records": list(config.get("local_evidence_records") or []),
        "judge_result": dict(config.get("judge_result") or {}),
        "max_queries": int(
            config.get("limit", config.get("queries_per_round", 5)) or 5
        ),
        "tried_queries": set(
            str(item) for item in list(config.get("tried_queries") or [])
        ),
        "generic_tokens": config.get("generic_anchor_tokens"),
    }
    if not common["judge_result"] and not common["local_evidence_records"]:
        return []
    if "decomposition" in mode or "probe" in mode:
        return _decomposition_followups(**common)
    return _follow_up_queries(**common)


def _primitive_search(
    query: str,
    platform: str | dict[str, Any],
    limit: int = 10,
) -> list[dict[str, Any]]:
    from search_mesh.router import search_platform

    batch = search_platform(
        _coerce_platform(platform, limit),
        str(query or ""),
        context={"limit": int(limit or 10)},
    )
    return batch.to_hit_dicts()[: max(int(limit or 10), 0)]


def _primitive_fetch(url: str) -> dict[str, Any]:
    from capabilities.crawl_page import run as crawl_page
    from capabilities.follow_links import run as follow_links

    document = next(iter(crawl_page(str(url or "").strip()) or []), {}) or {}
    references = follow_links(document) if document else []
    return {
        "url": document.get("final_url") or document.get("url") or str(url or ""),
        "title": document.get("title") or "",
        "clean_markdown": document.get("markdown") or document.get("text") or "",
        "references": references,
        "error": document.get("error") or "",
    }


def _primitive_score(
    hits: list[dict[str, Any]],
    query: str,
    scoring_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    from rerank.lexical import lexical_score

    preferred = dict(scoring_config or {}).get("preferred_content_types")
    scored: list[dict[str, Any]] = []
    for item in [dict(hit) for hit in list(hits or []) if isinstance(hit, dict)]:
        item["score_hint"] = lexical_score(
            str(query or ""),
            _coerce_hit(item, query),
            preferred_content_types=preferred,
            scoring_config=scoring_config,
        )
        scored.append(item)
    return scored


def _primitive_dedup(
    hits: list[dict[str, Any]],
    threshold: float = 0.85,
    max_per_domain: int | None = None,
) -> list[dict[str, Any]]:
    from capabilities.dedup_results import run as dedup_results
    from rerank.lexical import dedup_hits

    _ = threshold
    deduped = dedup_results(
        [dict(hit) for hit in list(hits or []) if isinstance(hit, dict)],
        max_per_domain=max_per_domain,
    )
    normalized = dedup_hits(
        [_coerce_hit(item) for item in deduped],
        max_per_domain=max_per_domain,
    )
    return [_hit_to_dict(hit) for hit in normalized]


def _primitive_extract_entities(texts: str | list[str]) -> list[str]:
    values = [texts] if isinstance(texts, str) else list(texts or [])
    matches = [
        match.group(0).strip(" \t\n\r.,:;()[]{}")
        for text in values
        for pattern in _ENTITY_PATTERNS
        for match in pattern.finditer(str(text or ""))
    ]
    return _ordered_unique(matches)


def _primitive_cross_ref(
    hits: list[dict[str, Any]],
    jaccard_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    from capabilities.consensus_score import run as consensus_score
    from capabilities.cross_verify import run as cross_verify

    boosted = consensus_score(
        [dict(hit) for hit in list(hits or []) if isinstance(hit, dict)]
    )
    report = cross_verify(boosted, jaccard_threshold=jaccard_threshold)
    disputes = dict(report.get("source_dispute_map") or {})
    consensus = list(report.get("consensus") or [])
    contradictions = list(report.get("contradictions") or [])
    result: list[dict[str, Any]] = []
    for hit in boosted:
        source = str(hit.get("source") or hit.get("provider") or "")
        url = str(hit.get("url") or "")

        def related(item: dict) -> bool:
            return url in list(item.get("urls") or []) or source in list(
                item.get("sources") or []
            )

        result.append(
            {
                **hit,
                "cross_refs": {
                    "consensus": [item for item in consensus if related(item)][:5],
                    "contradictions": [
                        item for item in contradictions if related(item)
                    ][:5],
                    "source_summary": dict(disputes.get(source) or {}),
                    "stance_counts": dict(report.get("stance_counts") or {}),
                },
            }
        )
    return result


def _primitive_classify_intent(query: str) -> str:
    text = str(query or "")
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text):
            return intent
    return "research"


def _primitive_synthesize(
    evidence: list[dict[str, Any]],
    synthesis_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from research.synthesizer import _align_claims

    return _align_claims(
        [dict(item) for item in list(evidence or []) if isinstance(item, dict)],
        synthesis_config=synthesis_config,
    )


def _primitive_report(
    evidence: list[dict[str, Any]],
    template: str | None = None,
) -> dict[str, Any]:
    from capabilities.generate_report import run as generate_report

    report = generate_report(
        [dict(item) for item in list(evidence or []) if isinstance(item, dict)],
        template=template,
    )
    if template and isinstance(report, dict) and "template" not in report:
        report = {**report, "template": template}
    return report


def _primitive_store(
    records: list[dict[str, Any]] | None = None,
    filters: dict[str, Any] | None = None,
    index_path: str | None = None,
) -> int | list[dict[str, Any]]:
    from evidence_index.index import LocalEvidenceIndex
    from evidence_index.query import search_evidence

    index = LocalEvidenceIndex(Path(index_path or ".autosearch-evidence.jsonl"))
    if records is not None:
        items = [dict(item) for item in list(records or []) if isinstance(item, dict)]
        return index.add(items)
    if filters is None:
        raise ValueError("store requires either records or filters")
    criteria = dict(filters or {})
    query = str(criteria.pop("query", "") or "").strip()
    limit = int(criteria.pop("limit", 10) or 10)
    loaded = index.load_all()
    matched = search_evidence(loaded, query, limit=limit) if query else loaded[:limit]
    return _filter_records(matched, criteria)


def _primitive_generate_queries(
    task: str,
    genes: dict[str, list[str]],
    config: dict[str, Any] | None = None,
) -> list[str]:
    from engine import EngineConfig, PatternStore, QueryGenerator

    cfg = dict(config or {})
    limit = int(cfg.get("limit", cfg.get("queries_per_round", 5)) or 5)
    patterns = PatternStore(
        Path(cfg.get("patterns_path") or "/tmp/autosearch-primitives-patterns.jsonl")
    )
    patterns.use_patterns = list(cfg.get("patterns") or patterns.use_patterns)
    generator = QueryGenerator(
        EngineConfig(
            genes=dict(genes or {}),
            queries_per_round=limit,
            llm_ratio=float(cfg.get("llm_ratio", 0.0) or 0.0),
            pattern_ratio=float(cfg.get("pattern_ratio", 0.0) or 0.0),
            gene_ratio=float(cfg.get("gene_ratio", 1.0) or 1.0),
        ),
        patterns,
    )
    generator.add_seed_queries(
        _ordered_unique([str(task or ""), *list(cfg.get("seed_queries") or [])])
    )
    generator.add_llm_suggestions(
        _ordered_unique(list(cfg.get("llm_suggestions") or []))
    )
    base_queries, _ = generator.generate(limit)
    mutation_queries = [spec.get("text", "") for spec in _mutation_query_specs(cfg)]
    return _ordered_unique([str(task or ""), *base_queries, *mutation_queries])[:limit]


def _primitive_evaluate_engagement(
    metrics: dict[str, Any],
    platform: str,
    formulas: dict[str, str] | None = None,
) -> float:
    from genome.safe_eval import SafeEvalError, safe_eval

    formula = dict(formulas or _DEFAULT_ENGAGEMENT_FORMULAS).get(
        str(platform or "").lower(), ""
    )
    if not formula:
        return 0.0
    try:
        return safe_eval(formula, dict(metrics or {}))
    except SafeEvalError:
        return 0.0


def _primitive_score_consensus(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from capabilities.consensus_score import run as consensus_score

    return consensus_score(
        [dict(hit) for hit in list(hits or []) if isinstance(hit, dict)]
    )


register_primitive(
    "search",
    {
        "type": "object",
        "properties": {"query": {}, "platform": {}, "limit": {"type": "integer"}},
        "required": ["query", "platform"],
    },
    "hits",
    _primitive_search,
)
register_primitive(
    "fetch",
    {
        "type": "object",
        "properties": {"url": {"type": "string"}},
        "required": ["url"],
    },
    "document",
    _primitive_fetch,
)
register_primitive(
    "score",
    {
        "type": "object",
        "properties": {"hits": {}, "query": {}, "scoring_config": {}},
        "required": ["hits", "query"],
    },
    "hits",
    _primitive_score,
)
register_primitive(
    "dedup",
    {
        "type": "object",
        "properties": {"hits": {}, "threshold": {}, "max_per_domain": {}},
        "required": ["hits"],
    },
    "hits",
    _primitive_dedup,
)
register_primitive(
    "extract_entities",
    {
        "type": "object",
        "properties": {"texts": {}},
        "required": ["texts"],
    },
    "entities",
    _primitive_extract_entities,
)
register_primitive(
    "cross_ref",
    {
        "type": "object",
        "properties": {"hits": {}, "jaccard_threshold": {}},
        "required": ["hits"],
    },
    "hits",
    _primitive_cross_ref,
)
register_primitive(
    "classify_intent",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    "label",
    _primitive_classify_intent,
)
register_primitive(
    "synthesize",
    {
        "type": "object",
        "properties": {"evidence": {}, "synthesis_config": {}},
        "required": ["evidence"],
    },
    "claim_alignment",
    _primitive_synthesize,
)
register_primitive(
    "report",
    {
        "type": "object",
        "properties": {"evidence": {}, "template": {}},
        "required": ["evidence"],
    },
    "report",
    _primitive_report,
)
register_primitive(
    "store",
    {
        "type": "object",
        "properties": {"records": {}, "filters": {}, "index_path": {}},
    },
    "count|records",
    _primitive_store,
)
register_primitive(
    "generate_queries",
    {
        "type": "object",
        "properties": {"task": {}, "genes": {}, "config": {}},
        "required": ["task", "genes"],
    },
    "queries",
    _primitive_generate_queries,
)
register_primitive(
    "evaluate_engagement",
    {
        "type": "object",
        "properties": {"metrics": {}, "platform": {}, "formulas": {}},
        "required": ["metrics", "platform"],
    },
    "score",
    _primitive_evaluate_engagement,
)
register_primitive(
    "score_consensus",
    {
        "type": "object",
        "properties": {"hits": {}},
        "required": ["hits"],
    },
    "hits",
    _primitive_score_consensus,
)


__all__ = [
    "PrimitiveSpec",
    "call_primitive",
    "list_primitives",
    "register_primitive",
]
