"""XHS search via AutoSearch Signing Worker + XHS native API.

Requires:
  AUTOSEARCH_SIGNSRV_URL   → e.g. https://autosearch-signsrv.xxx.workers.dev
  AUTOSEARCH_SERVICE_TOKEN → as_xxx service token
  XHS_A1_COOKIE            → user's XHS a1 cookie value

Flow:
  1. POST Worker /sign/xhs with uri + data + a1 → X-s/X-t/X-s-common
  2. POST XHS native API with signed headers → search results
"""

from __future__ import annotations

import html
import os
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="xiaohongshu")

_SIGNSRV_URL = os.environ.get("AUTOSEARCH_SIGNSRV_URL", "").rstrip("/")
_SERVICE_TOKEN = os.environ.get("AUTOSEARCH_SERVICE_TOKEN", "")
_XHS_A1_COOKIE = os.environ.get("XHS_A1_COOKIE", "")

_XHS_SEARCH_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
_XHS_SEARCH_PATH = "/api/sns/web/v1/search/notes"

MAX_SNIPPET_LENGTH = 300


def _is_configured() -> bool:
    return bool(_SIGNSRV_URL and _SERVICE_TOKEN and _XHS_A1_COOKIE)


def _clean_text(value: object) -> str:
    return " ".join(html.unescape(str(value or "")).split())


def _truncate(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    candidate = text[:max_len]
    if candidate and not candidate[-1].isspace():
        shorter = candidate.rsplit(None, 1)[0]
        if shorter:
            candidate = shorter
    return f"{candidate.rstrip()}…"


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    note_id = str(item.get("id") or "").strip()
    if not note_id:
        return None

    xsec = str(item.get("xsecToken") or "").strip()
    url = (
        f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec}&xsec_source=pc_search"
        if xsec
        else f"https://www.xiaohongshu.com/explore/{note_id}"
    )

    note_card = item.get("noteCard")
    if isinstance(note_card, Mapping):
        title = _clean_text(note_card.get("displayTitle") or note_card.get("title"))
        user = note_card.get("user") or {}
        author = _clean_text(user.get("nickname") if isinstance(user, Mapping) else None)
        desc = _clean_text(note_card.get("desc"))
    else:
        title = _clean_text(item.get("title") or item.get("display_title"))
        author = ""
        desc = _clean_text(item.get("desc"))

    snippet = _truncate(desc, MAX_SNIPPET_LENGTH) or None

    return Evidence(
        url=url,
        title=title or author or "Xiaohongshu note",
        snippet=snippet,
        content=desc or snippet,
        source_channel=f"xiaohongshu:{author}" if author else "xiaohongshu:native",
        fetched_at=fetched_at,
    )


async def search(query: SubQuery, client: httpx.AsyncClient | None = None) -> list[Evidence]:
    """Search XHS via Signing Worker + native XHS API.

    Returns empty list if not configured (missing env vars) — caller falls through
    to via_tikhub fallback.
    """
    if not _is_configured():
        return []

    _client = client or httpx.AsyncClient(timeout=20)
    _owns_client = client is None

    try:
        search_data = {
            "keyword": query.text,
            "page": 1,
            "page_size": 20,
            "search_id": "",
            "sort": "general",
            "note_type": 0,
        }

        # Step 1: Get signing headers from Worker
        try:
            sign_resp = await _client.post(
                f"{_SIGNSRV_URL}/sign/xhs",
                headers={
                    "Authorization": f"Bearer {_SERVICE_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={"uri": _XHS_SEARCH_PATH, "data": search_data, "a1": _XHS_A1_COOKIE},
                timeout=8,
            )
            sign_resp.raise_for_status()
            sign_data = sign_resp.json()
        except Exception as exc:
            LOGGER.warning("xhs_signsrv_failed", reason=str(exc))
            return []

        if not sign_data.get("ok"):
            LOGGER.warning("xhs_signsrv_error", error=sign_data.get("error"))
            return []

        # Step 2: Call XHS native API with signed headers
        xhs_headers = {
            "X-s": sign_data["X-s"],
            "X-t": str(sign_data["X-t"]),
            "X-s-common": sign_data["X-s-common"],
            "X-b3-traceid": sign_data["X-b3-traceid"],
            "Cookie": f"a1={_XHS_A1_COOKIE}",
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.xiaohongshu.com/",
            "Origin": "https://www.xiaohongshu.com",
            "Accept": "application/json, text/plain, */*",
        }

        try:
            xhs_resp = await _client.post(
                _XHS_SEARCH_URL,
                headers=xhs_headers,
                json=search_data,
                timeout=15,
            )
            xhs_resp.raise_for_status()
        except Exception as exc:
            LOGGER.warning("xhs_native_api_failed", reason=str(exc))
            return []

        payload = xhs_resp.json()
        outer = payload.get("data", {})
        inner = outer.get("data", {}) if isinstance(outer, Mapping) else {}
        items = inner.get("items", []) if isinstance(inner, Mapping) else []

        if not isinstance(items, list):
            return []

        fetched_at = datetime.now(UTC)
        results: list[Evidence] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            ev = _to_evidence(item, fetched_at=fetched_at)
            if ev is not None:
                results.append(ev)

        return results

    finally:
        if _owns_client:
            await _client.aclose()
