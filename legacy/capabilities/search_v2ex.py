"""Search V2EX tech community via DuckDuckGo site filter."""

name = "search_v2ex"
description = (
    "Search V2EX Chinese tech community for discussions, experiences, and opinions"
)
when = "When looking for Chinese tech community discussions, developer experiences, or opinions on tools."
input_type = "query"
output_type = "hits"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query"},
    },
    "required": ["input"],
}


def run(query, **context):
    from search_mesh.router import search_platform

    site_query = f"site:v2ex.com {query}"
    limit = context.get("limit", 20)
    try:
        batch = search_platform({"name": "ddgs"}, site_query, query_family="social")
        return batch.to_hit_dicts()[:limit]
    except Exception:
        return []


def test():
    from search_mesh.router import search_platform  # noqa: F401

    return "ok"
