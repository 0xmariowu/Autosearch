import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from query_dedup import semantic_query_similarity
from rerank.hybrid import rerank_hits
from rerank.lexical import dedup_hits, harmonic_position_bonus, normalize_url
from search_mesh.models import SearchHit


class RerankTests(unittest.TestCase):
    def _hit(self, *, title: str, url: str, snippet: str, provider: str = "searxng", score_hint: int = 0) -> SearchHit:
        return SearchHit.from_fields(
            url=url,
            title=title,
            snippet=snippet,
            source=provider,
            provider=provider,
            query="agent runtime",
            rank=1,
            backend=provider,
            score_hint=score_hint,
        )

    def test_normalize_url_removes_trailing_slash_and_query(self):
        self.assertEqual(
            normalize_url("https://example.com/a/?x=1"),
            "https://example.com/a",
        )

    def test_dedup_hits_removes_duplicate_urls(self):
        hits = [
            self._hit(title="A", url="https://example.com/a", snippet="one"),
            self._hit(title="A2", url="https://example.com/a/", snippet="two"),
        ]
        deduped = dedup_hits(hits)
        self.assertEqual(len(deduped), 1)

    def test_rerank_hits_prefers_more_relevant_result(self):
        hits = [
            self._hit(title="Random page", url="https://example.com/r", snippet="misc text"),
            self._hit(title="Agent runtime guide", url="https://example.com/a", snippet="agent runtime implementation"),
        ]
        ranked = rerank_hits("agent runtime", hits, rerank_profile="hybrid")
        self.assertEqual(ranked[0].title, "Agent runtime guide")

    def test_dedup_hits_can_cap_per_domain(self):
        hits = [
            self._hit(title="A", url="https://example.com/a", snippet="agent runtime"),
            self._hit(title="B", url="https://example.com/b", snippet="agent runtime"),
            self._hit(title="C", url="https://other.com/c", snippet="agent runtime"),
        ]
        deduped = dedup_hits(hits, max_per_domain=1)
        self.assertEqual([item.url for item in deduped], ["https://example.com/a", "https://other.com/c"])

    def test_harmonic_position_bonus_prefers_earlier_rank(self):
        self.assertGreater(harmonic_position_bonus(1), harmonic_position_bonus(5))

    def test_semantic_query_similarity_handles_rephrased_queries(self):
        left = "github issue release gate failure mode"
        right = "release gate issue failure modes on github"
        self.assertGreaterEqual(semantic_query_similarity(left, right), 0.7)


if __name__ == "__main__":
    unittest.main()
