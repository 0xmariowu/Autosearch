from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="sec_edgar")

BASE_URL = "https://efts.sec.gov/LATEST/search-index"
HTTP_TIMEOUT = 15.0
USER_AGENT = "AutoSearch research-tool autosearch@0xmariowu.github.io"
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": USER_AGENT,
}


def _first_list_value(values: object) -> str | None:
    if not isinstance(values, list) or not values:
        return None

    value = str(values[0] or "").strip()
    return value or None


def _build_url(source: Mapping[str, object]) -> str | None:
    cik = _first_list_value(source.get("ciks"))
    adsh = str(source.get("adsh") or "").strip()
    if not cik or not adsh:
        return None

    try:
        cik_number = int(cik)
    except ValueError:
        return None

    adsh_no_dashes = adsh.replace("-", "")
    if not adsh_no_dashes:
        return None

    return f"https://www.sec.gov/Archives/edgar/data/{cik_number}/{adsh_no_dashes}/{adsh}-index.htm"


def _build_title(source: Mapping[str, object]) -> str:
    form = str(source.get("form") or "filing").strip() or "filing"
    company = _first_list_value(source.get("display_names"))
    if company:
        return f"{company} — {form}"
    return f"SEC filing · {form}"


def _build_snippet(source: Mapping[str, object]) -> str:
    form = str(source.get("form") or "filing").strip() or "filing"
    parts = [form]

    file_date = str(source.get("file_date") or "").strip()
    if file_date:
        parts.append(f"filed {file_date}")

    period_ending = str(source.get("period_ending") or "").strip()
    if period_ending:
        parts.append(f"period ending {period_ending}")

    return " · ".join(parts)


def _to_evidence(source: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    url = _build_url(source)
    if not url:
        return None

    snippet = _build_snippet(source)
    return Evidence(
        url=url,
        title=_build_title(source),
        snippet=snippet,
        content=snippet,
        source_channel="sec_edgar",
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
                params={"q": query.text},
                headers=REQUEST_HEADERS,
            )
        else:
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT,
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    BASE_URL,
                    params={"q": query.text},
                    headers=REQUEST_HEADERS,
                )

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("invalid payload")

        hits = payload.get("hits")
        if not isinstance(hits, Mapping):
            raise ValueError("invalid hits payload")

        items = hits.get("hits")
        if not isinstance(items, list):
            raise ValueError("invalid items payload")
    except Exception as exc:
        LOGGER.warning("sec_edgar_search_failed", reason=str(exc))
        return []

    fetched_at = datetime.now(UTC)
    evidences: list[Evidence] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue

        source = item.get("_source")
        if not isinstance(source, Mapping):
            continue

        evidence = _to_evidence(source, fetched_at=fetched_at)
        if evidence is not None:
            evidences.append(evidence)

    return evidences
