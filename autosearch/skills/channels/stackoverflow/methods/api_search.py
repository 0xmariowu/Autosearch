# Self-written for task F201
import html
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="stackoverflow")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
MAX_SNIPPET_LENGTH = 300
BASE_URL = "https://api.stackexchange.com/2.3/search/advanced"


def _truncate_on_word_boundary(text: str, max_length: int) -> str:
    text = text.strip()
    if len(text) <= max_length:
        return text

    candidate = text[:max_length]
    if candidate and not candidate[-1].isspace():
        shortened = candidate.rsplit(None, 1)[0]
        if shortened:
            candidate = shortened

    return f"{candidate.rstrip()}…"


def _source_channel(tags: object) -> str:
    if not isinstance(tags, list):
        return "stackoverflow"

    normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    if not normalized_tags:
        return "stackoverflow"

    return f"stackoverflow:{','.join(normalized_tags[:3])}"


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = str(item.get("link") or "").strip()
    if not url:
        return None

    body_markdown = str(item.get("body_markdown") or "").strip()
    snippet = _truncate_on_word_boundary(body_markdown, MAX_SNIPPET_LENGTH) or None

    return Evidence(
        url=url,
        title=html.unescape(str(item.get("title") or "").strip()),
        snippet=snippet,
        content=body_markdown or snippet,
        source_channel=_source_channel(item.get("tags")),
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    try:
        if http_client is not None:
            response = await http_client.get(
                BASE_URL,
                params={
                    "q": query.text,
                    "site": "stackoverflow",
                    "pagesize": MAX_RESULTS,
                    "order": "desc",
                    "sort": "relevance",
                    "filter": "withbody",
                },
            )
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    BASE_URL,
                    params={
                        "q": query.text,
                        "site": "stackoverflow",
                        "pagesize": MAX_RESULTS,
                        "order": "desc",
                        "sort": "relevance",
                        "filter": "withbody",
                    },
                )

        response.raise_for_status()
        payload = response.json()
        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("invalid items payload")
    except Exception as exc:
        LOGGER.warning("stackoverflow_search_failed", reason=str(exc))
        raise_as_channel_error(exc)

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
