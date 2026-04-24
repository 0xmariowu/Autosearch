# Self-written for task F204
from __future__ import annotations

import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="podcast_cn")

BASE_URL = "https://itunes.apple.com/search"
MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"
REQUEST_HEADERS = {"User-Agent": USER_AGENT}
NON_SLUG_CHAR_RE = re.compile(r"[^\w-]+", re.UNICODE)
MULTI_HYPHEN_RE = re.compile(r"-+")


def _sanitize_source_token(value: str) -> str:
    slug = value.lower().strip()
    if not slug:
        return ""

    slug = re.sub(r"\s+", "-", slug)
    slug = slug.replace("_", "-")
    slug = NON_SLUG_CHAR_RE.sub("", slug)
    slug = MULTI_HYPHEN_RE.sub("-", slug).strip("-")
    return slug


def _source_channel(item: Mapping[str, object]) -> str:
    genre = str(item.get("primaryGenreName") or "").strip()
    genre_slug = _sanitize_source_token(genre)
    return f"podcast_cn:{genre_slug}" if genre_slug else "podcast_cn"


def _snippet(item: Mapping[str, object]) -> str | None:
    genre = html.unescape(str(item.get("primaryGenreName") or "").strip())
    track_count = item.get("trackCount")
    if not genre or track_count in (None, ""):
        return None
    return f"{genre} podcast (Episodes: {track_count})"


def _title(item: Mapping[str, object]) -> str:
    collection_name = html.unescape(str(item.get("collectionName") or "").strip())
    artist_name = html.unescape(str(item.get("artistName") or "").strip())
    if collection_name and artist_name:
        return f"{collection_name} - {artist_name}"
    return collection_name or artist_name


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = str(item.get("collectionViewUrl") or item.get("feedUrl") or "").strip()
    if not url:
        return None

    snippet = _snippet(item)
    return Evidence(
        url=url,
        title=_title(item),
        snippet=snippet,
        content=snippet,
        source_channel=_source_channel(item),
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    params = {
        "country": "cn",
        "media": "podcast",
        "entity": "podcast",
        "limit": MAX_RESULTS,
        "term": query.text,
    }

    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=REQUEST_HEADERS)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(BASE_URL, params=params, headers=REQUEST_HEADERS)

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("invalid iTunes payload")

        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("invalid iTunes results payload")
    except Exception as exc:
        LOGGER.warning("podcast_cn_search_failed", reason=str(exc))
        raise_as_channel_error(exc)

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in results:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
