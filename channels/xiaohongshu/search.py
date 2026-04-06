"""Xiaohongshu search: Baidu Kaifa with optional cookie enrichment.

XHS search API needs X-s/X-t signature (not replicable without browser JS).
Search: Baidu Kaifa site:xiaohongshu.com (URL-filtered).
Content enrichment: with a1 cookie, fetch note detail SSR for full text.
Cookie: XHS_COOKIE env var → browser-cookie3.
"""

from __future__ import annotations

import json
import re
import sys

import httpx

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
_MAX_CONTENT_FETCH = 3


async def search(query: str, max_results: int = 10) -> list[dict]:
    from channels._engines.cookie_auth import get_cookies, has_cookies
    from channels._engines.ddgs import search_ddgs_site

    results = await search_ddgs_site(query, "xiaohongshu.com", max_results=max_results)

    cookies = get_cookies(".xiaohongshu.com", "XHS_COOKIE")
    if has_cookies(cookies, ["a1"]) and results:
        await _enrich_notes(results, cookies)

    return results


async def _enrich_notes(results: list[dict], cookies: dict[str, str]) -> None:
    from channels._engines.cookie_auth import cookie_header
    from lib.search_runner import DEFAULT_TIMEOUT

    targets: list[tuple[int, str]] = []
    for i, r in enumerate(results):
        note_id = _extract_note_id(r.get("url", ""))
        if note_id and len(targets) < _MAX_CONTENT_FETCH:
            targets.append((i, note_id))
    if not targets:
        return

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        for idx, note_id in targets:
            try:
                resp = await client.get(
                    f"https://www.xiaohongshu.com/explore/{note_id}",
                    headers={
                        "User-Agent": _UA,
                        "Cookie": cookie_header(cookies),
                        "Referer": "https://www.xiaohongshu.com/",
                    },
                    follow_redirects=True,
                )
                if resp.is_error:
                    continue
                content, meta = _parse_note_ssr(resp.text)
                if content:
                    results[idx].setdefault("metadata", {})["extracted_content"] = (
                        content
                    )
                if meta:
                    results[idx].setdefault("metadata", {}).update(meta)
            except Exception as exc:
                print(f"[xiaohongshu] note fetch: {exc}", file=sys.stderr)


def _parse_note_ssr(html: str) -> tuple[str, dict]:
    match = re.search(
        r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>", html, re.DOTALL
    )
    if not match:
        return "", {}
    raw = match.group(1).replace("undefined", "null")
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return "", {}

    ndm = state.get("note", {}).get("noteDetailMap", {})
    for detail in ndm.values():
        nd = detail.get("note")
        if not isinstance(nd, dict):
            continue
        title = nd.get("title", "")
        desc = nd.get("desc", "")
        if not title and not desc:
            continue

        content = f"{title}\n{desc}".strip()
        meta: dict = {}
        user = nd.get("user", {})
        if user.get("nickname"):
            meta["author"] = user["nickname"]
        interact = nd.get("interactInfo", {})
        for field, key in [
            ("likedCount", "likes"),
            ("collectedCount", "collected"),
            ("commentCount", "num_comments"),
        ]:
            val = interact.get(field)
            if val is not None:
                meta[key] = val
        return content[:3000] if len(content) > 50 else "", meta

    return "", {}


def _extract_note_id(url: str) -> str:
    match = re.search(r"(?:explore|item|discovery/item)/([a-f0-9]{24})", url)
    return match.group(1) if match else ""
