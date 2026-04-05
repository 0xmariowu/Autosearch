from unittest.mock import patch

import pytest

from lib.phase2 import run_phase2


def _result(url: str, source: str) -> dict:
    return {
        "url": url,
        "title": "Title",
        "snippet": "Snippet",
        "source": source,
        "query": "agents",
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_run_phase2_with_subreddits() -> None:
    calls: list[tuple[str, str, int]] = []

    async def fake_search_subreddit(subreddit, query, max_results):
        calls.append((subreddit, query, max_results))
        return [_result(f"https://reddit.com/r/{subreddit}", "reddit")]

    with patch(
        "lib.phase2._search_subreddit",
        new=fake_search_subreddit,
    ):
        results = await run_phase2(
            {
                "subreddits": ["python", "machinelearning"],
                "x_handles": [],
                "authors": [],
            },
            "agent frameworks",
            max_per_entity=3,
        )

    assert calls == [
        ("python", "agent frameworks", 3),
        ("machinelearning", "agent frameworks", 3),
    ]
    assert len(results) == 2


@pytest.mark.asyncio
async def test_run_phase2_deduplicates() -> None:
    async def fake_sub(sub, q, n):
        return [_result("https://example.com/shared", "reddit")]

    async def fake_handle(handle, q, n):
        return [_result("https://example.com/shared", "twitter")]

    with (
        patch("lib.phase2._search_subreddit", new=fake_sub),
        patch("lib.phase2._search_x_handle", new=fake_handle),
    ):
        results = await run_phase2(
            {"subreddits": ["python"], "x_handles": ["alice"], "authors": []},
            "agent frameworks",
        )

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/shared"


@pytest.mark.asyncio
async def test_run_phase2_empty_entities() -> None:
    results = await run_phase2(
        {"subreddits": [], "x_handles": [], "authors": []},
        "agent frameworks",
    )
    assert results == []


@pytest.mark.asyncio
async def test_run_phase2_handles_errors() -> None:
    async def fake_sub_error(sub, q, n):
        raise RuntimeError("boom")

    async def fake_handle_ok(handle, q, n):
        return [_result("https://x.com/alice/status/1", "twitter")]

    with (
        patch("lib.phase2._search_subreddit", new=fake_sub_error),
        patch("lib.phase2._search_x_handle", new=fake_handle_ok),
    ):
        results = await run_phase2(
            {"subreddits": ["python"], "x_handles": ["alice"], "authors": []},
            "agent frameworks",
        )

    assert len(results) == 1
