# Self-written for task F202
import html
import re
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="wikipedia")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
MAX_SNIPPET_LENGTH = 300
BASE_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch; mario@miao.company)"
TAG_RE = re.compile(r"<[^>]+>")


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


def _clean_snippet(snippet: object) -> str | None:
    cleaned = TAG_RE.sub("", str(snippet or "")).strip()
    cleaned = html.unescape(cleaned)
    if not cleaned:
        return None
    return _truncate_on_word_boundary(cleaned, MAX_SNIPPET_LENGTH) or None


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    pageid = item.get("pageid")
    if pageid in (None, ""):
        return None

    snippet = _clean_snippet(item.get("snippet"))

    return Evidence(
        url=f"https://en.wikipedia.org/?curid={pageid}",
        title=html.unescape(str(item.get("title") or "").strip()),
        snippet=snippet,
        content=snippet,
        source_channel="wikipedia:en",
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query.text,
        "format": "json",
        "srlimit": MAX_RESULTS,
        "srprop": "snippet",
    }
    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(BASE_URL, params=params, headers=headers)

        response.raise_for_status()
        payload = response.json()
        query_payload = payload.get("query")
        if not isinstance(query_payload, Mapping):
            raise ValueError("invalid query payload")

        items = query_payload.get("search")
        if not isinstance(items, list):
            raise ValueError("invalid search payload")
    except Exception as exc:
        LOGGER.warning("wikipedia_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
