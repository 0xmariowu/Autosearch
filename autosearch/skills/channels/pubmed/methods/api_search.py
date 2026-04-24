"""PubMed E-utilities search channel — free, no API key required."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="pubmed")

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_MAX_RESULTS = 10
_HTTP_TIMEOUT = 20.0


async def search(query: SubQuery) -> list[Evidence]:
    try:
        ids = await _esearch(query.text)
        if not ids:
            return []
        summaries = await _esummary(ids)
        return [_to_evidence(s) for s in summaries if s]
    except Exception as exc:
        LOGGER.warning("pubmed_search_failed", reason=str(exc))
        raise_as_channel_error(exc)


async def _esearch(query: str) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(_MAX_RESULTS),
        "retmode": "json",
        "sort": "relevance",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(_ESEARCH_URL, params=params)
        resp.raise_for_status()
    data = resp.json()
    return data.get("esearchresult", {}).get("idlist", [])


async def _esummary(ids: list[str]) -> list[dict]:
    params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "json",
    }
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        resp = await client.get(_ESUMMARY_URL, params=params)
        resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})
    uids = result.get("uids", ids)
    return [result.get(uid, {}) for uid in uids]


def _to_evidence(summary: dict) -> Evidence | None:
    uid = summary.get("uid") or summary.get("pmid") or ""
    title = summary.get("title") or ""
    if not title:
        return None
    authors = summary.get("authors") or []
    author_str = ", ".join(a.get("name", "") for a in authors[:3])
    source = summary.get("source") or ""
    doi = next(
        (
            art.get("value", "")
            for art in (summary.get("articleids") or [])
            if art.get("idtype") == "doi"
        ),
        "",
    )
    url = f"https://pubmed.ncbi.nlm.nih.gov/{uid}/" if uid else ""
    body_parts = [
        f"Journal: {source}" if source else "",
        f"Authors: {author_str}" if author_str else "",
    ]
    body = " | ".join(p for p in body_parts if p)
    if doi:
        body = f"{body} | DOI: {doi}" if body else f"DOI: {doi}"

    return Evidence(
        title=title,
        url=url,
        snippet=body,
        score=0.7,
        source_channel="pubmed",
        fetched_at=datetime.now(UTC),
    )
