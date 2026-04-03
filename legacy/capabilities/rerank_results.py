"""Rerank search hits by relevance to query."""

from search_mesh.models import SearchHit

name = "rerank_results"
description = "Rerank search hits using hybrid lexical + provider scoring for better relevance ordering."
when = "When you have raw search hits and need to reorder them by relevance before presenting or judging."
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
    from rerank import rerank_hits

    items = [input] if isinstance(input, dict) else list(input or [])
    items = [d for d in items if isinstance(d, dict)]
    if not items:
        return []
    query = context.get("query", "")
    profile = context.get("profile", "hybrid")
    hits = [_dict_to_hit(d) for d in items]
    ranked = rerank_hits(query, hits, rerank_profile=profile)
    return [_hit_to_dict(h) for h in ranked]


def test():
    from rerank import rerank_hits  # noqa: F401

    return "ok"
