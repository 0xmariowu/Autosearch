# Self-written, plan v2.3 § 13.5
from datetime import UTC, datetime
from urllib.parse import quote_plus

from autosearch.core.models import Evidence, SubQuery


class DemoChannel:
    languages: list[str] = ["en", "mixed"]

    def __init__(self, name: str = "demo") -> None:
        self.name = name

    async def search(self, query: SubQuery) -> list[Evidence]:
        now = datetime.now(UTC)
        encoded_query = quote_plus(query.text)
        return [
            Evidence(
                url=f"https://demo.example/arxiv/{encoded_query}",
                title=f"{query.text}: retrieval benchmark survey",
                snippet=(
                    f"An arXiv-style survey discussing {query.text} and why the benchmark "
                    "setup matters."
                ),
                content=(
                    f"This demo evidence models an academic paper about {query.text}. "
                    f"It uses the query text directly and explains the rationale: {query.rationale}."
                ),
                source_channel="demo:arxiv",
                fetched_at=now,
            ),
            Evidence(
                url=f"https://demo.example/blog/{encoded_query}",
                title=f"Practitioner notes on {query.text}",
                snippet=(
                    f"A blog post summarizing implementation tradeoffs for {query.text} in "
                    "production systems."
                ),
                content=(
                    f"This demo blog post covers {query.text} with operational details, rollout "
                    "pitfalls, and concrete observations that help lexical ranking."
                ),
                source_channel="demo:blog",
                fetched_at=now,
            ),
            Evidence(
                url=f"https://demo.example/github/{encoded_query}",
                title=f"{query.text} reference implementation",
                snippet=(
                    f"A repository README describing a sample implementation for {query.text} "
                    "with tests and examples."
                ),
                content=(
                    f"This demo GitHub evidence mentions {query.text} in code comments, README "
                    "notes, and issue discussions so reranking has strong term overlap."
                ),
                source_channel="demo:github",
                fetched_at=now,
            ),
            Evidence(
                url=f"https://demo.example/forum/{encoded_query}",
                title=f"Field report: teams evaluating {query.text}",
                snippet=(
                    f"A discussion thread where practitioners compare results for {query.text} "
                    "across several approaches."
                ),
                content=(
                    f"This demo forum thread explicitly repeats {query.text} while contrasting "
                    "evidence quality, confidence, and remaining gaps."
                ),
                source_channel="demo:forum",
                fetched_at=now,
            ),
        ]
