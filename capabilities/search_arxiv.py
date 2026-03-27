"""Search academic papers on arXiv."""

name = "search_arxiv"
description = "Search arXiv for academic papers and preprints. Uses Exa semantic search with site:arxiv.org filter for high-quality paper discovery."
when = "When looking for academic papers, research publications, or scientific preprints."
input_type = "query"
output_type = "hits"
input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Academic search query"},
        "context": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    "required": ["input"],
}


def run(query, **context):
    from search_mesh.router import search_platform
    limit = context.get("limit", 10)
    query_str = f"site:arxiv.org {query}" if "arxiv" not in str(query).lower() else str(query)

    # Try exa first (semantic search)
    try:
        batch = search_platform({"name": "exa"}, query_str, query_family="academic")
        hits = batch.to_hit_dicts()
        if hits:
            return hits[:limit]
    except Exception:
        pass

    # Fallback to ddgs
    try:
        batch = search_platform({"name": "ddgs"}, query_str, query_family="academic")
        return batch.to_hit_dicts()[:limit]
    except Exception:
        return []


def test():
    from search_mesh.router import search_platform  # noqa: F401
    return "ok"
