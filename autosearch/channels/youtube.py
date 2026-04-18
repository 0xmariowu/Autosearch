# Self-written, plan autosearch-0418-channels-and-skills.md § F005
import html
import os
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel")


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _clean_text(value: object) -> str:
    return _normalize_whitespace(html.unescape(str(value or "")))


class YouTubeChannel:
    """YouTube Data API v3 search channel.

    SECURITY: API key sent via `x-goog-api-key` header, never as URL query param
    (prevents key leaking into logs / error traces — same lesson as gemini provider).
    """

    name = "youtube"

    def __init__(
        self,
        api_key: str | None = None,
        max_results: int = 10,
        http_timeout: float = 15.0,
        base_url: str = "https://www.googleapis.com/youtube/v3/search",
    ) -> None:
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        self.max_results = max_results
        self.http_timeout = http_timeout
        self.base_url = base_url
        self._warned_no_api_key = False

    async def search(self, query: SubQuery) -> list[Evidence]:
        """Return YouTube video matches or [] when unavailable/failing."""

        if not self.api_key:
            if not self._warned_no_api_key:
                LOGGER.warning("youtube_search_skipped", channel=self.name, reason="no_api_key")
                self._warned_no_api_key = True
            return []

        try:
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "part": "snippet",
                        "q": query.text,
                        "type": "video",
                        "maxResults": self.max_results,
                    },
                    headers={"x-goog-api-key": self.api_key},
                )
                response.raise_for_status()

            payload = response.json()
            items = payload.get("items", [])
            if not isinstance(items, list):
                raise ValueError("invalid items payload")
            fetched_at = datetime.now(UTC)
            return [
                self._to_evidence(item, fetched_at=fetched_at)
                for item in items
                if isinstance(item, Mapping)
            ]
        except httpx.HTTPStatusError as exc:
            reason = "auth_failed" if exc.response.status_code in {401, 403} else str(exc)
            LOGGER.warning("youtube_search_failed", channel=self.name, reason=reason)
            return []
        except Exception as exc:
            LOGGER.warning("youtube_search_failed", channel=self.name, reason=str(exc))
            return []

    def _to_evidence(self, item: Mapping[str, object], *, fetched_at: datetime) -> Evidence:
        item_id = item["id"]
        snippet = item["snippet"]
        if not isinstance(item_id, Mapping) or not isinstance(snippet, Mapping):
            raise ValueError("invalid youtube item")

        video_id = str(item_id["videoId"]).strip()
        title = _clean_text(snippet["title"])
        description = _clean_text(snippet.get("description"))

        return Evidence(
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=title,
            snippet=description[:500] or None,
            source_channel=self.name,
            fetched_at=fetched_at,
            score=0.0,
        )
