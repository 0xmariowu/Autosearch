# Self-written for task feat/huggingface-openalex-channels
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="openalex")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
MAX_SNIPPET_LENGTH = 300
BASE_URL = "https://api.openalex.org/works"
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"


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


def _reconstruct_abstract(inverted: object) -> str:
    if not isinstance(inverted, Mapping) or not inverted:
        return ""

    positions: list[tuple[int, str]] = []
    for word, indices in inverted.items():
        if isinstance(indices, list):
            for index in indices:
                if isinstance(index, int):
                    positions.append((index, str(word)))

    positions.sort(key=lambda position: position[0])
    return " ".join(word for _, word in positions)


def _authors_text(authorships: object) -> str:
    if not isinstance(authorships, list):
        return ""

    names: list[str] = []
    for authorship in authorships:
        if not isinstance(authorship, Mapping):
            continue

        author = authorship.get("author")
        if not isinstance(author, Mapping):
            continue

        name = str(author.get("display_name") or "").strip()
        if name:
            names.append(name)

    return ", ".join(names[:3])


def _build_fallback_snippet(item: Mapping[str, object]) -> str:
    parts: list[str] = []

    authors = _authors_text(item.get("authorships"))
    if authors:
        parts.append(authors)

    publication_year = item.get("publication_year")
    if isinstance(publication_year, int):
        parts.append(str(publication_year))

    work_type = str(item.get("type") or "").strip()
    if work_type:
        parts.append(work_type)

    cited_by_count = item.get("cited_by_count")
    if isinstance(cited_by_count, int):
        parts.append(f"cited {cited_by_count}")
    else:
        parts.append("cited 0")

    return " \u00b7 ".join(parts)


def _resolve_url(item: Mapping[str, object]) -> str | None:
    best_oa_location = item.get("best_oa_location")
    if isinstance(best_oa_location, Mapping):
        landing_page_url = str(best_oa_location.get("landing_page_url") or "").strip()
        if landing_page_url:
            return landing_page_url

    doi = str(item.get("doi") or "").strip()
    if doi:
        return doi

    openalex_id = str(item.get("id") or "").strip()
    if openalex_id:
        return openalex_id

    return None


def _title(item: Mapping[str, object]) -> str:
    return str(item.get("title") or item.get("display_name") or "").strip()


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    title = _title(item)
    if not title:
        return None

    url = _resolve_url(item)
    if not url:
        return None

    abstract = _reconstruct_abstract(item.get("abstract_inverted_index")).strip()
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
        source_channel="openalex",
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    params = {
        "search": query.text,
        "per-page": MAX_RESULTS,
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

        items = payload.get("results")
        if not isinstance(items, list):
            raise ValueError("invalid results payload")
    except Exception as exc:
        LOGGER.warning("openalex_search_failed", reason=str(exc))
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
