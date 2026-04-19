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
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return []

    nested_data = data.get("data")
    if not isinstance(nested_data, Mapping):
        return []

    search_by_raw_query = nested_data.get("search_by_raw_query")
    if not isinstance(search_by_raw_query, Mapping):
        return []

    search_timeline = search_by_raw_query.get("search_timeline")
    if not isinstance(search_timeline, Mapping):
        return []

    timeline = search_timeline.get("timeline")
    if not isinstance(timeline, Mapping):
        return []

    instructions = timeline.get("instructions")
    if not isinstance(instructions, list):
        return []

    tweets: list[Mapping[str, object]] = []
    for instruction in instructions:
        if not isinstance(instruction, Mapping):
            continue
        entries = instruction.get("entries")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            content = entry.get("content")
            if not isinstance(content, Mapping):
                continue
            item_content = content.get("itemContent")
            if not isinstance(item_content, Mapping):
                continue
            tweet_results = item_content.get("tweet_results")
            if not isinstance(tweet_results, Mapping):
                continue
            result = tweet_results.get("result")
            if isinstance(result, Mapping):
                tweets.append(result)

    return tweets


def _to_evidence(tweet: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    rest_id = str(tweet.get("rest_id") or "").strip()

    legacy = tweet.get("legacy")
    legacy_map = legacy if isinstance(legacy, Mapping) else {}
    full_text = _clean_text(legacy_map.get("full_text"))

    core = tweet.get("core")
    core_map = core if isinstance(core, Mapping) else {}
    user_results = core_map.get("user_results")
    user_results_map = user_results if isinstance(user_results, Mapping) else {}
    user_result = user_results_map.get("result")
    user_result_map = user_result if isinstance(user_result, Mapping) else {}
    user_legacy = user_result_map.get("legacy")
    user_legacy_map = user_legacy if isinstance(user_legacy, Mapping) else {}
    screen_name = str(user_legacy_map.get("screen_name") or "").strip()

    if not rest_id or not screen_name:
        return None

    title = _truncate_on_word_boundary(full_text, max_length=MAX_TITLE_LENGTH) or "Tweet"
    snippet = _truncate_on_word_boundary(full_text, max_length=MAX_SNIPPET_LENGTH) or None
    content = full_text or snippet

    return Evidence(
        url=f"https://twitter.com/{screen_name}/status/{rest_id}",
        title=title,
        snippet=snippet,
        content=content,
        source_channel=f"twitter:{screen_name}" if screen_name else "twitter",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: TikhubClient | None = None) -> list[Evidence]:
    try:
        tikhub_client = client or TikhubClient()
        payload = await tikhub_client.get(
            SEARCH_PATH,
            {"keyword": query.text, "search_type": "Top"},
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
