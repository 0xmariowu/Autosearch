# Self-written for task F201
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import (
    ChannelAuthError,
    PermanentError,
    RateLimited,
    TransientError,
)
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

    # Bug 1 (fix-plan): distinguish "GitHub returned zero results" (legit empty)
    # from network failures, auth rejection (401/403), rate limits (429), and
    # malformed payloads. Each maps to a typed exception the MCP boundary
    # translates into a distinct status — so a 401 on a misconfigured token
    # no longer looks like "no matches found".
    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(BASE_URL, params=params, headers=headers)
    except httpx.HTTPError as exc:
        LOGGER.warning("github_search_public_repos_network_failed", reason=str(exc))
        raise TransientError(f"github network error: {exc}") from exc

    if response.status_code in (401, 403):
        LOGGER.warning("github_search_public_repos_auth_failed", status=response.status_code)
        raise ChannelAuthError(f"github rejected request (HTTP {response.status_code})")
    if response.status_code == 429:
        LOGGER.warning("github_search_public_repos_rate_limited")
        raise RateLimited("github rate limit (HTTP 429)")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        LOGGER.warning("github_search_public_repos_http_error", status=response.status_code)
        raise TransientError(f"github HTTP {response.status_code}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise PermanentError(f"github returned non-JSON payload: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise PermanentError("github payload was not a JSON object")
    items = payload.get("items")
    if not isinstance(items, list):
        raise PermanentError("github payload missing 'items' list (schema changed?)")

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
