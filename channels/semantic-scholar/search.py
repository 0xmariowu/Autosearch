from __future__ import annotations

import asyncio
import os
import sys

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, SearchError, make_result

_S2_API_KEY = os.environ.get("S2_API_KEY", "")


async def _ss_get(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """Semantic Scholar GET — raises SearchError on 429 rate limit.

    Retry is handled by the runner-level retry wrapper, not here.
    """
    headers = kwargs.pop("headers", {})
    if _S2_API_KEY:
        headers["x-api-key"] = _S2_API_KEY
    resp = await client.get(url, headers=headers, **kwargs)
    if resp.status_code == 429:
        raise SearchError(
            channel="semantic-scholar",
            error_type="rate_limit",
            message="429 Too Many Requests",
        )
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

                await asyncio.sleep(1)  # Rate limit: avoid back-to-back requests
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
        from lib.search_runner import SearchError

        raise SearchError(
            channel="semantic-scholar", error_type="network", message=str(e)
        ) from e
