"""Deduplicate search hits by normalized URL."""

from search_mesh.models import SearchHit

name = "dedup_results"
description = "Remove duplicate hits by normalized URL and optionally cap results per domain."
when = "When you have search hits that may contain duplicates from multiple providers."
input_type = "hits"
output_type = "hits"

input_schema = {
    "type": "object",
    "properties": {
        "input": {
            "type": "array",
            "items": {"type": "object"},
            "description": "List of hit dicts with url, title, snippet, provider fields",
        },
        "context": {"type": "object"},
    },
    "required": ["input"],
}


def _dict_to_hit(d):
    return SearchHit.from_mapping(
        d,
        provider=str(d.get("provider") or d.get("source") or "unknown"),
        query=str(d.get("query") or ""),
        rank=int(d.get("rank") or 0),
        backend=str(d.get("backend") or ""),
        query_family=str(d.get("query_family") or "unknown"),
    )


def _hit_to_dict(hit):
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


def run(input, **context):
    from rerank.lexical import dedup_hits

    items = [input] if isinstance(input, dict) else list(input or [])
    items = [d for d in items if isinstance(d, dict)]
    if not items:
        return []
    max_per_domain = context.get("max_per_domain", 5)
    hits = [_dict_to_hit(d) for d in items]
    deduped = dedup_hits(hits, max_per_domain=max_per_domain)
    return [_hit_to_dict(h) for h in deduped]


def test():
    from rerank.lexical import dedup_hits

    hit_a = SearchHit.from_fields(
        url="https://example.com/page",
        title="Page A",
        snippet="content",
        source="test",
        provider="test",
        query="q",
        rank=1,
    )
    hit_b = SearchHit.from_fields(
        url="https://example.com/page",
        title="Page A",
        snippet="content",
        source="test",
        provider="test",
        query="q",
        rank=2,
    )
    result = dedup_hits([hit_a, hit_b])
    assert len(result) == 1
    return "ok"
