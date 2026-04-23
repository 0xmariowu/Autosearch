from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import UTC, datetime

import structlog

from autosearch.core.models import Evidence, SubQuery
from autosearch.lib.tikhub_client import TikhubClient, TikhubError

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="twitter")
SEARCH_PATH = "/api/v1/twitter/web/fetch_search_timeline"
MAX_TITLE_LENGTH = 80
MAX_SNIPPET_LENGTH = 300


def _clean_text(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


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


def _extract_tweets(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Extract tweet objects — TikHub returns a flat list at data.timeline."""
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return []
    timeline = data.get("timeline")
    if not isinstance(timeline, list):
        return []
    return [t for t in timeline if isinstance(t, Mapping)]


def _expand_url(entities: object) -> str:
    if not isinstance(entities, Mapping):
        return ""
    urls = entities.get("urls")
    if not isinstance(urls, list):
        return ""
    for u in urls:
        if not isinstance(u, Mapping):
            continue
        expanded = str(u.get("expanded_url") or "").strip()
        if expanded and not expanded.startswith("https://t.co"):
            return expanded
    return ""


def _to_evidence(tweet: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    tweet_id = str(tweet.get("tweet_id") or "").strip()
    screen_name = str(tweet.get("screen_name") or "").strip()
    text = _clean_text(tweet.get("text"))

    if not tweet_id or not screen_name:
        return None

    url = f"https://x.com/{screen_name}/status/{tweet_id}"
    title = _truncate_on_word_boundary(text, max_length=MAX_TITLE_LENGTH) or "Tweet"
    snippet = _truncate_on_word_boundary(text, max_length=MAX_SNIPPET_LENGTH) or None
    content = text or snippet

    return Evidence(
        url=url,
        title=title,
        snippet=snippet,
        content=content,
        source_channel=f"twitter:{screen_name}",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {"keyword": query.text, "search_type": "Latest"},
        )
    except (TikhubError, ValueError) as exc:
        LOGGER.warning("twitter_tikhub_search_failed", reason=str(exc))
        return []

    tweets = _extract_tweets(payload)
    fetched_at = datetime.now(UTC)

    results: list[Evidence] = []
    for tweet in tweets:
        evidence = _to_evidence(tweet, fetched_at=fetched_at)
        if evidence is not None:
            results.append(evidence)

    return results
