"""Broad web search using free default providers."""

name = "search_web"
description = "Search the open web using SearXNG and DuckDuckGo. Returns diverse web results including articles, blog posts, documentation, and tutorials."
when = "When you need general web results for a topic. For code use search_github, for discussions use search_social."
input_type = "query"
output_type = "hits"

input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query text"},
        "context": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 20,
                },
                "query_family": {
                    "type": "string",
                    "description": "Query family label",
                    "default": "unknown",
                },
            },
        },
    },
    "required": ["input"],
}


def run(query, **context):
    from search_mesh.router import search_platform

    limit = context.get("limit", 20)
    query_family = context.get("query_family", "unknown")
    providers = [{"name": "searxng"}, {"name": "ddgs"}]
    all_hits = []
    for p in providers:
        try:
            batch = search_platform(p, str(query), query_family=query_family)
            all_hits.extend(batch.to_hit_dicts())
        except Exception:
            continue
    return all_hits[:limit]


def test():
    from search_mesh.router import search_platform  # noqa: F401

    return "ok"
