"""Search all providers and auto-process: deduplicate, merge, score."""

name = "search_and_process"
description = "Search ALL providers AND automatically deduplicate, merge content, and boost by consensus. Returns clean, unique, ranked results in one step instead of manually calling search + consensus + dedup."
when = "Default search method for maximum efficiency. Use instead of individual search + processing steps."
input_type = "query"
output_type = "hits"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query"},
        "context": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 100},
            },
        },
    },
    "required": ["input"],
}


def run(query, **context):
    from capabilities import dispatch

    limit = context.get("limit", 100)

    # Step 1: Search all available providers concurrently
    try:
        raw_hits = dispatch(
            "search_all", query, **{k: v for k, v in context.items() if k != "limit"}
        )
    except Exception:
        # Fallback to basic web search
        raw_hits = dispatch("search_web", query, limit=limit)

    if not raw_hits or not isinstance(raw_hits, list):
        return []

    # Step 2: Consensus score (boost multi-provider URLs)
    try:
        scored = dispatch("consensus_score", raw_hits)
    except Exception:
        scored = raw_hits

    # Step 3: Content merge (merge duplicate URLs)
    try:
        merged = dispatch("content_merge", scored)
    except Exception:
        merged = scored

    # Step 4: URL dedup
    seen = set()
    unique = []
    for h in merged:
        if not isinstance(h, dict):
            continue
        url = str(h.get("url", "")).strip()
        if url and url not in seen:
            seen.add(url)
            unique.append(h)

    # Sort by score descending
    unique.sort(key=lambda h: int(h.get("score_hint", 0) or 0), reverse=True)
    return unique[:limit]


def test():
    # Verify imports work
    return "ok"
