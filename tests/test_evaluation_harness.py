import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation_harness import build_bundle, bundle_metrics


class EvaluationHarnessTests(unittest.TestCase):
    def test_build_bundle_applies_query_and_source_caps(self):
        harness = {
            "bundle_policy": {
                "per_query_cap": 1,
                "per_source_cap": 2,
                "per_domain_cap": 2,
            }
        }
        bundle = build_bundle(
            [],
            [
                {"title": "a1", "url": "https://a.com/1", "source": "github_issues", "query": "q1"},
                {"title": "a2", "url": "https://a.com/2", "source": "github_issues", "query": "q1"},
                {"title": "b1", "url": "https://b.com/1", "source": "github_issues", "query": "q2"},
            ],
            harness,
        )
        self.assertEqual(len(bundle), 2)
        self.assertEqual([item["title"] for item in bundle], ["a1", "b1"])

    def test_build_bundle_normalizes_legacy_records(self):
        harness = {
            "bundle_policy": {
                "per_query_cap": 5,
                "per_source_cap": 5,
                "per_domain_cap": 5,
            }
        }
        bundle = build_bundle(
            [],
            [
                {"title": "legacy", "url": "https://a.com/1", "body": "legacy body", "source": "searxng", "query": "q1"},
            ],
            harness,
        )
        self.assertEqual(bundle[0]["record_type"], "evidence")
        self.assertEqual(bundle[0]["content_type"], "web")

    def test_bundle_metrics_tracks_novelty_and_diversity(self):
        previous = [
            {"title": "old", "url": "https://x.com/1", "source": "github_repos", "query": "q1"},
        ]
        bundle = previous + [
            {"title": "new1", "url": "https://y.com/2", "source": "github_issues", "query": "q2"},
            {"title": "new2", "url": "https://z.com/3", "source": "huggingface_datasets", "query": "q3"},
        ]
        metrics = bundle_metrics(bundle, previous_bundle=previous)
        self.assertEqual(metrics["new_unique_urls"], 2)
        self.assertGreater(metrics["source_diversity"], 0.5)
        self.assertGreater(metrics["novelty_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
