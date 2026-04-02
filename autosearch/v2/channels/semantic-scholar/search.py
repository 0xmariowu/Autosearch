from __future__ import annotations

import asyncio
import sys

import httpx

from autosearch.v2.search_runner import DEFAULT_TIMEOUT, make_result

SEMANTIC_SCHOLAR_RETRY_DELAYS = [2.0, 5.0]  # seconds between retries on 429


async def _ss_get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """Semantic Scholar GET with retry on 429 rate limit."""
    resp = await client.get(url, **kwargs)
    for delay in SEMANTIC_SCHOLAR_RETRY_DELAYS:
        if resp.status_code != 429:
            break
        print(
            f"[search_runner] semantic scholar 429, retry in {delay}s", file=sys.stderr
        )
        await asyncio.sleep(delay)
        resp = await client.get(url, **kwargs)
    return resp


async def search(query: str, max_results: int = 10, mode: str = "search") -> list[dict]:
    """Search Semantic Scholar API."""
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            if mode == "citations":
                resp = await _ss_get(
                    client,
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={"query": query, "limit": 1, "fields": "paperId,title"},
                )
                if resp.status_code != 200:
                    return []
                papers = resp.json().get("data", [])
                if not papers:
                    return []
                paper_id = papers[0]["paperId"]

                resp = await _ss_get(
                    client,
                    f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations",
                    params={
                        "limit": max_results,
                        "fields": "title,url,year,citationCount,authors",
                    },
                )
                if resp.status_code != 200:
                    return []
                citations = resp.json().get("data", [])
                results = []
                for c in citations:
                    cp = c.get("citingPaper", {})
                    if not cp.get("title"):
                        continue
                    authors = ", ".join(
                        a.get("name", "") for a in (cp.get("authors") or [])[:3]
                    )
                    metadata = {}
                    if cp.get("year"):
                        metadata["published_at"] = f"{cp['year']}-01-01T00:00:00Z"
                    if cp.get("citationCount"):
                        metadata["citations"] = cp["citationCount"]
                    results.append(
                        make_result(
                            url=cp.get("url")
                            or f"https://api.semanticscholar.org/paper/{cp.get('paperId', '')}",
                            title=cp.get("title", ""),
                            snippet=f"Authors: {authors}. Year: {cp.get('year', 'N/A')}. Citations: {cp.get('citationCount', 0)}",
                            source="semantic-scholar",
                            query=query,
                            extra_metadata=metadata,
                        )
                    )
                return results

            resp = await _ss_get(
                client,
                "https://api.semanticscholar.org/graph/v1/paper/search",
                params={
                    "query": query,
                    "limit": max_results,
                    "fields": "title,url,year,citationCount,authors,abstract",
                },
            )
            if resp.status_code != 200:
                print(
                    f"[search_runner] semantic scholar {resp.status_code}",
                    file=sys.stderr,
                )
                return []
            papers = resp.json().get("data", [])
            results = []
            for p in papers:
                authors = ", ".join(
                    a.get("name", "") for a in (p.get("authors") or [])[:3]
                )
                metadata = {}
                if p.get("year"):
                    metadata["published_at"] = f"{p['year']}-01-01T00:00:00Z"
                if p.get("citationCount"):
                    metadata["citations"] = p["citationCount"]
                results.append(
                    make_result(
                        url=p.get("url") or "",
                        title=p.get("title", ""),
                        snippet=p.get("abstract", "") or f"Authors: {authors}",
                        source="semantic-scholar",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
            return results
    except Exception as e:
        print(f"[search_runner] semantic scholar error: {e}", file=sys.stderr)
        return []
