# Self-written for task F202
import html
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="wikidata")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
BASE_URL = "https://www.wikidata.org/w/api.php"
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch; mario@miao.company)"


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    entity_id = str(item.get("id") or "").strip()
    concepturi = str(item.get("concepturi") or "").strip()
    url = concepturi or (f"https://www.wikidata.org/wiki/{entity_id}" if entity_id else "")
    if not url:
        return None

    title = html.unescape(str(item.get("label") or entity_id or concepturi).strip())
    description = html.unescape(str(item.get("description") or "").strip()) or None
    source_channel = f"wikidata:{entity_id}" if entity_id else "wikidata"

    return Evidence(
        url=url,
        title=title,
        snippet=description,
        content=description,
        source_channel=source_channel,
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
        "action": "wbsearchentities",
        "search": query.text,
        "language": "en",
        "format": "json",
        "limit": MAX_RESULTS,
        "type": "item",
    }
    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(BASE_URL, params=params, headers=headers)

        response.raise_for_status()
        payload = response.json()
        items = payload.get("search")
        if not isinstance(items, list):
            raise ValueError("invalid search payload")
    except Exception as exc:
        LOGGER.warning("wikidata_search_failed", reason=str(exc))
        raise_as_channel_error(exc)

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
