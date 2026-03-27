"""Merge duplicate URLs instead of discarding them."""

name = "content_merge"
description = "When the same URL appears multiple times (from different queries or providers), merge their content instead of discarding duplicates. Keeps longest title, concatenates unique snippets, collects all providers."
when = "After collecting hits from multiple sources, before or instead of simple dedup."
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

    # Group by normalized URL
    url_groups = {}
    order = []
    for hit in hits:
        url = str(hit.get("url") or "").strip().rstrip("/").lower()
        if not url:
            order.append(hit)
            continue
        if url not in url_groups:
            url_groups[url] = []
            order.append(url)
        url_groups[url].append(hit)

    # Merge each group
    merged = []
    for item in order:
        if isinstance(item, dict):
            merged.append(item)  # hits without URL pass through
            continue
        group = url_groups[item]
        if len(group) == 1:
            merged.append(group[0])
            continue

        # Pick longest title
        best_title = max((h.get("title") or "" for h in group), key=len)
        # Concatenate unique snippets
        seen_snippets = set()
        snippet_parts = []
        for h in group:
            s = str(h.get("snippet") or h.get("body") or "").strip()
            if s and s not in seen_snippets:
                seen_snippets.add(s)
                snippet_parts.append(s)
        # Collect all providers
        all_providers = sorted(
            {str(h.get("provider") or "") for h in group if h.get("provider")}
        )

        # Use first hit as base, update fields
        base = dict(group[0])
        base["title"] = best_title
        base["snippet"] = " | ".join(snippet_parts)
        if "body" in base:
            base["body"] = " | ".join(snippet_parts)
        base["providers"] = all_providers
        base["merge_count"] = len(group)
        merged.append(base)

    return merged


def test():
    sample = [
        {
            "url": "https://A.com/",
            "title": "Short",
            "snippet": "First snippet",
            "provider": "ddgs",
        },
        {
            "url": "https://a.com",
            "title": "Longer Title Here",
            "snippet": "Second snippet",
            "provider": "searxng",
        },
        {
            "url": "https://a.com",
            "title": "A",
            "snippet": "First snippet",
            "provider": "exa",
        },  # duplicate snippet
        {
            "url": "https://b.com",
            "title": "B",
            "snippet": "Only one",
            "provider": "ddgs",
        },
    ]
    result = run(sample)
    assert len(result) == 2, f"Expected 2, got {len(result)}"
    assert result[0]["title"] == "Longer Title Here"
    assert result[0]["merge_count"] == 3
    assert "First snippet" in result[0]["snippet"]
    assert "Second snippet" in result[0]["snippet"]
    return "ok"
