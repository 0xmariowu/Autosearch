"""Broad web search using all available providers for maximum coverage."""

name = "search_web_broad"
description = "Search the web using ALL available providers simultaneously (SearXNG + DuckDuckGo + Exa + Tavily). Use when you need maximum coverage and are willing to use premium API credits."
when = "When you need the widest possible coverage. More expensive than search_web which only uses free providers."
input_type = "query"
output_type = "hits"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query"},
        "context": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    "required": ["input"],
}


def run(query, **context):
    from search_mesh.router import search_platform

    limit = context.get("limit", 50)
    providers = ["searxng", "ddgs", "exa", "tavily"]

    all_hits = []
    for name_str in providers:
        try:
            batch = search_platform(
                {"name": name_str}, str(query), query_family="broad"
            )
            all_hits.extend(batch.to_hit_dicts())
        except Exception:
            continue
    return all_hits[:limit]


def test():
    from search_mesh.router import search_platform  # noqa: F401

    return "ok"
