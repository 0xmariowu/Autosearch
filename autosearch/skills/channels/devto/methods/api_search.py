# Self-written for task F201
import html
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="devto")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
BASE_URL = "https://dev.to/api/articles"


def _source_channel(tags: object) -> str:
    if not isinstance(tags, list):
        return "devto:"

    normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    return f"devto:{','.join(normalized_tags[:3])}"


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = str(item.get("url") or "").strip()
    if not url:
        return None

    description = str(item.get("description") or "").strip() or None

    return Evidence(
        url=url,
        title=html.unescape(str(item.get("title") or "").strip()),
        snippet=description,
        content=description,
        source_channel=_source_channel(item.get("tag_list")),
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
                    "search": query.text,
                    "per_page": MAX_RESULTS,
                },
            )
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    BASE_URL,
                    params={
                        "search": query.text,
                        "per_page": MAX_RESULTS,
                    },
                )

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("invalid items payload")
    except Exception as exc:
        LOGGER.warning("devto_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
