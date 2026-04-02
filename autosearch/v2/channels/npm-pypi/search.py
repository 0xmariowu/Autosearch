from __future__ import annotations

import asyncio
import sys

import httpx
from dateutil import parser as date_parser
from lxml import html as lxml_html

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
    try:
        return date_parser.parse(value).isoformat()
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
    total_pages = max(1, (max_results + PYPI_PAGE_SIZE - 1) // PYPI_PAGE_SIZE)

    try:
        async with httpx.AsyncClient(
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for page in range(1, total_pages + 1):
                response = await client.get(
                    f"{PYPI_BASE_URL}/search/",
                    params={"q": query, "page": page},
                )
                response.raise_for_status()
                dom = lxml_html.fromstring(response.text)
                entries = dom.xpath(
                    '/html/body/main/div/div/div/form/div/ul/li/a[@class="package-snippet"]'
                )
                if not entries:
                    break

                for entry in entries:
                    href = "".join(entry.xpath("./@href")).strip()
                    name = "".join(
                        text.strip()
                        for text in entry.xpath(
                            './h3/span[@class="package-snippet__name"]/text()'
                        )
                        if text.strip()
                    )
                    version = "".join(
                        text.strip()
                        for text in entry.xpath(
                            './h3/span[@class="package-snippet__version"]/text()'
                        )
                        if text.strip()
                    )
                    description = " ".join(
                        text.strip() for text in entry.xpath("./p//text()") if text.strip()
                    )
                    published_at = "".join(
                        text.strip()
                        for text in entry.xpath(
                            './h3/span[@class="package-snippet__created"]/time/@datetime'
                        )
                        if text.strip()
                    )
                    if not href or not name:
                        continue

                    metadata = {
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
