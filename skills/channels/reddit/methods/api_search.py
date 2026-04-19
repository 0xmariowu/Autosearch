# Self-written for task F201
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="reddit")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
MAX_SNIPPET_LENGTH = 300
BASE_URL = "https://www.reddit.com/search.json"
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"


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


def _resolve_url(post: Mapping[str, object]) -> str | None:
    if bool(post.get("is_self")):
        permalink = str(post.get("permalink") or "").strip()
        if not permalink:
            return None
        return f"https://www.reddit.com{permalink}"

    url = str(post.get("url") or "").strip()
    return url or None


def _to_evidence(post: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _resolve_url(post)
    if not url:
        return None

    selftext = str(post.get("selftext") or "").strip()
    subreddit = str(post.get("subreddit") or "").strip()
    snippet = _truncate_on_word_boundary(selftext, MAX_SNIPPET_LENGTH) or None
    source_channel = f"reddit:r/{subreddit}" if subreddit else "reddit"

    return Evidence(
        url=url,
        title=str(post.get("title") or "").strip(),
        snippet=snippet,
        content=selftext or snippet,
        source_channel=source_channel,
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
                    "limit": MAX_RESULTS,
                    "raw_json": 1,
                },
                headers={"User-Agent": USER_AGENT},
            )
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(
                    BASE_URL,
                    params={
                        "q": query.text,
                        "limit": MAX_RESULTS,
                        "raw_json": 1,
                    },
                    headers={"User-Agent": USER_AGENT},
                )

        response.raise_for_status()
        payload = response.json()
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise ValueError("invalid data payload")

        children = data.get("children")
        if not isinstance(children, list):
            raise ValueError("invalid children payload")
    except Exception as exc:
        LOGGER.warning("reddit_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for child in children:
        if not isinstance(child, Mapping):
            continue

        post = child.get("data")
        if not isinstance(post, Mapping):
            continue

        evidence = _to_evidence(post, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
