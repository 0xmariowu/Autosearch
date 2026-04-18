# Self-written, plan autosearch-0418-channels-and-skills.md § F005
import asyncio
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


class ArxivChannel:
    """arxiv.org search channel — free, no auth. Academic preprint coverage.

    Follows skills/channels/arxiv/SKILL.md spec. Uses export.arxiv.org Atom API.
    Code-registered for now (per F005 wave pattern); will migrate to registry.compile_from_skills
    under F003 once the pipeline reads skill methods directly.
    """

    name = "arxiv"

    def __init__(
        self,
        max_results: int = 10,
        http_timeout: float = 30.0,
        base_url: str = "http://export.arxiv.org/api/query",
    ) -> None:
        self.max_results = max_results
        self.http_timeout = http_timeout
        self.base_url = base_url

    async def search(self, query: SubQuery) -> list[Evidence]:
        """Run arxiv Atom query, parse feed, return Evidence list."""

        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "search_query": f"all:{query.text}",
                        "start": 0,
                        "max_results": self.max_results,
                        "sortBy": "relevance",
                        "sortOrder": "descending",
                    },
                )
                response.raise_for_status()

            feed = await asyncio.to_thread(feedparser.parse, response.text)
            if getattr(feed, "bozo", 0):
                bozo_exception = getattr(feed, "bozo_exception", None)
                raise ValueError(str(bozo_exception or "failed to parse Atom feed"))

            entries = list(getattr(feed, "entries", []))
            if not entries:
                raise ValueError("empty feed")
        except Exception as exc:
            LOGGER.warning("arxiv_search_failed", channel=self.name, reason=str(exc))
            return []

        fetched_at = datetime.now(UTC)
        return [self._to_evidence(entry, fetched_at=fetched_at) for entry in entries]

    def _to_evidence(self, entry: object, *, fetched_at: datetime) -> Evidence:
        title = _normalize_whitespace(str(getattr(entry, "title", "") or ""))
        summary = _normalize_whitespace(str(getattr(entry, "summary", "") or ""))
        url = str(getattr(entry, "link", "") or getattr(entry, "id", "") or "").strip()

        return Evidence(
            url=url,
            title=title,
            snippet=summary[:500] or None,
            source_channel=self.name,
            fetched_at=fetched_at,
            score=0.0,
        )
