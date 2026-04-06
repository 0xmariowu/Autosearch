from __future__ import annotations

import asyncio
import re

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

NPM_API = "https://registry.npmjs.org/-/v1/search"
NPM_PAGE_SIZE = 25
PYPI_BASE_URL = "https://pypi.org"
PYPI_PAGE_SIZE = 20
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


def _safe_isoformat(value: str) -> str | None:
    """Parse ISO 8601 dates without external deps."""
    if not value:
        return None
    try:
        # npm dates are like "2024-03-15T10:30:00.000Z"
        # PyPI dates are like "2024-03-15T10:30:00+00:00"
        cleaned = value.strip()
        if re.match(r"\d{4}-\d{2}-\d{2}", cleaned):
            return cleaned
        return None
    except Exception:
        return None


async def _search_npm(query: str, max_results: int) -> list[dict]:
    results: list[dict] = []

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(
                NPM_API,
                params={
                    "text": query,
                    "size": min(max_results, NPM_PAGE_SIZE),
                },
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("objects", [])

            for entry in items:
                package = entry.get("package", {})
                name = package.get("name", "")
                if not name:
                    continue
                url = f"https://www.npmjs.com/package/{name}"

                links = package.get("links", {})
                metadata = {
                    "ecosystem": "npm",
                    "package_name": name,
                    "version": package.get("version", ""),
                    "keywords": package.get("keywords", []),
                    "homepage": links.get("homepage", ""),
                    "source_code_url": links.get("repository", ""),
                }
                publisher = package.get("publisher", {})
                if publisher.get("username"):
                    metadata["author"] = publisher["username"]
                published_at = _safe_isoformat(package.get("date", ""))
                if published_at:
                    metadata["published_at"] = published_at

                results.append(
                    make_result(
                        url=url,
                        title=name,
                        snippet=package.get("description", "") or "",
                        source="npm-pypi",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
                if len(results) >= max_results:
                    return results[:max_results]

        return results[:max_results]
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="npm-pypi", error_type="network", message=f"npm: {exc}"
        ) from exc


async def _search_pypi(query: str, max_results: int) -> list[dict]:
    """Search PyPI using DDGS site: search (PyPI's own search blocks scrapers)."""
    from channels._engines.ddgs import search_ddgs_site

    try:
        return await search_ddgs_site(query, "pypi.org", max_results=max_results)
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="npm-pypi", error_type="network", message=f"pypi: {exc}"
        ) from exc


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        npm_results, pypi_results = await asyncio.gather(
            _search_npm(query, max_results),
            _search_pypi(query, max_results),
        )
    except Exception as exc:
        from lib.search_runner import SearchError

        raise SearchError(
            channel="npm-pypi", error_type="network", message=str(exc)
        ) from exc

    merged: list[dict] = []
    limit = max(len(npm_results), len(pypi_results))
    for index in range(limit):
        if index < len(npm_results):
            merged.append(npm_results[index])
        if index < len(pypi_results):
            merged.append(pypi_results[index])
        if len(merged) >= max_results:
            break
    return merged[:max_results]
