from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
API_BASE = "https://x.com/i/api/graphql"
DEFAULT_QUERY_ID = "6AAys3t42mosm_yTI_QENg"
FALLBACK_QUERY_IDS = ["M1jEez78PEfVfbQLvlWMvQ", "5h0kNbk3ii97rmfY6CdgAA"]
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
_CACHE_TTL_SECONDS = 86400  # 24 hours
_CACHE_FILE: Path | None = None
_JS_BUNDLE_RE = re.compile(
    r'https://abs\.twimg\.com/responsive-web/client-web[^"\']+\.js'
)
_QUERY_ID_RE = re.compile(
    r'\{queryId:"([^"]+)"[^}]*operationName:"SearchTimeline"'
    r'|operationName:"SearchTimeline"[^}]*queryId:"([^"]+)"'
)


def _log_error(message: str, exc: Exception | None = None) -> None:
    if exc is None:
        print(f"[twitter-graphql] {message}", file=sys.stderr)
        return
    print(f"[twitter-graphql] {message}: {exc}", file=sys.stderr)


def _extract_cookie_pair(cookie_jar: object) -> tuple[str, str] | None:
    try:
        allowed_domains = {".twitter.com", "twitter.com", ".x.com", "x.com"}
        auth_token = ""
        ct0 = ""

        for cookie in cookie_jar:
            domain = (getattr(cookie, "domain", "") or "").lower()
            if domain not in allowed_domains:
                continue

            name = getattr(cookie, "name", "")
            value = getattr(cookie, "value", "")

            if name == "auth_token" and value:
                auth_token = value
            elif name == "ct0" and value:
                ct0 = value

            if auth_token and ct0:
                return auth_token, ct0
    except Exception as exc:
        _log_error("Failed to extract cookies", exc)

    return None


# --- Query ID refresh ---


def _get_cache_path() -> Path:
    global _CACHE_FILE
    if _CACHE_FILE is not None:
        return _CACHE_FILE
    root = Path(__file__).resolve().parent.parent.parent
    _CACHE_FILE = root / "state" / "twitter-query-ids.json"
    return _CACHE_FILE


def _load_cached_ids() -> list[str] | None:
    path = _get_cache_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        cached_at = data.get("cached_at", 0)
        import time

        if time.time() - cached_at > _CACHE_TTL_SECONDS:
            return None
        ids = data.get("query_ids", [])
        return ids if ids else None
    except Exception:
        return None


def _save_cached_ids(ids: list[str]) -> None:
    path = _get_cache_path()
    try:
        import time

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"query_ids": ids, "cached_at": time.time()}, indent=2) + "\n"
        )
    except OSError:
        pass


async def _fetch_query_ids_from_bundles() -> list[str]:
    try:
        timeout = httpx.Timeout(15.0, connect=10.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get("https://x.com")
            if resp.status_code != 200:
                return []

            bundle_urls = _JS_BUNDLE_RE.findall(resp.text)
            if not bundle_urls:
                return []

            # Only fetch a few bundles to avoid downloading megabytes
            for url in bundle_urls[:8]:
                try:
                    js_resp = await client.get(url)
                    if js_resp.status_code != 200:
                        continue
                    for match in _QUERY_ID_RE.finditer(js_resp.text):
                        query_id = match.group(1) or match.group(2)
                        if query_id:
                            print(
                                f"[twitter-graphql] refreshed query ID: {query_id}",
                                file=sys.stderr,
                            )
                            return [query_id]
                except Exception:
                    continue
    except Exception as exc:
        _log_error("Failed to fetch query IDs from bundles", exc)
    return []


async def get_query_ids() -> list[str]:
    cached = _load_cached_ids()
    if cached:
        return cached

    fresh = await _fetch_query_ids_from_bundles()
    if fresh:
        _save_cached_ids(fresh)
        return fresh

    # Fall back to hardcoded IDs
    return [DEFAULT_QUERY_ID, *FALLBACK_QUERY_IDS]


# --- Credential detection ---


def get_credentials() -> tuple[str, str] | None:
    try:
        auth_token = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
        ct0 = os.getenv("TWITTER_CT0", "").strip()
        if auth_token and ct0:
            print("[twitter] using env var credentials for GraphQL", file=sys.stderr)
            return auth_token, ct0

        try:
            import browser_cookie3  # type: ignore
        except ImportError:
            print(
                "[twitter] install browser-cookie3 for auto cookie extraction",
                file=sys.stderr,
            )
            return None

        browsers = [
            ("Safari", browser_cookie3.safari),
            ("Chrome", browser_cookie3.chrome),
            ("Firefox", browser_cookie3.firefox),
        ]

        for browser_name, loader in browsers:
            try:
                cookie_jar = loader()
                credentials = _extract_cookie_pair(cookie_jar)
                if credentials is not None:
                    print(
                        f"[twitter] using {browser_name} cookies for GraphQL",
                        file=sys.stderr,
                    )
                    return credentials
            except Exception as exc:
                _log_error(f"Failed to load {browser_name} cookies", exc)

        print(
            "[twitter] no X/Twitter session found in browsers, using DDGS fallback",
            file=sys.stderr,
        )
        return None
    except Exception as exc:
        _log_error("Failed to get credentials", exc)
        return None


def _build_features() -> dict:
    try:
        return {
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "articles_preview_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "rweb_video_timestamps_enabled": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "communities_web_enable_tweet_community_results_fetch": True,
            "interactive_text_enabled": True,
            "responsive_web_text_conversations_enabled": False,
        }
    except Exception as exc:
        _log_error("Failed to build features", exc)
        return {}


def _parse_tweets(response_json: dict) -> list[dict]:
    try:
        instructions = (
            response_json.get("data", {})
            .get("search_by_raw_query", {})
            .get("search_timeline", {})
            .get("timeline", {})
            .get("instructions", [])
        )
        if not isinstance(instructions, list):
            return []

        tweets: list[dict] = []

        for instruction in instructions:
            try:
                if instruction.get("type") != "TimelineAddEntries":
                    continue

                entries = instruction.get("entries", [])
                if not isinstance(entries, list):
                    continue

                for entry in entries:
                    try:
                        entry_id = entry.get("entryId", "")
                        if not re.match(r"^tweet-", entry_id):
                            continue

                        result = (
                            entry.get("content", {})
                            .get("itemContent", {})
                            .get("tweet_results", {})
                            .get("result", {})
                        )
                        if not isinstance(result, dict):
                            continue

                        if result.get("__typename") == "TweetWithVisibilityResults":
                            result = result.get("tweet", {})
                            if not isinstance(result, dict):
                                continue

                        legacy = result.get("legacy", {})
                        user_result = (
                            result.get("core", {})
                            .get("user_results", {})
                            .get("result", {})
                        )
                        user_legacy = user_result.get("legacy", {})

                        if not isinstance(legacy, dict) or not isinstance(
                            user_legacy, dict
                        ):
                            continue

                        rest_id = str(result.get("rest_id", "") or "").strip()
                        full_text = str(legacy.get("full_text", "") or "")
                        author_handle = str(
                            user_legacy.get("screen_name", "") or ""
                        ).strip()
                        author_handle = re.sub(r"^@", "", author_handle)
                        author_handle = re.sub(r"[^A-Za-z0-9_]", "", author_handle)

                        if not rest_id or not full_text or not author_handle:
                            continue

                        created_at_raw = str(legacy.get("created_at", "") or "").strip()
                        if not created_at_raw:
                            continue

                        try:
                            created_dt = datetime.strptime(
                                created_at_raw, "%a %b %d %H:%M:%S %z %Y"
                            )
                            created_at_iso = (
                                created_dt.astimezone(timezone.utc)
                                .isoformat()
                                .replace("+00:00", "Z")
                            )
                        except Exception as exc:
                            _log_error("Failed to parse tweet timestamp", exc)
                            continue

                        _quotes = int(legacy.get("quote_count", 0) or 0)

                        tweets.append(
                            {
                                "text": full_text,
                                "url": f"https://x.com/{author_handle}/status/{rest_id}",
                                "author_handle": author_handle,
                                "likes": int(legacy.get("favorite_count", 0) or 0),
                                "reposts": int(legacy.get("retweet_count", 0) or 0),
                                "replies": int(legacy.get("reply_count", 0) or 0),
                                "created_at": created_at_iso,
                            }
                        )
                    except Exception as exc:
                        _log_error("Failed to parse tweet entry", exc)
                        continue
            except Exception as exc:
                _log_error("Failed to parse timeline instruction", exc)
                continue

        return tweets
    except Exception as exc:
        _log_error("Failed to parse GraphQL response", exc)
        return []


async def search_graphql(query: str, max_results: int = 20) -> list[dict]:
    try:
        credentials = get_credentials()
        if credentials is None:
            return []

        auth_token, ct0 = credentials
        await asyncio.sleep(0)

        variables = {
            "rawQuery": query,
            "count": min(max_results, 20),
            "querySource": "typed_query",
            "product": "Latest",
        }
        features = _build_features()
        query_ids = await get_query_ids()

        headers = {
            "Authorization": f"Bearer {BEARER_TOKEN}",
            "X-Csrf-Token": ct0,
            "Cookie": f"auth_token={auth_token}; ct0={ct0}",
            "User-Agent": USER_AGENT,
            "X-Twitter-Auth-Type": "OAuth2Session",
            "X-Twitter-Active-User": "yes",
            "origin": "https://x.com",
            "referer": "https://x.com/",
            "X-Client-Transaction-Id": uuid.uuid4().hex,
        }

        timeout = httpx.Timeout(20.0, connect=10.0)

        async with httpx.AsyncClient(headers=headers, timeout=timeout) as client:
            for index, query_id in enumerate(query_ids):
                try:
                    url = f"{API_BASE}/{query_id}/SearchTimeline"
                    response = await client.get(
                        url,
                        params={
                            "variables": json.dumps(variables, separators=(",", ":")),
                            "features": json.dumps(features, separators=(",", ":")),
                        },
                    )

                    if response.status_code == 404 and index < len(query_ids) - 1:
                        await asyncio.sleep(0)
                        continue

                    if response.status_code != 200:
                        _log_error(
                            f"SearchTimeline request failed with status {response.status_code}"
                        )
                        return []

                    try:
                        response_json = response.json()
                    except Exception as exc:
                        _log_error("Failed to decode GraphQL response JSON", exc)
                        return []

                    parsed = _parse_tweets(response_json)
                    if not parsed:
                        return []
                    return parsed[:max_results]
                except Exception as exc:
                    _log_error("GraphQL request failed", exc)
                    return []

        return []
    except Exception as exc:
        _log_error("search_graphql failed", exc)
        return []
