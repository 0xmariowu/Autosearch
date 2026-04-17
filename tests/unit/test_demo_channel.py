# Self-written, plan v2.3 § 13.5
import inspect

import pytest

from autosearch.channels.demo import DemoChannel
from autosearch.core.models import Evidence, SubQuery


@pytest.mark.asyncio
async def test_demo_channel_search_matches_channel_contract() -> None:
    channel = DemoChannel()

    assert channel.name == "demo"
    assert inspect.iscoroutinefunction(channel.search)

    results = await channel.search(
        SubQuery(text="vector database tuning", rationale="Need demo evidence for ranking")
    )

    assert isinstance(results, list)
    assert results
    assert all(isinstance(item, Evidence) for item in results)


@pytest.mark.asyncio
async def test_demo_channel_returns_multiple_query_aware_sources() -> None:
    query = SubQuery(
        text="vector database tuning",
        rationale="Need multiple sources that retain lexical overlap for BM25",
    )

    results = await DemoChannel().search(query)

    assert len(results) >= 3
    assert all(
        query.text in evidence.title or query.text in (evidence.content or "")
        for evidence in results
    )
    assert len({evidence.source_channel for evidence in results}) >= 2
