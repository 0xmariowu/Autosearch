# Self-written for task F201
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import NamedTuple

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="package_search")

NPM_SEARCH_URL = "https://registry.npmjs.org/-/v1/search"
PYPI_JSON_URL = "https://pypi.org/pypi/{token}/json"
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": USER_AGENT,
}
MAX_NPM_RESULTS = 10
MAX_SNIPPET_LENGTH = 300
PER_SOURCE_TIMEOUT_SECONDS = 5.0


class SourceResult(NamedTuple):
    source: str
    evidence: list[Evidence]
    error: Exception | None


def _truncate_on_word_boundary(text: str, *, max_length: int) -> str:
    text = text.strip()
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


def _tokenize_pypi_query(text: str, *, max_pypi_tokens: int) -> list[str]:
    return text.split()[:max_pypi_tokens]


def _to_pypi_evidence(payload: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    info = payload.get("info")
    if not isinstance(info, Mapping):
        raise ValueError("invalid PyPI info payload")

    package_url = str(info.get("package_url") or "").strip()
    home_page = str(info.get("home_page") or "").strip()
    url = package_url or home_page
    if not url:
        return None

    name = str(info.get("name") or "").strip()
    version = str(info.get("version") or "").strip()
    title = " ".join(part for part in (name, version) if part) or name or url
    summary = str(info.get("summary") or "").strip()
    snippet = _truncate_on_word_boundary(summary, max_length=MAX_SNIPPET_LENGTH) or None
    content = summary or None

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=content,
        source_channel="package_search:pypi",
        fetched_at=fetched_at,
        score=0.0,
    )


def _to_npm_evidence(package: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    links = package.get("links")
    link_map = links if isinstance(links, Mapping) else {}
    npm_url = str(link_map.get("npm") or "").strip()
    homepage = str(link_map.get("homepage") or "").strip()
    url = npm_url or homepage
    if not url:
        return None

    name = str(package.get("name") or "").strip()
    version = str(package.get("version") or "").strip()
    title = " ".join(part for part in (name, version) if part) or name or url
    description = str(package.get("description") or "").strip()
    snippet = _truncate_on_word_boundary(description, max_length=MAX_SNIPPET_LENGTH) or None
    content = description or None

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=content,
        source_channel="package_search:npm",
        fetched_at=fetched_at,
        score=0.0,
    )


def _dedupe_by_url(evidences: list[Evidence]) -> list[Evidence]:
    seen_urls: set[str] = set()
    deduped: list[Evidence] = []

    for evidence in evidences:
        if evidence.url in seen_urls:
            continue
        seen_urls.add(evidence.url)
        deduped.append(evidence)

    return deduped


async def _fetch_pypi_token(
    client: httpx.AsyncClient,
    token: str,
    *,
    fetched_at: datetime,
) -> list[Evidence]:
    response = await client.get(PYPI_JSON_URL.format(token=token), headers=REQUEST_HEADERS)
    if response.status_code == 404:
        return []

    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("invalid PyPI payload")

    evidence = _to_pypi_evidence(payload, fetched_at=fetched_at)
    return [evidence] if evidence is not None else []


async def _fetch_npm_results(
    client: httpx.AsyncClient,
    query_text: str,
    *,
    fetched_at: datetime,
) -> list[Evidence]:
    response = await client.get(
        NPM_SEARCH_URL,
        params={"text": query_text, "size": MAX_NPM_RESULTS},
        headers=REQUEST_HEADERS,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("invalid npm payload")

    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise ValueError("invalid npm objects payload")

    evidences: list[Evidence] = []
    for item in objects:
        if not isinstance(item, Mapping):
            continue

        package = item.get("package")
        if not isinstance(package, Mapping):
            continue

        evidence = _to_npm_evidence(package, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences


async def _run_pypi_source(
    client: httpx.AsyncClient,
    token: str,
    *,
    fetched_at: datetime,
) -> SourceResult:
    source = f"pypi:{token}"
    try:
        return SourceResult(
            source=source,
            evidence=await asyncio.wait_for(
                _fetch_pypi_token(client, token, fetched_at=fetched_at),
                timeout=PER_SOURCE_TIMEOUT_SECONDS,
            ),
            error=None,
        )
    except TimeoutError:
        error = TimeoutError(f"{source} timed out after {PER_SOURCE_TIMEOUT_SECONDS:.1f}s")
        LOGGER.warning("package_search_source_failed", source=source, reason=str(error))
        return SourceResult(source=source, evidence=[], error=error)
    except httpx.HTTPError as exc:
        LOGGER.warning("package_search_source_failed", source=source, reason=str(exc))
        return SourceResult(source=source, evidence=[], error=exc)
    except Exception as exc:
        LOGGER.warning("package_search_source_failed", source=source, reason=str(exc))
        return SourceResult(source=source, evidence=[], error=exc)


async def _run_npm_source(
    client: httpx.AsyncClient,
    query_text: str,
    *,
    fetched_at: datetime,
) -> SourceResult:
    source = "npm"
    try:
        return SourceResult(
            source=source,
            evidence=await asyncio.wait_for(
                _fetch_npm_results(client, query_text, fetched_at=fetched_at),
                timeout=PER_SOURCE_TIMEOUT_SECONDS,
            ),
            error=None,
        )
    except TimeoutError:
        error = TimeoutError(f"{source} timed out after {PER_SOURCE_TIMEOUT_SECONDS:.1f}s")
        LOGGER.warning("package_search_source_failed", source=source, reason=str(error))
        return SourceResult(source=source, evidence=[], error=error)
    except httpx.HTTPError as exc:
        LOGGER.warning("package_search_source_failed", source=source, reason=str(exc))
        return SourceResult(source=source, evidence=[], error=exc)
    except Exception as exc:
        LOGGER.warning("package_search_source_failed", source=source, reason=str(exc))
        return SourceResult(source=source, evidence=[], error=exc)


def _most_informative_error(results: list[SourceResult]) -> Exception:
    errors = [result.error for result in results if result.error is not None]
    for error in errors:
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            if status in (401, 403, 429) or 400 <= status < 500:
                return error
    for error in errors:
        if isinstance(error, httpx.HTTPStatusError):
            return error
    return errors[0]


async def _search_with_client(
    query: SubQuery,
    *,
    client: httpx.AsyncClient,
    max_pypi_tokens: int,
) -> list[Evidence]:
    fetched_at = datetime.now(UTC)
    pypi_tokens = _tokenize_pypi_query(query.text, max_pypi_tokens=max_pypi_tokens)
    tasks = [
        _run_npm_source(client, query.text, fetched_at=fetched_at),
        *[_run_pypi_source(client, token, fetched_at=fetched_at) for token in pypi_tokens],
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    npm_results: list[Evidence] = []
    pypi_results: list[Evidence] = []
    source_results: list[SourceResult] = []
    for result in results:
        if isinstance(result, Exception):
            source = "unknown"
            LOGGER.warning("package_search_source_failed", source=source, reason=str(result))
            source_results.append(SourceResult(source=source, evidence=[], error=result))
            continue
        source_results.append(result)
        if result.source == "npm":
            npm_results.extend(result.evidence)
            continue
        pypi_results.extend(result.evidence)

    if source_results and all(
        result.error is not None and not result.evidence for result in source_results
    ):
        raise_as_channel_error(_most_informative_error(source_results))

    return _dedupe_by_url([*npm_results, *pypi_results])


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
    max_pypi_tokens: int = 5,
) -> list[Evidence]:
    if http_client is not None:
        return await _search_with_client(
            query,
            client=http_client,
            max_pypi_tokens=max_pypi_tokens,
        )

    async with httpx.AsyncClient(timeout=PER_SOURCE_TIMEOUT_SECONDS) as client:
        return await _search_with_client(
            query,
            client=client,
            max_pypi_tokens=max_pypi_tokens,
        )
