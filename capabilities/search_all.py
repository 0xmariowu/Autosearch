"""Search all available providers concurrently for maximum coverage."""

name = "search_all"
description = "Search ALL available providers in one call: GitHub repos+issues, web (SearXNG+DuckDuckGo), social (Reddit+HN), and more. Returns combined results from all providers. Maximum coverage per step."
when = "When you want the widest possible results in a single step. Preferred over calling individual search capabilities one at a time."
input_type = "query"
output_type = "hits"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query"},
        "context": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 150, "description": "Max results to return"},
                "query_family": {"type": "string", "default": "unknown"},
            },
        },
    },
    "required": ["input"],
}


def run(query, **context):
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from search_mesh.router import search_platform

    limit = context.get("limit", 150)
    query_family = context.get("query_family", "unknown")

    providers = [
        {"name": "github_repos"},
        {"name": "github_issues"},
        {"name": "searxng"},
        {"name": "ddgs"},
        {"name": "reddit", "sub": "all"},
        {"name": "hn"},
    ]

    # Try to add premium providers if available
    try:
        from source_capability import refresh_source_capability
        report = refresh_source_capability()
        sources = report.get("sources", {})
        if sources.get("exa", {}).get("available"):
            providers.append({"name": "exa"})
        if sources.get("tavily", {}).get("available"):
            providers.append({"name": "tavily"})
        if sources.get("twitter_xreach", {}).get("available"):
            providers.append({"name": "twitter_xreach"})
        if sources.get("huggingface_datasets", {}).get("available"):
            providers.append({"name": "huggingface_datasets"})
    except Exception:
        pass

    all_hits = []

    def _search_one(platform):
        try:
            batch = search_platform(platform, str(query), query_family=query_family)
            return batch.to_hit_dicts()
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=min(len(providers), 6)) as pool:
        futures = {pool.submit(_search_one, p): p for p in providers}
        for future in as_completed(futures, timeout=25):
            try:
                hits = future.result()
                all_hits.extend(hits)
            except Exception:
                continue

    # URL dedup before returning
    seen = set()
    unique = []
    for h in all_hits:
        if not isinstance(h, dict):
            continue
        url = str(h.get("url", "")).strip()
        if url and url not in seen:
            seen.add(url)
            unique.append(h)
        elif not url:
            unique.append(h)  # Keep hits without URL

    return unique[:limit]


def test():
    from search_mesh.router import search_platform  # noqa: F401
    from concurrent.futures import ThreadPoolExecutor  # noqa: F401
    return "ok"
