from __future__ import annotations

from datetime import UTC, datetime

import feedparser
import pytest

from autosearch.core.context_compression import compress_evidence
from autosearch.core.models import Evidence
from autosearch.skills.channels.bilibili.methods import via_tikhub as bilibili
from autosearch.skills.channels.google_news.methods import api_search as google_news
from autosearch.skills.channels.twitter.methods import via_tikhub as twitter
from autosearch.skills.channels.youtube.methods import data_api_v3 as youtube


FETCHED_AT = datetime(2026, 4, 25, 12, 0, tzinfo=UTC)


def _assert_published_at_survives_consolidation(
    evidence: Evidence,
    expected: datetime,
) -> None:
    report = compress_evidence([evidence.to_context_dict()], query=evidence.title, top_k=1)

    assert report["top_evidence"][0]["published_at"] == expected
    assert report["top_evidence"][0]["published_at"] != report["top_evidence"][0]["fetched_at"]


def test_google_news_pubdate_flows_through_consolidate_research() -> None:
    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>AI regulation passes EU</title>
      <link>https://news.google.com/rss/articles/abc</link>
      <pubDate>Mon, 15 Apr 2024 10:00:00 GMT</pubDate>
      <description>AI regulation passes EU</description>
      <source url="https://reuters.com">Reuters</source>
    </item>
  </channel>
</rss>
"""
    entry = feedparser.parse(rss).entries[0]
    evidence = google_news._to_evidence(entry, fetched_at=FETCHED_AT)

    assert evidence is not None
    _assert_published_at_survives_consolidation(
        evidence,
        datetime(2024, 4, 15, 10, 0, tzinfo=UTC),
    )


def test_youtube_published_at_flows_through_consolidate_research() -> None:
    evidence = youtube._to_evidence(
        {
            "id": {"videoId": "abc123"},
            "snippet": {
                "title": "MLX Tutorial for Apple Silicon",
                "description": "Learn to run LLMs on Apple Silicon with MLX.",
                "publishedAt": "2024-03-01T00:00:00Z",
            },
        },
        fetched_at=FETCHED_AT,
    )

    _assert_published_at_survives_consolidation(
        evidence,
        datetime(2024, 3, 1, 0, 0, tzinfo=UTC),
    )


def test_bilibili_pubdate_flows_through_consolidate_research() -> None:
    evidence = bilibili._to_video_evidence(
        {
            "bvid": "BV1abc123",
            "title": "Video title one",
            "description": "First description.",
            "author": "UP One",
            "pubdate": 1713546000,
        },
        fetched_at=FETCHED_AT,
    )

    assert evidence is not None
    _assert_published_at_survives_consolidation(
        evidence,
        datetime(2024, 4, 19, 17, 0, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("created_at", "expected"),
    [
        ("Thu Apr 23 10:00:00 +0000 2026", datetime(2026, 4, 23, 10, 0, tzinfo=UTC)),
    ],
)
def test_twitter_created_at_flows_through_consolidate_research(
    created_at: str,
    expected: datetime,
) -> None:
    evidence = twitter._to_evidence(
        {
            "tweet_id": "1234567890",
            "screen_name": "openai",
            "text": "OpenAI ships a new API update.",
            "created_at": created_at,
        },
        fetched_at=FETCHED_AT,
    )

    assert evidence is not None
    _assert_published_at_survives_consolidation(evidence, expected)
