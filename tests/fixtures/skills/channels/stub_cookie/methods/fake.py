# Self-written, plan autosearch-0418-channels-and-skills.md § F001
from datetime import UTC, datetime

from autosearch.core.models import Evidence, SubQuery


async def search(query: SubQuery) -> list[Evidence]:
    return [
        Evidence(
            url=f"https://example.com/stub-cookie/{query.text.replace(' ', '-')}",
            title=f"stub_cookie result for {query.text}",
            snippet=query.rationale,
            source_channel="stub_cookie:fake",
            fetched_at=datetime.now(UTC),
        )
    ]
