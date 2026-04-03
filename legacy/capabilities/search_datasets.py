"""Search Hugging Face datasets."""

name = "search_datasets"
description = "Search Hugging Face for datasets by topic. Returns dataset names, descriptions, download counts, and tags."
when = "When looking for ML/AI datasets, training data, or benchmark datasets."
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

    try:
        batch = search_platform(
            {"name": "huggingface_datasets"}, str(query), query_family=query_family
        )
        return batch.to_hit_dicts()[:limit]
    except Exception:
        return []


def test():
    from search_mesh.router import search_platform  # noqa: F401

    return "ok"
