"""Xueqiu stock search + trending posts.

1:1 adapted from Agent-Reach agent_reach/channels/xueqiu.py.
Requires: XUEQIU_COOKIES env var (full cookie string with xq_a_token).
Run: autosearch login xueqiu
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from autosearch.core.models import Evidence, SubQuery

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_REFERER = "https://xueqiu.com/"
_TIMEOUT = 10

_cookie_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cookie_jar))
_cookies_loaded = False


def _load_cookies() -> bool:
    global _cookies_loaded
    if _cookies_loaded:
        return True
    cookie_str = os.environ.get("XUEQIU_COOKIES", "")
    if not cookie_str:
        return False
    for pair in cookie_str.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        name, _, value = pair.partition("=")
        cookie = http.cookiejar.Cookie(
            version=0,
            name=name.strip(),
            value=value.strip(),
            port=None,
            port_specified=False,
            domain=".xueqiu.com",
            domain_specified=True,
            domain_initial_dot=True,
            path="/",
            path_specified=True,
            secure=True,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
        )
        _cookie_jar.set_cookie(cookie)
    _cookies_loaded = True
    return True


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Referer": _REFERER})
    with _opener.open(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


async def search(query: SubQuery) -> list[Evidence]:
    if not _load_cookies():
        return []

    fetched_at = datetime.now(UTC)
    results: list[Evidence] = []

    # 1. Stock search (by ticker or name)
    try:
        data = _get_json(
            f"https://xueqiu.com/stock/search.json?code={urllib.parse.quote(query.text)}&size=5"
        )
        for s in (data.get("stocks") or [])[:5]:
            symbol = s.get("code", "")
            name = s.get("name", "")
            if not symbol:
                continue
            results.append(
                Evidence(
                    url=f"https://xueqiu.com/S/{symbol}",
                    title=f"{name} ({symbol})",
                    snippet=f"Exchange: {s.get('exchange', '')}",
                    source_channel="xueqiu:stock",
                    fetched_at=fetched_at,
                )
            )
    except Exception:
        pass

    # 2. Hot posts (financial discussion)
    try:
        data = _get_json(
            "https://xueqiu.com/v4/statuses/public_timeline_by_category.json"
            "?since_id=-1&max_id=-1&count=10&category=-1"
        )
        for item in (data.get("list") or [])[:8]:
            try:
                post = json.loads(item["data"]) if isinstance(item.get("data"), str) else {}
            except (json.JSONDecodeError, KeyError):
                continue
            user = post.get("user") or {}
            text = _strip_html(post.get("text") or post.get("description") or "")
            target = post.get("target", "")
            title = post.get("title") or text[:60] or "雪球热帖"
            if query.text.lower() not in title.lower() and query.text.lower() not in text.lower():
                continue
            results.append(
                Evidence(
                    url=f"https://xueqiu.com{target}" if target else "https://xueqiu.com",
                    title=title,
                    snippet=text[:300] if text else None,
                    source_channel=f"xueqiu:{user.get('screen_name', 'post')}",
                    fetched_at=fetched_at,
                )
            )
    except Exception:
        pass

    return results
