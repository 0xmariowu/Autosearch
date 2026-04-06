"""Tests for judge.py utility functions and backward-compatible interfaces.

Dimension-specific tests are in test_judge_v2.py.
This file covers: load_results, parse_date, load_scoring_config, custom weights.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from lib.judge import (
    DEFAULT_WEIGHTS,
    load_default_weights,
    load_results,
    load_scoring_config,
    parse_date,
    score_results,
)


def write_evidence_jsonl(tmp_path: Path, rows: list[object] | None = None) -> Path:
    evidence_path = tmp_path / "evidence.jsonl"
    lines = [json.dumps(row) for row in (rows or [])]
    content = "\n".join(lines)
    if lines:
        content += "\n"
    evidence_path.write_text(content, encoding="utf-8")
    return evidence_path


def make_result(
    *,
    url: str,
    query: str = "openai api",
    source: str = "web",
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
# load_results
# ---------------------------------------------------------------------------


def test_load_results_empty_file(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path, [])
    assert load_results(evidence_path) == []


def test_load_results_malformed_lines(tmp_path):
    evidence_path = tmp_path / "evidence.jsonl"
    evidence_path.write_text(
        "\n".join(
            [
                json.dumps({"url": "https://example.com/1"}),
                "{not json}",
                json.dumps({"url": "https://example.com/2"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert load_results(evidence_path) == [
        {"url": "https://example.com/1"},
        {"url": "https://example.com/2"},
    ]


def test_load_results_non_dict_json(tmp_path):
    evidence_path = tmp_path / "evidence.jsonl"
    evidence_path.write_text(
        "\n".join(
            [
                json.dumps("text"),
                json.dumps(["list"]),
                json.dumps({"url": "https://example.com/1"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert load_results(evidence_path) == [{"url": "https://example.com/1"}]


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------


def test_parse_date_iso():
    parsed = parse_date("2025-03-15T10:00:00Z")
    assert parsed == dt.datetime(2025, 3, 15, 10, 0, tzinfo=dt.timezone.utc)


def test_parse_date_unix_timestamp():
    timestamp = 1700000000
    assert parse_date(timestamp) == dt.datetime.fromtimestamp(
        timestamp, tz=dt.timezone.utc
    )


def test_parse_date_invalid():
    assert parse_date("garbage") is None


# ---------------------------------------------------------------------------
# Scoring config
# ---------------------------------------------------------------------------


def test_load_scoring_config_no_file(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    config = load_scoring_config(str(evidence_path))
    assert config["dimension_weights"] == DEFAULT_WEIGHTS
    assert load_default_weights(str(evidence_path)) == DEFAULT_WEIGHTS


def test_custom_weights(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [make_result(url="https://example.com/1")]
    payload = score_results(
        results,
        str(evidence_path),
        target=1,
        weights={"quantity": 1.0},
    )
    assert payload["dimensions"]["quantity"] == pytest.approx(1.0)
    assert payload["total"] == pytest.approx(1.0)


def test_weight_sum_zero(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [make_result(url="https://example.com/1")]
    zero_weights = {name: 0.0 for name in DEFAULT_WEIGHTS}
    payload = score_results(results, str(evidence_path), weights=zero_weights)
    assert payload["total"] == 0.0
