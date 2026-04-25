"""Baidu Tieba search channel; captcha safety pages are anti-scrape blocks."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx
import structlog

from autosearch.channels.base import TransientError, raise_as_channel_error
from autosearch.core.models import Evidence, SubQuery

LOGGER = structlog.get_logger(__name__).bind(component="channel", channel="tieba")

_SEARCH_URL = "https://tieba.baidu.com/f/search/res"
_HTTP_TIMEOUT = 15.0
_MAX_RESULTS = 10
_SAFETY_VERIFY_MARKERS = (
    "百度安全验证",
    "wappass.baidu.com",
    "safetyverify",
    "verify.baidu.com",
    "captcha",
    "安全验证",
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://tieba.baidu.com/",
}


async def search(query: SubQuery) -> list[Evidence]:
    try:
        return await _search_tieba(query.text)
    except Exception as exc:
        LOGGER.warning("tieba_search_failed", reason=str(exc))
        raise_as_channel_error(exc)


async def _search_tieba(query: str) -> list[Evidence]:
    params = {
        "qw": query,
        "rn": str(_MAX_RESULTS),
        "pn": "0",
        "sm": "1",
    }
    async with httpx.AsyncClient(
        timeout=_HTTP_TIMEOUT, headers=_HEADERS, follow_redirects=True
    ) as client:
        resp = await client.get(_SEARCH_URL, params=params)
        _raise_if_safety_verification_response(resp)
        resp.raise_for_status()

    return _parse_results(resp.text)


def _raise_if_safety_verification_response(resp: httpx.Response) -> None:
    if resp.status_code != 403:
        return
    if not _looks_like_safety_verification(resp):
        return
    raise TransientError("tieba anti-scrape safety verification returned HTTP 403")


def _looks_like_safety_verification(resp: httpx.Response) -> bool:
    body = resp.text.lower()
    if any(marker.lower() in body for marker in _SAFETY_VERIFY_MARKERS):
        return True

    content_type = resp.headers.get("content-type", "").lower()
    is_html = "html" in content_type or "<html" in body
    if not is_html:
        return False

    challenge_terms = ("验证码", "安全验证", "人机", "challenge", "captcha", "verify")
    return any(term in body for term in challenge_terms)


def _parse_results(html: str) -> list[Evidence]:
    """Extract post titles, URLs, and snippets from Tieba search result HTML."""
    results: list[Evidence] = []
    fetched_at = datetime.now(UTC)

    # Extract post links and titles from search results
    # Pattern: <a href="/p/XXXXXXX" title="...">...</a> or similar
    post_pattern = re.compile(
        r'<a[^>]+href="(/p/\d+)"[^>]*>([^<]{3,100})</a>',
        re.IGNORECASE,
    )
    seen_urls: set[str] = set()
    posts = post_pattern.findall(html)

    for path, title in posts:
        title = re.sub(r"<[^>]+>", "", title).strip()
        if not title or len(title) < 3:
            continue
        url = f"https://tieba.baidu.com{path}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        results.append(
            Evidence(
                title=title,
                url=url,
                snippet=None,
                score=0.6,
                source_channel="tieba",
                fetched_at=fetched_at,
            )
        )
        if len(results) >= _MAX_RESULTS:
            break

    return results
