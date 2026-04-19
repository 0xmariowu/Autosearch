# Self-written for task Plan-0420 W7 F701 + F702
import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="crossref")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
MAX_SNIPPET_LENGTH = 300
BASE_URL = "https://api.crossref.org/works"
TAG_RE = re.compile(r"<[^>]+>")


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


def _first_text(value: object) -> str:
    if not isinstance(value, list):
        return ""

    for item in value:
        text = _normalize_whitespace(str(item or "").strip())
        if text:
            return text

    return ""


def _author_name(author: Mapping[str, object]) -> str:
    explicit_name = _normalize_whitespace(str(author.get("name") or "").strip())
    if explicit_name:
        return explicit_name

    given = _normalize_whitespace(str(author.get("given") or "").strip())
    family = _normalize_whitespace(str(author.get("family") or "").strip())
    return " ".join(part for part in (given, family) if part).strip()


def _authors_text(authors: object) -> str:
    if not isinstance(authors, list):
        return ""

    names: list[str] = []
    for author in authors:
        if not isinstance(author, Mapping):
            continue

        name = _author_name(author)
        if name:
            names.append(name)

    return ", ".join(names[:3])


def _published_year(item: Mapping[str, object]) -> str:
    for key in ("published-print", "published", "issued"):
        published = item.get(key)
        if not isinstance(published, Mapping):
            continue

        date_parts = published.get("date-parts")
        if not isinstance(date_parts, list) or not date_parts:
            continue

        first_part = date_parts[0]
        if not isinstance(first_part, list) or not first_part:
            continue

        year = first_part[0]
        if isinstance(year, int):
            return str(year)
        if isinstance(year, str) and year.strip():
            return year.strip()

    return ""


def _clean_abstract(abstract: object) -> str:
    cleaned = TAG_RE.sub(" ", str(abstract or ""))
    return _normalize_whitespace(html.unescape(cleaned))


def _build_fallback_snippet(item: Mapping[str, object]) -> str:
    parts: list[str] = []

    authors = _authors_text(item.get("author"))
    if authors:
        parts.append(authors)

    container_title = _first_text(item.get("container-title"))
    if container_title:
        parts.append(container_title)

    year = _published_year(item)
    if year:
        parts.append(year)

    work_type = _normalize_whitespace(str(item.get("type") or "").strip())
    if work_type:
        parts.append(work_type)

    cited = item.get("is-referenced-by-count")
    parts.append(f"cited {cited}" if isinstance(cited, int) else "cited 0")

    return " · ".join(parts)


def _resolve_url(item: Mapping[str, object]) -> str | None:
    url = str(item.get("URL") or "").strip()
    if url:
        return url

    doi = str(item.get("DOI") or "").strip()
    if doi:
        return f"https://doi.org/{doi}"

    return None


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    title = _first_text(item.get("title"))
    if not title:
        return None

    url = _resolve_url(item)
    if not url:
        return None

    abstract = _clean_abstract(item.get("abstract"))
    if abstract:
        snippet = _truncate_on_word_boundary(abstract, max_length=MAX_SNIPPET_LENGTH)
        content = abstract
    else:
        snippet = _truncate_on_word_boundary(
            _build_fallback_snippet(item),
            max_length=MAX_SNIPPET_LENGTH,
        )
        content = snippet or None

    return Evidence(
        url=url,
        title=title,
        snippet=snippet or None,
        content=content,
        source_channel="crossref",
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
        "query.title": query.text,
        "rows": MAX_RESULTS,
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

        message = payload.get("message")
        if not isinstance(message, Mapping):
            raise ValueError("invalid message payload")

        items = message.get("items")
        if not isinstance(items, list):
            raise ValueError("invalid items payload")
    except Exception as exc:
        LOGGER.warning("crossref_search_failed", reason=str(exc))
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
