"""XHS search via AutoSearch Signing Worker + XHS native API.

Requires:
  AUTOSEARCH_SIGNSRV_URL   → e.g. https://autosearch-signsrv.xxx.workers.dev
  AUTOSEARCH_SERVICE_TOKEN → as_xxx service token
  XHS_COOKIES              → full XHS cookie string: "a1=xxx; web_session=yyy; ..."
                             (also accepts XHS_A1_COOKIE for bare a1 — legacy)

Flow:
  1. POST Worker /sign/xhs with cookies + uri + data → X-s/X-t/X-s-common (local signing, no TikHub)
  2. POST XHS native API with signed headers + full cookies → search results
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
# Prefer full cookie string; fall back to bare a1 for legacy compatibility
_XHS_COOKIES = (
    os.environ.get("XHS_COOKIES")
    or os.environ.get("XIAOHONGSHU_COOKIES")
    or os.environ.get("XHS_A1_COOKIE", "")
)

_XHS_SEARCH_URL = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
_XHS_SEARCH_PATH = "/api/sns/web/v1/search/notes"

MAX_SNIPPET_LENGTH = 300


def _is_configured() -> bool:
    return bool(_SIGNSRV_URL and _SERVICE_TOKEN and _XHS_COOKIES)


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
                json={"uri": _XHS_SEARCH_PATH, "data": search_data, "cookies": _XHS_COOKIES},
                timeout=8,
            )
            sign_resp.raise_for_status()
            sign_data = sign_resp.json()
        except Exception as exc:
            # Bug 2 (fix-plan v8 follow-up): swallowing as [] hid signsrv
            # outages AND prevented base.py's fallback chain from trying
            # via_tikhub. Raise a typed error so the registry's fallback runs.
            from autosearch.channels.base import raise_as_channel_error

            LOGGER.warning("xhs_signsrv_failed", reason=str(exc))
            raise_as_channel_error(exc)

        if not sign_data.get("ok"):
            from autosearch.channels.base import TransientError

            LOGGER.warning("xhs_signsrv_error", error=sign_data.get("error"))
            raise TransientError(f"xhs signsrv error: {sign_data.get('error')}")

        # Step 2: Call XHS native API with signed headers
        xhs_headers = {
            "X-s": sign_data["X-s"],
            "X-t": str(sign_data["X-t"]),
            "X-s-common": sign_data["X-s-common"],
            "X-b3-traceid": sign_data["X-b3-traceid"],
            "Cookie": _XHS_COOKIES,
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
            # Bug 2: native XHS API failure → typed error so the fallback chain
            # tries via_tikhub instead of returning a fake empty result.
            from autosearch.channels.base import raise_as_channel_error

            LOGGER.warning("xhs_native_api_failed", reason=str(exc))
            raise_as_channel_error(exc)

        payload = xhs_resp.json()
        xhs_code = payload.get("code", 0)

        # code=300011: XHS account flagged. Surface as ChannelAuthError so the
        # user sees "your XHS account is restricted, run autosearch login xhs"
        # rather than a confusing empty result.
        if xhs_code == 300011:
            from autosearch.channels.base import ChannelAuthError

            LOGGER.warning(
                "xhs_account_restricted",
                reason="XHS account flagged (code=300011). Run 'autosearch login xhs' with a normal account.",
            )
            raise ChannelAuthError(
                "XHS account flagged (code=300011). "
                "Run 'autosearch login xhs' with a normal account."
            )

        outer = payload.get("data", {})
        inner = outer.get("data", {}) if isinstance(outer, Mapping) else {}
        items = inner.get("items", []) if isinstance(inner, Mapping) else []

        if not isinstance(items, list):
            return []

        # Empty results on a seemingly successful response → check if account is restricted
        if not items and xhs_code == 0:
            me_payload: Mapping[str, object] | None = None
            try:
                me_resp = await _client.get(
                    "https://edith.xiaohongshu.com/api/sns/web/v2/user/me",
                    headers={k: v for k, v in xhs_headers.items() if k not in ("Content-Type",)},
                    timeout=8,
                )
                me_payload = me_resp.json()
            except Exception:
                pass  # health check failure is non-fatal; fall through to empty list

            if isinstance(me_payload, Mapping) and me_payload.get("code") == 300011:
                from autosearch.channels.base import ChannelAuthError

                LOGGER.warning(
                    "xhs_account_restricted",
                    reason="XHS account flagged — search silently returns empty. Run 'autosearch login xhs' with a different account.",
                )
                raise ChannelAuthError(
                    "XHS account flagged (code=300011). "
                    "Run 'autosearch login xhs' with a different account."
                )

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
