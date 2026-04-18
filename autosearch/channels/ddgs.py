# Self-written, plan autosearch-0418-channels-and-skills.md § F004
import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - compatibility fallback
    from duckduckgo_search import DDGS  # type: ignore[import-not-found]

LOGGER = structlog.get_logger(__name__).bind(component="channel")


class DDGSChannel:
    """DuckDuckGo Search channel — free, no auth, no cookie.

    First real channel for dogfood: moves autosearch from DemoChannel placeholder
    to actual web results. Uses the `ddgs` (renamed from duckduckgo-search) PyPI package.
    """

    name = "ddgs"

    def __init__(
        self,
        max_results: int = 10,
        region: str = "wt-wt",
        safesearch: str = "moderate",
    ) -> None:
        self.max_results = max_results
        self.region = region
        self.safesearch = safesearch

    async def search(self, query: SubQuery) -> list[Evidence]:
        """Run DDGS text search for query.text, convert each hit to Evidence."""

        try:
            results = await asyncio.to_thread(
                lambda: list(
                    DDGS().text(
                        query.text,
                        max_results=self.max_results,
                        region=self.region,
                        safesearch=self.safesearch,
                    )
                )
            )
        except Exception as exc:
            LOGGER.warning("ddgs_search_failed", channel=self.name, reason=str(exc))
            return []

        fetched_at = datetime.now(UTC)
        return [self._to_evidence(result, fetched_at=fetched_at) for result in results]

    def _to_evidence(
        self,
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
            source_channel=self.name,
            fetched_at=fetched_at,
            score=0.0,
        )
