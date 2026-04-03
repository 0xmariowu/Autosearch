from __future__ import annotations

import sys
import xml.etree.ElementTree as ET

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Search arXiv API (Atom feed)."""
    try:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        search_terms = " AND ".join(f"all:{w}" for w in query.split()[:4])
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": search_terms,
                    "max_results": max_results,
                    "sortBy": "relevance",
                },
            )
            if resp.status_code != 200:
                print(f"[search_runner] arxiv {resp.status_code}", file=sys.stderr)
                return []
            root = ET.fromstring(resp.text)
            results = []
            for entry in root.findall("a:entry", ns):
                title_el = entry.find("a:title", ns)
                id_el = entry.find("a:id", ns)
                summary_el = entry.find("a:summary", ns)
                published_el = entry.find("a:published", ns)
                if title_el is None or id_el is None:
                    continue
                title = (
                    title_el.text.strip().replace("\n", " ") if title_el.text else ""
                )
                url = id_el.text.strip() if id_el.text else ""
                snippet = (
                    summary_el.text.strip()[:300]
                    if summary_el is not None and summary_el.text
                    else ""
                )
                metadata = {}
                if published_el is not None and published_el.text:
                    metadata["published_at"] = published_el.text.strip()
                authors = [a.find("a:name", ns) for a in entry.findall("a:author", ns)]
                author_names = ", ".join(
                    a.text for a in authors[:3] if a is not None and a.text
                )
                if author_names:
                    metadata["authors"] = author_names
                results.append(
                    make_result(
                        url=url,
                        title=title,
                        snippet=snippet,
                        source="arxiv",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
            return results
    except Exception as e:
        print(f"[search_runner] arxiv error: {e}", file=sys.stderr)
        return []
