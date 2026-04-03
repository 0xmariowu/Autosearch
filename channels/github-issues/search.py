from __future__ import annotations

import asyncio
import json
import sys

from lib.search_runner import DEFAULT_TIMEOUT, make_result


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search GitHub issues via gh CLI."""
    try:
        cmd = [
            "gh",
            "search",
            "issues",
            query,
            f"--limit={max_results}",
            "--json=title,url,body,createdAt,repository",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=DEFAULT_TIMEOUT
        )
        if proc.returncode != 0:
            return []

        issues = json.loads(stdout.decode())
        results = []
        for r in issues:
            repo = r.get("repository", {})
            repo_name = repo.get("nameWithOwner", "") if isinstance(repo, dict) else ""
            metadata = {}
            if r.get("createdAt"):
                metadata["created_utc"] = r["createdAt"]
            results.append(
                make_result(
                    url=r.get("url", ""),
                    title=f"[{repo_name}] {r.get('title', '')}",
                    snippet=(r.get("body", "") or "")[:300],
                    source="github",
                    query=query,
                    extra_metadata=metadata,
                )
            )
        return results
    except Exception as e:
        print(f"[search_runner] gh issues error: {e}", file=sys.stderr)
        return []
