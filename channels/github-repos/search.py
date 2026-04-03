from __future__ import annotations

import asyncio
import json
import sys

from lib.search_runner import DEFAULT_TIMEOUT, make_result


async def search(query: str, max_results: int = 20) -> list[dict]:
    """Search GitHub repos via gh CLI."""
    try:
        cmd = [
            "gh",
            "search",
            "repos",
            query,
            f"--limit={max_results}",
            "--sort=stars",
            "--json=fullName,url,description,stargazersCount,updatedAt,language",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=DEFAULT_TIMEOUT
        )
        if proc.returncode != 0:
            print(f"[search_runner] gh repos error: {stderr.decode()}", file=sys.stderr)
            return []

        repos = json.loads(stdout.decode())
        results = []
        for r in repos:
            lang_raw = r.get("language", "")
            lang_name = lang_raw if isinstance(lang_raw, str) else ""
            metadata = {"stars": r.get("stargazersCount", 0)}
            if r.get("updatedAt"):
                metadata["updated_at"] = r["updatedAt"]
            if lang_name:
                metadata["language"] = lang_name
            results.append(
                make_result(
                    url=r.get("url", ""),
                    title=r.get("fullName", ""),
                    snippet=r.get("description", "") or "",
                    source="github",
                    query=query,
                    extra_metadata=metadata,
                )
            )
        return results
    except Exception as e:
        print(f"[search_runner] gh repos error: {e}", file=sys.stderr)
        return []
