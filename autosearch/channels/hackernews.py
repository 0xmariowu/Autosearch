# Self-written, plan autosearch-0418-channels-and-skills.md § F005
import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _clean_text(value: object) -> str:
    text = html.unescape(str(value or ""))
    text = _HTML_TAG_RE.sub("", text)
    return _normalize_whitespace(text)


def _truncate_with_ellipsis(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."


class HackerNewsChannel:
    """HN Algolia search — free, no auth. Real-time dev discussion coverage.

    Uses https://hn.algolia.com/api/v1/search endpoint.
    """

    name = "hackernews"

    def __init__(
        self,
        max_results: int = 10,
        http_timeout: float = 15.0,
        base_url: str = "https://hn.algolia.com/api/v1/search",
    ) -> None:
        self.max_results = max_results
        self.http_timeout = http_timeout
        self.base_url = base_url

    async def search(self, query: SubQuery) -> list[Evidence]:
        """Run Hacker News Algolia search, convert hits to Evidence."""

        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "query": query.text,
                        "hitsPerPage": self.max_results,
                        "tags": "(story,comment)",
                    },
                )
                response.raise_for_status()

            payload = response.json()
            hits = payload.get("hits", [])
            if not isinstance(hits, list):
                raise ValueError("invalid hits payload")
        except Exception as exc:
            LOGGER.warning("hackernews_search_failed", channel=self.name, reason=str(exc))
            return []

        fetched_at = datetime.now(UTC)
        return [
            self._to_evidence(hit, fetched_at=fetched_at)
            for hit in hits
            if isinstance(hit, Mapping)
        ]

    def _to_evidence(self, hit: Mapping[str, object], *, fetched_at: datetime) -> Evidence:
        object_id = str(hit.get("objectID") or "").strip()
        internal_url = self._item_url(object_id)
        external_url = str(hit.get("url") or "").strip()
        title = _clean_text(hit.get("title"))
        story_text = _clean_text(hit.get("story_text"))
        comment_text = _clean_text(hit.get("comment_text"))
        snippet = (story_text or comment_text)[:500] or None
        fallback_title = comment_text or story_text or f"Hacker News item {object_id}".strip()

        return Evidence(
            url=external_url or internal_url,
            title=title or _truncate_with_ellipsis(fallback_title, 80),
            snippet=snippet,
            source_channel=self.name,
            fetched_at=fetched_at,
            score=0.0,
        )

    def _item_url(self, object_id: str) -> str:
        if object_id:
            return f"https://news.ycombinator.com/item?id={object_id}"
        return "https://news.ycombinator.com/"
