"""Search GitHub repositories, issues, and code."""

name = "search_github"
description = "Search GitHub for repositories (by stars), issues (discussions and bugs), and code (specific implementations). Returns structured results with star counts and metadata."
when = "When looking for code, libraries, tools, or technical discussions on GitHub."
input_type = "query"
output_type = "hits"

input_schema = {
    "type": "object",
    "properties": {
        "input": {"type": "string", "description": "Search query text"},
        "context": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results to return", "default": 50},
                "query_family": {"type": "string", "description": "Query family label", "default": "unknown"},
                "search_type": {"type": "string", "enum": ["repos", "issues", "code", "all"], "default": "all"},
            },
        },
    },
    "required": ["input"],
}


def run(query, **context):
    from search_mesh.router import search_platform

    search_type = context.get("search_type", "all")
    limit = context.get("limit", 50)
    query_family = context.get("query_family", "unknown")

    providers = {
        "repos": {"name": "github_repos"},
        "issues": {"name": "github_issues"},
        "code": {"name": "github_code"},
    }
    if search_type != "all":
        providers = (
            {search_type: providers[search_type]}
            if search_type in providers
            else providers
        )

    all_hits = []
    for p in providers.values():
        try:
            batch = search_platform(p, str(query), query_family=query_family)
            all_hits.extend(batch.to_hit_dicts())
        except Exception:
            continue
    return all_hits[:limit]


def health_check():
    import shutil

    gh = shutil.which("gh")
    if not gh:
        return {"status": "off", "message": "gh CLI not installed"}
    import subprocess

    result = subprocess.run([gh, "auth", "status"], capture_output=True, timeout=5)
    if result.returncode == 0:
        return {"status": "ok", "message": "gh CLI authenticated"}
    return {"status": "off", "message": "gh CLI not authenticated"}


def test():
    from search_mesh.router import search_platform  # noqa: F401

    return "ok"
