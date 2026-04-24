"""Bilibili direct API search — WBI signing (local or via AutoSearch signing Worker).

Priority:
  1. AUTOSEARCH_SIGNSRV_URL configured → use Worker for WBI signing
  2. Fallback → local Python WBI implementation (always available)
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import time
from collections.abc import Mapping
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="bilibili")

_NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/all/v2"

# Optional: AutoSearch signing Worker
_SIGNSRV_URL = os.environ.get("AUTOSEARCH_SIGNSRV_URL", "").rstrip("/")
_SERVICE_TOKEN = os.environ.get("AUTOSEARCH_SERVICE_TOKEN", "")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Bilibili WBI mixin key positions (public constant)
_MIXIN_KEY_ENC_TAB = [
    46,
    47,
    18,
    2,
    53,
    8,
    23,
    32,
    15,
    50,
    10,
    31,
    58,
    3,
    45,
    35,
    27,
    43,
    5,
    49,
    33,
    9,
    42,
    19,
    29,
    28,
    14,
    39,
    12,
    38,
    41,
    13,
    37,
    48,
    7,
    16,
    24,
    55,
    40,
    61,
    26,
    17,
    0,
    1,
    60,
    51,
    30,
    4,
    22,
    25,
    54,
    21,
    56,
    59,
    6,
    63,
    57,
    62,
    11,
    36,
    20,
    34,
    44,
    52,
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

MAX_SNIPPET_LENGTH = 300


async def _get_wbi_salt(client: httpx.AsyncClient) -> str:
    """Fetch Bilibili's public signing keys and compute salt."""
    r = await client.get(_NAV_URL, headers=_HEADERS, timeout=10)
    r.raise_for_status()
    wbi_img = r.json().get("data", {}).get("wbi_img", {})
    img_key = wbi_img.get("img_url", "").rsplit("/", 1)[-1].split(".")[0]
    sub_key = wbi_img.get("sub_url", "").rsplit("/", 1)[-1].split(".")[0]
    combined = img_key + sub_key
    return "".join(combined[i] for i in _MIXIN_KEY_ENC_TAB)[:32]


def _sign_params(params: dict[str, str], salt: str) -> dict[str, str]:
    """Add wts + w_rid signature to params."""
    params["wts"] = str(int(time.time()))
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    filtered = "".join(c for c in query if c not in "!'()*")
    params["w_rid"] = hashlib.md5(f"{filtered}{salt}".encode()).hexdigest()
    return params


def _clean(value: object) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(_HTML_TAG_RE.sub(" ", text).split())


def _truncate(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    candidate = text[:max_len]
    if not candidate[-1].isspace():
        shorter = candidate.rsplit(None, 1)[0]
        if shorter:
            candidate = shorter
    return f"{candidate.rstrip()}…"


def _to_evidence(item: Mapping[str, object], *, fetched_at: datetime) -> Evidence | None:
    bvid = str(item.get("bvid") or "").strip()
    arcurl = str(item.get("arcurl") or "").strip()
    url = (
        arcurl
        if arcurl.startswith("http")
        else (f"https://www.bilibili.com/video/{bvid}" if bvid else "")
    )
    if not url:
        return None

    title = _clean(item.get("title"))
    desc = _clean(item.get("description"))
    snippet = _truncate(desc, MAX_SNIPPET_LENGTH) or None
    author = _clean(item.get("author"))

    return Evidence(
        url=url,
        title=title or "Bilibili video",
        snippet=snippet,
        content=desc or snippet,
        source_channel=f"bilibili:video:{author}" if author else "bilibili:video",
        fetched_at=fetched_at,
    )


async def _sign_via_worker(keyword: str, client: httpx.AsyncClient) -> dict[str, str] | None:
    """Try signing via AutoSearch Worker. Returns signed params dict or None on failure."""
    if not _SIGNSRV_URL or not _SERVICE_TOKEN:
        return None
    try:
        r = await client.post(
            f"{_SIGNSRV_URL}/sign/bilibili",
            headers={
                "Authorization": f"Bearer {_SERVICE_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "keyword": keyword,
                "page": 1,
                "page_size": 10,
                "search_type": "video",
                "order": "totalrank",
            },
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("ok"):
                return data["params"]
    except Exception as exc:
        LOGGER.debug("bilibili_worker_sign_failed", reason=str(exc))
    return None


async def search(query: SubQuery, client: httpx.AsyncClient | None = None) -> list[Evidence]:
    """Search Bilibili directly using WBI signing — Worker first, local fallback."""
    _client = client or httpx.AsyncClient(timeout=20)
    _owns_client = client is None
    try:
        # Try Worker signing first (uses KV-cached salt, global PoP)
        params = await _sign_via_worker(query.text, _client)

        if params is None:
            # Local fallback: fetch WBI salt directly from Bilibili
            try:
                salt = await _get_wbi_salt(_client)
            except Exception as exc:
                # Bug 2 (fix-plan v8 follow-up): typed transient so the
                # registry fallback chain tries via_tikhub instead of
                # treating salt failure as "no results".
                from autosearch.channels.base import raise_as_channel_error

                LOGGER.warning("bilibili_wbi_salt_failed", reason=str(exc))
                raise_as_channel_error(exc)
            params = _sign_params(
                {
                    "keyword": query.text,
                    "page": "1",
                    "page_size": "10",
                    "search_type": "video",
                    "order": "totalrank",
                },
                salt,
            )

        try:
            r = await _client.get(_SEARCH_URL, params=params, headers=_HEADERS, timeout=15)
            r.raise_for_status()
        except Exception as exc:
            # Bug 2: same — typed error so fallback runs.
            from autosearch.channels.base import raise_as_channel_error

            LOGGER.warning("bilibili_direct_search_failed", reason=str(exc))
            raise_as_channel_error(exc)

        fetched_at = datetime.now(UTC)
        results = r.json().get("data", {}).get("result", [])
        evidence: list[Evidence] = []

        for group in results:
            if not isinstance(group, Mapping) or group.get("result_type") != "video":
                continue
            for item in group.get("data", []):
                if isinstance(item, Mapping):
                    ev = _to_evidence(item, fetched_at=fetched_at)
                    if ev:
                        evidence.append(ev)

        return evidence
    finally:
        if _owns_client:
            await _client.aclose()
