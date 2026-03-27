"""Boost score for URLs seen by multiple search providers."""

name = "consensus_score"
description = "Boost score for URLs found by multiple search providers. A URL seen by 3 providers is more trustworthy than one from 1 provider. Adds consensus_count and providers fields."
when = "After collecting hits from multiple search providers, before final ranking."
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


def run(hits, **context):
    if not hits or not isinstance(hits, list):
        return hits if isinstance(hits, list) else []
    hits = [h for h in hits if isinstance(h, dict)]
    if not hits:
        return []
    from collections import defaultdict

    # Track which providers found each URL
    url_providers = defaultdict(set)
    for hit in hits:
        url = str(hit.get("url") or "").strip()
        provider = str(hit.get("provider") or hit.get("source") or "unknown").strip()
        if url:
            url_providers[url].add(provider)

    # Boost scores
    for hit in hits:
        url = str(hit.get("url") or "").strip()
        providers = url_providers.get(url, set())
        hit["consensus_count"] = len(providers)
        hit["providers"] = sorted(providers)
        # Multiply score_hint by consensus count (SearXNG pattern: weight *= len(positions))
        original_score = int(hit.get("score_hint", 0) or 0)
        hit["score_hint"] = original_score * max(1, len(providers))

    return hits


def test():
    sample = [
        {"url": "https://a.com", "score_hint": 10, "provider": "ddgs", "title": "A"},
        {"url": "https://a.com", "score_hint": 15, "provider": "searxng", "title": "A"},
        {"url": "https://b.com", "score_hint": 20, "provider": "ddgs", "title": "B"},
    ]
    result = run(sample)
    assert result[0]["consensus_count"] == 2, (
        f"Expected 2, got {result[0]['consensus_count']}"
    )
    assert result[0]["score_hint"] == 20, f"Expected 20, got {result[0]['score_hint']}"
    assert result[2]["consensus_count"] == 1
    assert result[2]["score_hint"] == 20
    return "ok"
