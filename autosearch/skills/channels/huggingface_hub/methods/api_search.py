# Self-written for task feat/huggingface-openalex-channels
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(
    component="channel",
    channel="huggingface_hub",
)

MAX_RESULTS = 10
HTTP_TIMEOUT = 15.0
MAX_SNIPPET_LENGTH = 300
BASE_URL = "https://huggingface.co/api/models"
USER_AGENT = "autosearch/1.0 (+https://github.com/0xmariowu/autosearch)"


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


def _format_count(value: object) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return "0"


def _tags_text(value: object) -> str:
    if not isinstance(value, list):
        return "-"

    tags = [str(tag).strip() for tag in value if str(tag).strip()]
    return ", ".join(tags[:5]) or "-"


def _build_snippet(item: Mapping[str, object]) -> str:
    snippet = (
        f"{str(item.get('pipeline_tag') or '').strip() or 'unknown-pipeline'}"
        f" \u00b7 {str(item.get('library_name') or '').strip() or 'unknown-library'}"
        f" \u00b7 {_format_count(item.get('downloads'))} downloads"
        f" \u00b7 {_format_count(item.get('likes'))} likes"
        f" \u00b7 tags: {_tags_text(item.get('tags'))}"
    )
    return _truncate_on_word_boundary(snippet, max_length=MAX_SNIPPET_LENGTH)


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    if item.get("private") is True:
        return None

    model_id = str(item.get("id") or "").strip()
    if not model_id:
        return None

    snippet = _build_snippet(item)
    return Evidence(
        url=f"https://huggingface.co/{model_id}",
        title=model_id,
        snippet=snippet,
        content=snippet,
        source_channel="huggingface_hub",
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
        "search": query.text,
        "limit": MAX_RESULTS,
    }
    try:
        if http_client is not None:
            response = await http_client.get(BASE_URL, params=params, headers=headers)
        else:
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            ) as client:
                response = await client.get(BASE_URL, params=params, headers=headers)

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("invalid items payload")
    except Exception as exc:
        LOGGER.warning("huggingface_hub_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue

        evidence = _to_evidence(item, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
