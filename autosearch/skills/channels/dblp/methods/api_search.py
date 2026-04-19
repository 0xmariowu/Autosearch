# Self-written for task Plan-0420 W7 F701 + F702
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="dblp")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
MAX_SNIPPET_LENGTH = 300
BASE_URL = "https://dblp.org/search/publ/api"


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _truncate_on_word_boundary(text: str, *, max_length: int) -> str:
    text = _normalize_whitespace(text)
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


def _clean_title(title: object) -> str:
    normalized = _normalize_whitespace(str(title or "").strip())
    if normalized.endswith("."):
        normalized = normalized[:-1].rstrip()
    return normalized


def _author_names(authors: object) -> list[str]:
    if not isinstance(authors, Mapping):
        return []

    raw_authors = authors.get("author")
    if isinstance(raw_authors, Mapping):
        items = [raw_authors]
    elif isinstance(raw_authors, list):
        items = raw_authors
    else:
        return []

    names: list[str] = []
    for item in items:
        if isinstance(item, Mapping):
            name = _normalize_whitespace(str(item.get("text") or "").strip())
        else:
            name = _normalize_whitespace(str(item or "").strip())
        if name:
            names.append(name)

    return names


def _resolve_url(info: Mapping[str, object]) -> str | None:
    for key in ("ee", "url"):
        url = str(info.get(key) or "").strip()
        if url:
            return url
    return None


def _build_snippet(info: Mapping[str, object]) -> str | None:
    parts: list[str] = []

    authors = ", ".join(_author_names(info.get("authors"))[:3])
    if authors:
        parts.append(authors)

    venue = _normalize_whitespace(str(info.get("venue") or "").strip())
    if venue:
        parts.append(venue)

    year = _normalize_whitespace(str(info.get("year") or "").strip())
    if year:
        parts.append(year)

    record_type = _normalize_whitespace(str(info.get("type") or "").strip())
    if record_type:
        parts.append(record_type)

    snippet = " · ".join(parts)
    return _truncate_on_word_boundary(snippet, max_length=MAX_SNIPPET_LENGTH) or None


def _to_evidence(hit: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    info = hit.get("info")
    if not isinstance(info, Mapping):
        return None

    title = _clean_title(info.get("title"))
    if not title:
        return None

    url = _resolve_url(info)
    if not url:
        return None

    snippet = _build_snippet(info)
    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=snippet,
        source_channel="dblp",
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    headers = {"Accept": "application/json"}
    params = {
        "q": query.text,
        "h": MAX_RESULTS,
        "format": "json",
    }

    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            ) as client:
                response = await client.get(BASE_URL, params=params, headers=headers)

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("invalid payload")

        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise ValueError("invalid result payload")

        hits = result.get("hits")
        if not isinstance(hits, Mapping):
            raise ValueError("invalid hits payload")

        raw_items = hits.get("hit", [])
        if isinstance(raw_items, list):
            items = raw_items
        elif isinstance(raw_items, Mapping):
            items = [raw_items]
        elif raw_items in (None, ""):
            items = []
        else:
            raise ValueError("invalid hit payload")
    except Exception as exc:
        LOGGER.warning("dblp_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
