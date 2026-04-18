# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from datetime import UTC, datetime

from autosearch.core.models import Evidence, SubQuery


async def search(query: SubQuery) -> list[Evidence]:
    return [
        Evidence(
            url=f"https://example.com/stub-ok/{query.text.replace(' ', '-')}",
            title=f"stub_ok result for {query.text}",
            snippet=query.rationale,
            source_channel="stub_ok:echo",
            fetched_at=datetime.now(UTC),
        )
    ]
