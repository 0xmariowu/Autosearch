from __future__ import annotations

import asyncio
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
_COMMENT_FILLERS = ("I ", "You ", "This.", "Same", "Agreed", "Lol", "lol")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


async def enrich_reddit_items(
    results: list[dict], max_items: int = 3, timeout_total: float = 5.0
) -> None:
    try:
        reddit_results = [
            result for result in results if result.get("source") == "reddit"
        ]
        reddit_results.sort(
            key=lambda item: item.get("metadata", {}).get("composite_score", 0),
            reverse=True,
        )
        selected_results = reddit_results[:max_items]
        if not selected_results:
            return

        bail_event = asyncio.Event()
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [
                asyncio.create_task(_enrich_single(result, client, bail_event))
                for result in selected_results
            ]
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout_total,
                )
            except asyncio.TimeoutError:
                print(
                    f"[enrichment] timeout after {timeout_total}s",
                    file=sys.stderr,
                )
                for task in tasks:
                    if not task.done():
                        task.cancel()
                try:
                    await asyncio.gather(*tasks, return_exceptions=True)
                except Exception:
                    pass
    except Exception as exc:
        print(f"[enrichment] {exc}", file=sys.stderr)
        return


async def _enrich_via_scrapecreators(result: dict) -> bool:
    """Try enriching a Reddit post via ScrapeCreators. Returns True if successful."""
    try:
        from channels._engines.scrapecreators import fetch_reddit_comments

        comments = await fetch_reddit_comments(result["url"], max_comments=5)
        if not comments:
            return False

        metadata = result.setdefault("metadata", {})
        metadata["top_comments"] = comments
        metadata["comment_insights"] = _extract_comment_insights(
            [c.get("excerpt", "") for c in comments]
        )
        if comments:
            metadata["top_comment_score"] = comments[0].get("score", 0)
        return True
    except Exception:
        return False


async def _enrich_single(
    result: dict, client: httpx.AsyncClient, bail_event: asyncio.Event
) -> None:
    try:
        if bail_event.is_set():
            return

        # Try ScrapeCreators first (if API key set)
        if await _enrich_via_scrapecreators(result):
            return

        path = urlparse(result["url"]).path
        if not path:
            return

        try:
            response = await client.get(
                f"https://www.reddit.com{path}.json?raw_json=1",
                headers={"User-Agent": USER_AGENT},
            )
        except Exception:
            return

        if response.status_code == 429:
            bail_event.set()
            return
        if response.status_code == 403:
            print(
                "[enrichment] reddit .json blocked (403), skipping comment fetch",
                file=sys.stderr,
            )
            return
        if response.is_error:
            return

        try:
            data = response.json()
        except Exception:
            return

        if not isinstance(data, list) or len(data) < 2:
            return

        try:
            post = data[0]["data"]["children"][0]["data"]
            comment_nodes = data[1]["data"]["children"]
        except Exception:
            return

        upvote_ratio_value = post.get("upvote_ratio", 0.0)
        try:
            upvote_ratio = float(upvote_ratio_value)
        except (TypeError, ValueError):
            upvote_ratio = 0.0

        eligible_comments: list[tuple[int, dict[str, int | str], str]] = []
        for node in comment_nodes:
            if not isinstance(node, dict) or node.get("kind") != "t1":
                continue

            comment = node.get("data", {})
            if not isinstance(comment, dict):
                continue

            author = str(comment.get("author", "") or "")
            body = str(comment.get("body", "") or "")
            if author in {"[deleted]", "[removed]"}:
                continue

            stripped_body = body.strip()
            if stripped_body in {"[deleted]", "[removed]"}:
                continue

            try:
                score = int(comment.get("score", 0))
            except (TypeError, ValueError):
                continue
            if score < 1:
                continue

            created_utc = comment.get("created_utc")
            if not isinstance(created_utc, (int, float)):
                continue

            eligible_comments.append(
                (
                    score,
                    {
                        "score": score,
                        "author": author,
                        "excerpt": stripped_body[:200],
                        "date": datetime.fromtimestamp(
                            created_utc, tz=timezone.utc
                        ).isoformat(),
                    },
                    stripped_body,
                )
            )

        eligible_comments.sort(key=lambda item: item[0], reverse=True)
        eligible_comments = eligible_comments[:5]
        top_comments = [item[1] for item in eligible_comments]
        comment_insights = _extract_comment_insights(
            [item[2] for item in eligible_comments]
        )
        metadata = result.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            result["metadata"] = metadata

        metadata["upvote_ratio"] = upvote_ratio
        metadata["top_comments"] = top_comments
        metadata["comment_insights"] = comment_insights
    except Exception as exc:
        print(f"[enrichment] {exc}", file=sys.stderr)
        return


def _extract_comment_insights(comment_bodies: list[str]) -> list[str]:
    insights: list[str] = []
    seen: set[str] = set()

    for body in comment_bodies:
        text = body.strip()
        if not text:
            continue

        for sentence in _SENTENCE_SPLIT_RE.split(text):
            cleaned = sentence.strip()
            if len(cleaned) <= 30:
                continue
            if cleaned.startswith(_COMMENT_FILLERS):
                continue
            if cleaned in seen:
                continue

            seen.add(cleaned)
            insights.append(cleaned)
            if len(insights) >= 3:
                return insights

    return insights
