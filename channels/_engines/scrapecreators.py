from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import httpx

from lib.search_runner import DEFAULT_TIMEOUT, make_result

API_BASE = "https://api.scrapecreators.com/v1"


def _get_api_key() -> str:
    return os.getenv("SCRAPECREATORS_API_KEY", "").strip()


def _headers() -> dict[str, str]:
    return {"x-api-key": _get_api_key(), "Accept": "application/json"}


async def search_reddit(query: str, max_results: int = 10) -> list[dict]:
    """Search Reddit via ScrapeCreators. Returns [] if no API key."""
    if not _get_api_key():
        return []
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{API_BASE}/reddit/search",
                params={"query": query, "sort": "relevance", "timeframe": "month"},
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(posts, list):
                posts = posts.get("children", []) if isinstance(posts, dict) else []

            results: list[dict] = []
            for post in posts:
                post_data = post.get("data", post) if isinstance(post, dict) else {}
                permalink = post_data.get("permalink", "")
                title = post_data.get("title", "")
                if not permalink or not title:
                    continue
                url = (
                    f"https://www.reddit.com{permalink}"
                    if permalink.startswith("/")
                    else permalink
                )
                extra: dict = {
                    "subreddit": post_data.get("subreddit", ""),
                    "score": post_data.get("score", 0),
                    "num_comments": post_data.get("num_comments", 0),
                }
                created_utc = post_data.get("created_utc")
                if isinstance(created_utc, (int, float)):
                    extra["published_at"] = datetime.fromtimestamp(
                        created_utc, tz=timezone.utc
                    ).isoformat()
                results.append(
                    make_result(
                        url=url,
                        title=title,
                        snippet=(post_data.get("selftext", "") or "")[:500],
                        source="reddit",
                        query=query,
                        extra_metadata=extra,
                    )
                )
                if len(results) >= max_results:
                    break
            return results
    except Exception as exc:
        print(f"[scrapecreators] reddit search failed: {exc}", file=sys.stderr)
        return []


async def search_reddit_subreddit(
    subreddit: str, query: str, max_results: int = 10
) -> list[dict]:
    """Search within a specific subreddit via ScrapeCreators. Returns [] if no API key."""
    if not _get_api_key():
        return []
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{API_BASE}/reddit/subreddit/search",
                params={
                    "subreddit": subreddit,
                    "query": query,
                    "sort": "relevance",
                    "timeframe": "month",
                },
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(posts, list):
                posts = posts.get("children", []) if isinstance(posts, dict) else []

            results: list[dict] = []
            for post in posts:
                post_data = post.get("data", post) if isinstance(post, dict) else {}
                permalink = post_data.get("permalink", "")
                title = post_data.get("title", "")
                if not permalink or not title:
                    continue
                url = (
                    f"https://www.reddit.com{permalink}"
                    if permalink.startswith("/")
                    else permalink
                )
                extra: dict = {
                    "subreddit": post_data.get("subreddit", subreddit),
                    "score": post_data.get("score", 0),
                    "num_comments": post_data.get("num_comments", 0),
                }
                created_utc = post_data.get("created_utc")
                if isinstance(created_utc, (int, float)):
                    extra["published_at"] = datetime.fromtimestamp(
                        created_utc, tz=timezone.utc
                    ).isoformat()
                results.append(
                    make_result(
                        url=url,
                        title=title,
                        snippet=(post_data.get("selftext", "") or "")[:500],
                        source="reddit",
                        query=query,
                        extra_metadata=extra,
                    )
                )
                if len(results) >= max_results:
                    break
            return results
    except Exception as exc:
        print(
            f"[scrapecreators] reddit subreddit search failed: {exc}",
            file=sys.stderr,
        )
        return []


async def fetch_reddit_comments(post_url: str, max_comments: int = 10) -> list[dict]:
    """Fetch comments for a Reddit post via ScrapeCreators. Returns [] if no API key."""
    if not _get_api_key():
        return []
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{API_BASE}/reddit/post/comments",
                params={"url": post_url},
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            comments_raw = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(comments_raw, list):
                comments_raw = (
                    comments_raw.get("children", [])
                    if isinstance(comments_raw, dict)
                    else []
                )

            comments: list[dict] = []
            for node in comments_raw:
                comment = node.get("data", node) if isinstance(node, dict) else {}
                author = str(comment.get("author", "") or "")
                body = str(comment.get("body", "") or "").strip()
                if not body or author in {"[deleted]", "[removed]", "AutoModerator"}:
                    continue
                score = 0
                try:
                    score = int(comment.get("score", 0))
                except (TypeError, ValueError):
                    pass
                comments.append(
                    {
                        "score": score,
                        "author": author,
                        "excerpt": body[:200],
                    }
                )
                if len(comments) >= max_comments:
                    break
            comments.sort(key=lambda c: c["score"], reverse=True)
            return comments
    except Exception as exc:
        print(f"[scrapecreators] reddit comments failed: {exc}", file=sys.stderr)
        return []


async def search_twitter(query: str, max_results: int = 10) -> list[dict]:
    """Search Twitter via ScrapeCreators. Returns [] if no API key."""
    if not _get_api_key():
        return []
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.get(
                f"{API_BASE}/twitter/search/tweets",
                params={"query": query, "sort_by": "relevance"},
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            tweets = data.get("data", data) if isinstance(data, dict) else data
            if not isinstance(tweets, list):
                tweets = []

            results: list[dict] = []
            for tweet in tweets:
                text = str(tweet.get("text", "") or tweet.get("full_text", "") or "")
                tweet_id = str(tweet.get("id_str", "") or tweet.get("id", "") or "")
                author = str(
                    tweet.get("screen_name", "")
                    or tweet.get("user", {}).get("screen_name", "")
                    or ""
                )
                if not text or not tweet_id:
                    continue
                url = (
                    f"https://x.com/{author}/status/{tweet_id}"
                    if author
                    else f"https://x.com/i/status/{tweet_id}"
                )
                extra: dict = {
                    "likes": int(tweet.get("favorite_count", 0) or 0),
                    "reposts": int(tweet.get("retweet_count", 0) or 0),
                    "replies": int(tweet.get("reply_count", 0) or 0),
                    "author_handle": author,
                }
                created_at = tweet.get("created_at", "")
                if created_at:
                    extra["published_at"] = created_at
                results.append(
                    make_result(
                        url=url,
                        title=text[:200],
                        snippet=text[:500],
                        source="twitter",
                        query=query,
                        extra_metadata=extra,
                    )
                )
                if len(results) >= max_results:
                    break
            return results
    except Exception as exc:
        print(f"[scrapecreators] twitter search failed: {exc}", file=sys.stderr)
        return []
