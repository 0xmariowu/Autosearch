from __future__ import annotations

import asyncio
import sys


import httpx

from autosearch.v2.search_runner import DEFAULT_TIMEOUT, make_result

NPM_API = "https://api.npms.io/v2/search"
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
    total_pages = max(1, (max_results + NPM_PAGE_SIZE - 1) // NPM_PAGE_SIZE)

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for page in range(1, total_pages + 1):
                response = await client.get(
                    NPM_API,
                    params={
                        "from": (page - 1) * NPM_PAGE_SIZE,
                        "q": query,
                        "size": NPM_PAGE_SIZE,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                items = payload.get("results", [])
                if not items:
                    break

                for entry in items:
                    package = entry.get("package", {})
                    name = package.get("name", "")
                    links = package.get("links", {})
                    url = links.get("npm", "")
                    if not name or not url:
                        continue

                    metadata = {
                        "ecosystem": "npm",
                        "package_name": name,
                        "version": package.get("version", ""),
                        "maintainer": package.get("author", {}).get("name", ""),
                        "tags": list(entry.get("flags", {}).keys())
                        + package.get("keywords", []),
                        "homepage": links.get("homepage", ""),
                        "source_code_url": links.get("repository", ""),
                    }
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
        print(f"[npm-pypi] npm search failed: {exc}", file=sys.stderr)
        return []


async def _search_pypi(query: str, max_results: int) -> list[dict]:
    results: list[dict] = []

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(
                f"{PYPI_BASE_URL}/search/",
                params={"q": query, "page": 1},
            )
            response.raise_for_status()
            text = response.text

            # Parse package snippets with regex (no lxml dependency)
            snippets = re.findall(
                r'<a\s+class="package-snippet"\s+href="(/project/[^"]+/)"[^>]*>'
                r"(.*?)</a>",
                text,
                re.DOTALL,
            )

            for href, snippet_html in snippets:
                name_match = re.search(
                    r"package-snippet__name[^>]*>([^<]+)", snippet_html
                )
                version_match = re.search(
                    r"package-snippet__version[^>]*>([^<]+)", snippet_html
                )
                desc_match = re.search(
                    r"package-snippet__description[^>]*>([^<]*)", snippet_html
                )
                date_match = re.search(r'datetime="([^"]+)"', snippet_html)

                name = name_match.group(1).strip() if name_match else ""
                if not name:
                    continue

                version = version_match.group(1).strip() if version_match else ""
                description = desc_match.group(1).strip() if desc_match else ""
                published_at = date_match.group(1).strip() if date_match else ""

                metadata: dict[str, str] = {
                    "ecosystem": "pypi",
                    "package_name": name,
                    "version": version,
                }
                parsed_date = _safe_isoformat(published_at)
                if parsed_date:
                    metadata["published_at"] = parsed_date

                results.append(
                    make_result(
                        url=f"{PYPI_BASE_URL}{href}",
                        title=name,
                        snippet=description,
                        source="npm-pypi",
                        query=query,
                        extra_metadata=metadata,
                    )
                )
                if len(results) >= max_results:
                    return results[:max_results]

        return results[:max_results]
    except Exception as exc:
        print(f"[npm-pypi] pypi search failed: {exc}", file=sys.stderr)
        return []


async def search(query: str, max_results: int = 10) -> list[dict]:
    try:
        npm_results, pypi_results = await asyncio.gather(
            _search_npm(query, max_results),
            _search_pypi(query, max_results),
        )
    except Exception as exc:
        print(f"[npm-pypi] search failed: {exc}", file=sys.stderr)
        return []

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
