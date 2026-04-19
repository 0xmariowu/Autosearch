# Self-written for task F201
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="github")

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
BASE_URL = "https://api.github.com/search/repositories"
ACCEPT_HEADER = "application/vnd.github+json"
API_VERSION = "2022-11-28"
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"


def _source_channel(item: Mapping[str, object]) -> str:
    language = str(item.get("language") or "").strip()
    return f"github:public:{language or 'unknown'}"


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = str(item.get("html_url") or "").strip()
    if not url:
        return None

    description = str(item.get("description") or "").strip() or None

    return Evidence(
        url=url,
        title=str(item.get("full_name") or "").strip(),
        snippet=description,
        content=description,
        source_channel=_source_channel(item),
        fetched_at=fetched_at,
        score=0.0,
    )


async def search(
    query: SubQuery,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> list[Evidence]:
    headers = {
        "Accept": ACCEPT_HEADER,
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": USER_AGENT,
    }
    params = {
        "q": query.text,
        "per_page": MAX_RESULTS,
        "sort": "stars",
        "order": "desc",
    }

    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(BASE_URL, params=params, headers=headers)

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("invalid payload")

        items = payload.get("items")
        if not isinstance(items, list):
            raise ValueError("invalid items payload")
    except Exception as exc:
        LOGGER.warning("github_search_public_repos_failed", reason=str(exc))
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
