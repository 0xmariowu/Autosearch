"""Tests for judge.py v2 — report quality dimensions.

Written test-first: these tests define the expected behavior of the new judge.
Implementation in lib/judge.py should make all tests pass.

New dimensions:
  rubric_pass_rate (0.30) — reads rubric-history.jsonl
  groundedness     (0.20) — delivery citation URLs vs evidence URLs
  relevant_yield   (0.15) — llm_relevant=true / total
  content_depth    (0.15) — extracted_content non-empty ratio
  source_diversity (0.10) — unique platforms WITH relevant results
  quantity         (0.10) — unique URLs / target
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.judge import (
    DEFAULT_WEIGHTS,
    score_results,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_evidence(tmp_path: Path, rows: list[dict]) -> Path:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    path = evidence_dir / "test-results.jsonl"
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return path


def write_state(tmp_path: Path, filename: str, payload: object) -> Path:
    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    path = state_dir / filename
    if isinstance(payload, list):
        # JSONL format
        path.write_text(
            "\n".join(json.dumps(item) for item in payload) + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_delivery(
    tmp_path: Path, content: str, filename: str = "test-report.html"
) -> Path:
    delivery_dir = tmp_path / "delivery"
    delivery_dir.mkdir(exist_ok=True)
    path = delivery_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


def make_result(
    *,
    url: str,
    query: str = "test query",
    source: str = "web-ddgs",
    title: str = "",
    snippet: str = "",
    metadata: dict | None = None,
) -> dict:
    return {
        "url": url,
        "query": query,
        "source": source,
        "title": title,
        "snippet": snippet,
        "metadata": metadata or {},
    }


# ---------------------------------------------------------------------------
# T1: New default weights
# ---------------------------------------------------------------------------


class TestNewWeights:
    def test_has_six_dimensions(self):
        assert len(DEFAULT_WEIGHTS) == 6

    def test_weights_sum_to_one(self):
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_expected_dimensions_present(self):
        expected = {
            "rubric_pass_rate",
            "groundedness",
            "relevant_yield",
            "content_depth",
            "source_diversity",
            "quantity",
        }
        assert set(DEFAULT_WEIGHTS.keys()) == expected

    def test_old_dimensions_removed(self):
        removed = {
            "latency",
            "freshness",
            "adoption",
            "knowledge_growth",
            "efficiency",
            "diversity",
        }
        for dim in removed:
            assert dim not in DEFAULT_WEIGHTS, f"{dim} should be removed"

    def test_rubric_pass_rate_highest_weight(self):
        max_dim = max(DEFAULT_WEIGHTS, key=DEFAULT_WEIGHTS.get)
        assert max_dim == "rubric_pass_rate"


# ---------------------------------------------------------------------------
# T2: rubric_pass_rate
# ---------------------------------------------------------------------------


class TestRubricPassRate:
    def test_no_rubric_history_file(self, tmp_path):
        evidence_path = write_evidence(tmp_path, [make_result(url="https://a.com")])
        payload = score_results([make_result(url="https://a.com")], str(evidence_path))
        # No rubric data = no quality evidence = 0.0
        assert payload["dimensions"]["rubric_pass_rate"] == pytest.approx(0.0)

    def test_reads_latest_entry(self, tmp_path):
        evidence_path = write_evidence(tmp_path, [make_result(url="https://a.com")])
        write_state(
            tmp_path,
            "rubric-history.jsonl",
            [
                {"topic": "old", "timestamp": "2026-04-01T00:00:00Z", "pass_rate": 0.5},
                {
                    "topic": "new",
                    "timestamp": "2026-04-06T00:00:00Z",
                    "pass_rate": 0.85,
                },
            ],
        )
        payload = score_results([make_result(url="https://a.com")], str(evidence_path))
        assert payload["dimensions"]["rubric_pass_rate"] == pytest.approx(0.85)

    def test_computes_from_passed_total(self, tmp_path):
        """If pass_rate field missing, compute from passed/total."""
        evidence_path = write_evidence(tmp_path, [make_result(url="https://a.com")])
        write_state(
            tmp_path,
            "rubric-history.jsonl",
            [
                {
                    "topic": "t",
                    "timestamp": "2026-04-06T00:00:00Z",
                    "passed": 18,
                    "total": 24,
                },
            ],
        )
        payload = score_results([make_result(url="https://a.com")], str(evidence_path))
        assert payload["dimensions"]["rubric_pass_rate"] == pytest.approx(0.75)

    def test_single_entry(self, tmp_path):
        evidence_path = write_evidence(tmp_path, [make_result(url="https://a.com")])
        write_state(
            tmp_path,
            "rubric-history.jsonl",
            [
                {"topic": "t", "timestamp": "2026-04-06T00:00:00Z", "pass_rate": 1.0},
            ],
        )
        payload = score_results([make_result(url="https://a.com")], str(evidence_path))
        assert payload["dimensions"]["rubric_pass_rate"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T3: groundedness
# ---------------------------------------------------------------------------


class TestGroundedness:
    def test_no_delivery_file(self, tmp_path):
        evidence_path = write_evidence(tmp_path, [make_result(url="https://a.com")])
        payload = score_results([make_result(url="https://a.com")], str(evidence_path))
        assert payload["dimensions"]["groundedness"] == pytest.approx(0.0)

    def test_no_citations_in_delivery(self, tmp_path):
        evidence_path = write_evidence(tmp_path, [make_result(url="https://a.com")])
        write_delivery(tmp_path, "<html><body>Report with no citations</body></html>")
        payload = score_results([make_result(url="https://a.com")], str(evidence_path))
        assert payload["dimensions"]["groundedness"] == pytest.approx(0.0)

    def test_all_citations_grounded(self, tmp_path):
        urls = ["https://example.com/1", "https://example.com/2"]
        evidence_path = write_evidence(
            tmp_path,
            [
                make_result(url=urls[0]),
                make_result(url=urls[1]),
            ],
        )
        html = """<html><body>
        <p>Finding <a href="#ref-1" class="cite">[1]</a> and <a href="#ref-2" class="cite">[2]</a></p>
        <ol>
        <li id="ref-1"><a href="https://example.com/1">Source 1</a></li>
        <li id="ref-2"><a href="https://example.com/2">Source 2</a></li>
        </ol>
        </body></html>"""
        write_delivery(tmp_path, html)
        payload = score_results([make_result(url=u) for u in urls], str(evidence_path))
        assert payload["dimensions"]["groundedness"] == pytest.approx(1.0)

    def test_partial_grounding(self, tmp_path):
        evidence_path = write_evidence(
            tmp_path,
            [
                make_result(url="https://example.com/1"),
                # url /2 NOT in evidence
            ],
        )
        html = """<html><body>
        <li id="ref-1"><a href="https://example.com/1">Source 1</a></li>
        <li id="ref-2"><a href="https://example.com/2">Source 2</a></li>
        </body></html>"""
        write_delivery(tmp_path, html)
        payload = score_results(
            [make_result(url="https://example.com/1")], str(evidence_path)
        )
        # 1 grounded out of 2 cited = 0.5
        assert payload["dimensions"]["groundedness"] == pytest.approx(0.5)

    def test_markdown_format(self, tmp_path):
        evidence_path = write_evidence(
            tmp_path,
            [
                make_result(url="https://example.com/1"),
            ],
        )
        md = "# Report\nSee [1](https://example.com/1) and [2](https://example.com/2)\n"
        write_delivery(tmp_path, md, filename="test-report.md")
        payload = score_results(
            [make_result(url="https://example.com/1")], str(evidence_path)
        )
        assert payload["dimensions"]["groundedness"] == pytest.approx(0.5)

    def test_plain_markdown_citation_format(self, tmp_path):
        """[N] Title — URL format used in AutoSearch .md deliveries."""
        evidence_path = write_evidence(
            tmp_path,
            [
                make_result(url="https://example.com/1"),
                make_result(url="https://example.com/2"),
            ],
        )
        md = (
            "# Report\nSome findings.\n\n"
            "## References\n"
            "[1] Source One — https://example.com/1\n"
            "[2] Source Two — https://example.com/2\n"
            "[3] Source Three — https://example.com/3\n"
        )
        write_delivery(tmp_path, md, filename="test-report.md")
        payload = score_results(
            [
                make_result(url="https://example.com/1"),
                make_result(url="https://example.com/2"),
            ],
            str(evidence_path),
        )
        # 2 grounded out of 3 cited
        assert payload["dimensions"]["groundedness"] == pytest.approx(2.0 / 3.0)


# ---------------------------------------------------------------------------
# T4: content_depth
# ---------------------------------------------------------------------------


class TestContentDepth:
    def test_all_empty_content(self, tmp_path):
        results = [make_result(url=f"https://a.com/{i}") for i in range(5)]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["content_depth"] == pytest.approx(0.0)

    def test_all_rich_content(self, tmp_path):
        results = [
            make_result(
                url=f"https://a.com/{i}",
                metadata={"extracted_content": "Full article text here..."},
            )
            for i in range(5)
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["content_depth"] == pytest.approx(1.0)

    def test_mixed_content(self, tmp_path):
        results = [
            make_result(
                url="https://a.com/1", metadata={"extracted_content": "Content"}
            ),
            make_result(
                url="https://a.com/2", metadata={"extracted_content": "Content"}
            ),
            make_result(
                url="https://a.com/3", metadata={"extracted_content": "Content"}
            ),
            make_result(url="https://a.com/4"),  # no content
            make_result(url="https://a.com/5"),  # no content
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["content_depth"] == pytest.approx(0.6)

    def test_empty_string_not_counted(self, tmp_path):
        results = [
            make_result(url="https://a.com/1", metadata={"extracted_content": ""}),
            make_result(
                url="https://a.com/2", metadata={"extracted_content": "Real content"}
            ),
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["content_depth"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T5: relevant_yield (replaces old relevance + efficiency)
# ---------------------------------------------------------------------------


class TestRelevantYield:
    def test_all_relevant(self, tmp_path):
        results = [
            make_result(url=f"https://a.com/{i}", metadata={"llm_relevant": True})
            for i in range(5)
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["relevant_yield"] == pytest.approx(1.0)

    def test_none_relevant(self, tmp_path):
        results = [
            make_result(url=f"https://a.com/{i}", metadata={"llm_relevant": False})
            for i in range(5)
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["relevant_yield"] == pytest.approx(0.0)

    def test_mixed_relevance(self, tmp_path):
        results = [
            make_result(url="https://a.com/1", metadata={"llm_relevant": True}),
            make_result(url="https://a.com/2", metadata={"llm_relevant": False}),
            make_result(url="https://a.com/3", metadata={"llm_relevant": True}),
            make_result(url="https://a.com/4", metadata={"llm_relevant": False}),
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["relevant_yield"] == pytest.approx(0.5)

    def test_fallback_keyword_match(self, tmp_path):
        """Without llm_relevant, falls back to keyword overlap."""
        results = [
            make_result(
                url="https://a.com/1", query="openai api", title="OpenAI API docs"
            ),
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["relevant_yield"] > 0.0


# ---------------------------------------------------------------------------
# T6: source_diversity (only platforms with relevant results count)
# ---------------------------------------------------------------------------


class TestSourceDiversity:
    def test_multiple_platforms_all_relevant(self, tmp_path):
        results = [
            make_result(
                url="https://a.com/1",
                source="github-repos",
                metadata={"llm_relevant": True},
            ),
            make_result(
                url="https://a.com/2",
                source="web-ddgs",
                metadata={"llm_relevant": True},
            ),
            make_result(
                url="https://a.com/3", source="arxiv", metadata={"llm_relevant": True}
            ),
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["source_diversity"] == pytest.approx(1.0)

    def test_many_platforms_but_only_one_relevant(self, tmp_path):
        """Searched 3 platforms, but only 1 had relevant results."""
        results = [
            make_result(
                url="https://a.com/1",
                source="github-repos",
                metadata={"llm_relevant": True},
            ),
            make_result(
                url="https://a.com/2",
                source="web-ddgs",
                metadata={"llm_relevant": False},
            ),
            make_result(
                url="https://a.com/3", source="arxiv", metadata={"llm_relevant": False}
            ),
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        # Only 1 platform contributed relevant results — low diversity
        assert payload["dimensions"]["source_diversity"] < 0.5

    def test_single_platform(self, tmp_path):
        results = [
            make_result(
                url=f"https://a.com/{i}",
                source="web-ddgs",
                metadata={"llm_relevant": True},
            )
            for i in range(5)
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert payload["dimensions"]["source_diversity"] == pytest.approx(0.0)

    def test_no_llm_relevant_falls_back(self, tmp_path):
        """Without llm_relevant field, count all platforms."""
        results = [
            make_result(url="https://a.com/1", source="github-repos"),
            make_result(url="https://a.com/2", source="web-ddgs"),
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        # Fallback: treat all as contributing
        assert payload["dimensions"]["source_diversity"] > 0.0


# ---------------------------------------------------------------------------
# T7: quantity (unchanged logic)
# ---------------------------------------------------------------------------


class TestQuantity:
    def test_below_target(self, tmp_path):
        results = [make_result(url=f"https://a.com/{i}") for i in range(15)]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path), target=30)
        assert payload["dimensions"]["quantity"] == pytest.approx(0.5)

    def test_at_target(self, tmp_path):
        results = [make_result(url=f"https://a.com/{i}") for i in range(30)]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path), target=30)
        assert payload["dimensions"]["quantity"] == pytest.approx(1.0)

    def test_above_target_capped(self, tmp_path):
        results = [make_result(url=f"https://a.com/{i}") for i in range(60)]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path), target=30)
        assert payload["dimensions"]["quantity"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# T8: score_results interface compatibility
# ---------------------------------------------------------------------------


class TestScoreResultsInterface:
    def test_returns_total_dimensions_meta(self, tmp_path):
        evidence_path = write_evidence(tmp_path, [])
        payload = score_results([], str(evidence_path))
        assert "total" in payload
        assert "dimensions" in payload
        assert "meta" in payload

    def test_total_in_range(self, tmp_path):
        results = [make_result(url=f"https://a.com/{i}") for i in range(10)]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        assert 0.0 <= payload["total"] <= 1.0

    def test_all_dimensions_in_range(self, tmp_path):
        results = [
            make_result(
                url=f"https://a.com/{i}",
                source=f"platform-{i}",
                metadata={"llm_relevant": True, "extracted_content": "text"},
            )
            for i in range(5)
        ]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        for name, value in payload["dimensions"].items():
            assert 0.0 <= value <= 1.0, f"{name} = {value} out of range"

    def test_empty_results_no_crash(self, tmp_path):
        evidence_path = write_evidence(tmp_path, [])
        payload = score_results([], str(evidence_path))
        assert payload["total"] == pytest.approx(0.0)
        for value in payload["dimensions"].values():
            assert 0.0 <= value <= 1.0

    def test_custom_weights(self, tmp_path):
        results = [make_result(url="https://a.com/1")]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(
            results, str(evidence_path), target=1, weights={"quantity": 1.0}
        )
        assert payload["dimensions"]["quantity"] == pytest.approx(1.0)
        assert payload["total"] == pytest.approx(1.0)

    def test_meta_fields(self, tmp_path):
        results = [make_result(url="https://a.com/1")]
        evidence_path = write_evidence(tmp_path, results)
        payload = score_results(results, str(evidence_path))
        meta = payload["meta"]
        assert "total_results" in meta
        assert "unique_urls" in meta
        assert "platforms" in meta
        assert "target" in meta
        assert "queries_used" in meta
