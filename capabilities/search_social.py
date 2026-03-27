"""Search social platforms: Reddit, Hacker News, Twitter/X."""

name = "search_social"
description = "Search community discussions on Reddit, Hacker News, and Twitter/X. Returns posts, comments, and threads with engagement scores."
when = "When looking for community opinions, discussions, real-world experiences, or trending topics."
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
    platforms = context.get("platforms", ["reddit", "hn", "twitter_xreach"])

    all_hits = []
    for name_str in platforms:
        try:
            batch = search_platform({"name": name_str}, str(query), query_family=query_family)
            all_hits.extend(batch.to_hit_dicts())
        except Exception:
            continue
    return all_hits[:limit]


def test():
    from search_mesh.router import search_platform  # noqa: F401
    return "ok"
