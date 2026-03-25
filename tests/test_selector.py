import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from selector import evaluate_acceptance


class SelectorTests(unittest.TestCase):
    def test_selector_accepts_real_score_gain_with_novelty(self):
        decision = evaluate_acceptance(
            current_state={"score": 80, "accepted_findings": [{}] * 10, "dimension_scores": {"a": 10, "b": 10}},
            candidate_score=84,
            candidate_dimensions={"a": 12, "b": 12},
            candidate_metrics={
                "new_unique_urls": 3,
                "novelty_ratio": 0.2,
                "source_diversity": 0.4,
                "source_concentration": 0.4,
                "query_concentration": 0.4,
            },
            harness={
                "anti_cheat": {
                    "min_new_unique_urls": 1,
                    "min_novelty_ratio": 0.01,
                    "min_source_diversity": 0.15,
                    "max_source_concentration": 0.82,
                    "max_query_concentration": 0.70,
                }
            },
            candidate_finding_count=15,
        )
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["anti_cheat_warnings"], [])

    def test_selector_rejects_score_gain_without_new_information(self):
        decision = evaluate_acceptance(
            current_state={"score": 80, "accepted_findings": [{}] * 10, "dimension_scores": {"a": 10, "b": 10}},
            candidate_score=84,
            candidate_dimensions={"a": 12, "b": 12},
            candidate_metrics={
                "new_unique_urls": 0,
                "novelty_ratio": 0.0,
                "source_diversity": 0.1,
                "source_concentration": 0.95,
                "query_concentration": 0.9,
            },
            harness={
                "anti_cheat": {
                    "min_new_unique_urls": 1,
                    "min_novelty_ratio": 0.01,
                    "min_source_diversity": 0.15,
                    "max_source_concentration": 0.82,
                    "max_query_concentration": 0.70,
                }
            },
            candidate_finding_count=10,
        )
        self.assertFalse(decision["accepted"])
        self.assertIn("no_new_unique_urls", decision["anti_cheat_failures"])

    def test_selector_accepts_tie_with_new_information_and_only_soft_warnings(self):
        decision = evaluate_acceptance(
            current_state={
                "score": 82,
                "accepted_findings": [{}] * 30,
                "dimension_scores": {"a": 14, "b": 15, "c": 17, "d": 18, "e": 18},
            },
            candidate_score=82,
            candidate_dimensions={"a": 12, "b": 16, "c": 18, "d": 18, "e": 18},
            candidate_metrics={
                "new_unique_urls": 3,
                "novelty_ratio": 0.0833,
                "source_diversity": 0.1111,
                "source_concentration": 0.8,
                "query_concentration": 0.2778,
            },
            harness={
                "anti_cheat": {
                    "min_new_unique_urls": 1,
                    "min_novelty_ratio": 0.01,
                    "min_source_diversity": 0.15,
                    "max_source_concentration": 0.82,
                    "max_query_concentration": 0.70,
                }
            },
            candidate_finding_count=36,
            current_program={"provider_mix": ["github_repos", "github_issues", "twitter_xreach"]},
            candidate_program={"provider_mix": ["github_issues"], "sampling_policy": {"bundle_per_query_cap": 3}},
        )
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["anti_cheat_failures"], [])
        self.assertIn("source_diversity_too_low", decision["anti_cheat_warnings"])
        self.assertEqual(decision["reason"], "tie_broken_by_profile_novelty_or_program_with_warnings")
        self.assertTrue(decision["program_changed"])
        self.assertIn("provider_mix", decision["program_change_fields"])

    def test_selector_rejects_tie_without_new_urls_even_if_profile_improves(self):
        decision = evaluate_acceptance(
            current_state={
                "score": 82,
                "accepted_findings": [{}] * 30,
                "dimension_scores": {"a": 14, "b": 15, "c": 17, "d": 18, "e": 18},
            },
            candidate_score=82,
            candidate_dimensions={"a": 16, "b": 16, "c": 17, "d": 18, "e": 18},
            candidate_metrics={
                "new_unique_urls": 0,
                "novelty_ratio": 0.0,
                "source_diversity": 0.2,
                "source_concentration": 0.8,
                "query_concentration": 0.2,
            },
            harness={
                "anti_cheat": {
                    "min_new_unique_urls": 1,
                    "min_novelty_ratio": 0.01,
                    "min_source_diversity": 0.15,
                    "max_source_concentration": 0.82,
                    "max_query_concentration": 0.70,
                }
            },
            candidate_finding_count=36,
        )
        self.assertFalse(decision["accepted"])
        self.assertIn("no_new_unique_urls", decision["anti_cheat_failures"])

    def test_selector_accepts_tie_with_program_mutation_and_new_information(self):
        decision = evaluate_acceptance(
            current_state={
                "score": 82,
                "accepted_findings": [{}] * 20,
                "dimension_scores": {"a": 14, "b": 15},
            },
            candidate_score=82,
            candidate_dimensions={"a": 14, "b": 15},
            candidate_metrics={
                "new_unique_urls": 2,
                "novelty_ratio": 0.1,
                "source_diversity": 0.2,
                "source_concentration": 0.5,
                "query_concentration": 0.4,
            },
            harness={
                "anti_cheat": {
                    "min_new_unique_urls": 1,
                    "min_novelty_ratio": 0.01,
                    "min_source_diversity": 0.15,
                    "max_source_concentration": 0.82,
                    "max_query_concentration": 0.70,
                }
            },
            candidate_finding_count=20,
            current_program={"provider_mix": ["github_repos", "github_issues", "twitter_xreach"]},
            candidate_program={"provider_mix": ["github_issues"]},
        )
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["provider_specialization"], 2)


if __name__ == "__main__":
    unittest.main()
