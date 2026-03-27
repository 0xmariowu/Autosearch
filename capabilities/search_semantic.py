"""Semantic web search using Exa and Tavily (premium providers)."""

name = "search_semantic"
description = "Semantic search using Exa (neural search) and Tavily (AI-optimized). Higher quality but costs API credits. Use as premium fallback when free search isn't finding good results."
when = "When free search providers return low-quality results, or when you need semantic (meaning-based) rather than keyword search."
input_type = "query"
output_type = "hits"

input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query text"},
        "context": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results to return", "default": 20},
                "query_family": {"type": "string", "description": "Query family label", "default": "unknown"},
            },
        },
    },
    "required": ["input"],
}


def run(query, **context):
    from search_mesh.router import search_platform
    limit = context.get("limit", 20)
    query_family = context.get("query_family", "unknown")
    providers = [{"name": "exa"}, {"name": "tavily"}]

    all_hits = []
    for p in providers:
        try:
            batch = search_platform(p, str(query), query_family=query_family)
            all_hits.extend(batch.to_hit_dicts())
        except Exception:
            continue
    return all_hits[:limit]


def health_check():
    import os
    checks = {}
    # Check Exa via mcporter
    import shutil
    if shutil.which("mcporter"):
        checks["exa"] = "ok"
    else:
        checks["exa"] = "off"
    # Check Tavily
    if os.environ.get("TAVILY_API_KEY"):
        checks["tavily"] = "ok"
    else:
        checks["tavily"] = "off"
    if any(v == "ok" for v in checks.values()):
        return {"status": "ok", "message": f"exa={checks.get('exa','off')}, tavily={checks.get('tavily','off')}"}
    return {"status": "off", "message": "No premium providers available"}


def test():
    from search_mesh.router import search_platform  # noqa: F401
    return "ok"
