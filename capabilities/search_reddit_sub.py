"""Search specific Reddit subreddits."""

name = "search_reddit_sub"
description = "Search a specific Reddit subreddit for discussions. Useful for targeted community research."
when = "When you want discussions from a specific subreddit like r/MachineLearning, r/LocalLLaMA, etc."
input_type = "query"
output_type = "hits"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query"},
        "context": {
            "type": "object",
            "properties": {
                "subreddit": {"type": "string", "default": "MachineLearning"},
            },
        },
    },
    "required": ["input"],
}

def run(query, **context):
    from search_mesh.router import search_platform
    sub = context.get("subreddit", "MachineLearning")
    try:
        batch = search_platform({"name": "reddit", "sub": sub}, str(query), query_family="social")
        return batch.to_hit_dicts()[:context.get("limit", 20)]
    except Exception:
        return []

def test():
    from search_mesh.router import search_platform  # noqa: F401
    return "ok"
