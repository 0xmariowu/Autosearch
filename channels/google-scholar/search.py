from __future__ import annotations

import re
import sys

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

SCHOLAR_URL = "https://scholar.google.com/scholar"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


async def _search_scholar_html(query: str, max_results: int) -> list[dict]:
    """Try Google Scholar HTML scraping (may 403)."""
    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        resp = await client.get(
            SCHOLAR_URL,
            params={
                "q": query,
                "hl": "en",
                "ie": "UTF-8",
                "oe": "UTF-8",
                "start": 0,
                "as_sdt": "2007",
                "as_vis": "0",
            },
        )
        resp.raise_for_status()
        text = resp.text

        results: list[dict] = []
        # Parse search result blocks
        blocks = re.findall(
            r'<div\s+class="gs_ri">(.*?)</div>\s*</div>',
            text,
            re.DOTALL,
        )
        for block in blocks:
            title_match = re.search(
                r'<h3[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL
            )
            if not title_match:
                continue
            url = title_match.group(1)
            title = re.sub(r"<[^>]+>", "", title_match.group(2)).strip()

            snippet_match = re.search(
                r'<div\s+class="gs_rs">(.*?)</div>', block, re.DOTALL
            )
            snippet = (
                re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()
                if snippet_match
                else ""
            )

            year_match = re.search(r"(\d{4})\s*-\s*", block)
            metadata: dict = {}
            if year_match:
                metadata["published_at"] = f"{year_match.group(1)}-01-01T00:00:00Z"

            cited_match = re.search(r"Cited by (\d+)", block)
            if cited_match:
                metadata["citations"] = int(cited_match.group(1))

            results.append(
                make_result(
                    url=url,
                    title=title,
                    snippet=snippet,
                    source="google-scholar",
                    query=query,
                    extra_metadata=metadata,
                )
            )
            if len(results) >= max_results:
                break

        return results


async def _search_ddgs_fallback(query: str, max_results: int) -> list[dict]:
    """Fallback: search Google Scholar via DuckDuckGo site: filter."""
    from channels._engines.ddgs import search_ddgs_site

    return await search_ddgs_site(query, "scholar.google.com", max_results)


async def search(query: str, max_results: int = 10) -> list[dict]:
    # Try direct scraping first, fall back to ddgs
    try:
        results = await _search_scholar_html(query, max_results)
        if results:
            return results
    except Exception as exc:
        print(
            f"[google-scholar] HTML scraping failed, trying fallback: {exc}",
            file=sys.stderr,
        )

    try:
        return await _search_ddgs_fallback(query, max_results)
    except Exception as exc:
        print(f"[google-scholar] all search methods failed: {exc}", file=sys.stderr)
        return []
