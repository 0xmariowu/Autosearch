import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rerank.hybrid import rerank_hits
from rerank.lexical import dedup_hits, normalize_url
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


if __name__ == "__main__":
    unittest.main()
