# Self-written, plan autosearch-0418-channels-and-skills.md § F003
import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - compatibility fallback
    from duckduckgo_search import DDGS  # type: ignore[import-not-found]

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="ddgs")

MAX_RESULTS = 10
REGION = "wt-wt"
SAFESEARCH = "moderate"


async def search(query: SubQuery) -> list[Evidence]:
    try:
        results = await asyncio.to_thread(
            lambda: list(
                DDGS().text(
                    query.text,
                    max_results=MAX_RESULTS,
                    region=REGION,
                    safesearch=SAFESEARCH,
                )
            )
        )
    except Exception as exc:
        LOGGER.warning("ddgs_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    return [_to_evidence(result, fetched_at=fetched_at) for result in results]


def _to_evidence(
    result: Mapping[str, object],
    *,
    fetched_at: datetime,
) -> Evidence:
    title = str(result.get("title") or "")
    href = str(result.get("href") or "")
    body = str(result.get("body") or "")

    return Evidence(
        url=href,
        title=title,
        snippet=body[:500] or None,
        source_channel="ddgs",
        fetched_at=fetched_at,
        score=0.0,
    )
