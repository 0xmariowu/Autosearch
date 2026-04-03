import datetime as dt
import json
from pathlib import Path

import pytest

from lib.judge import (
    DEFAULT_WEIGHTS,
    NEUTRAL_DIMENSION_SCORE,
    load_default_weights,
    load_results,
    load_scoring_config,
    parse_date,
    score_adoption,
    score_knowledge_growth,
    score_latency,
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


def write_state_json(tmp_path: Path, filename: str, payload: dict) -> Path:
    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    path = state_dir / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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


def test_score_empty_results(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path, [])

    payload = score_results([], str(evidence_path))

    assert payload["total"] == pytest.approx(
        (
            DEFAULT_WEIGHTS["latency"]
            + DEFAULT_WEIGHTS["adoption"]
            + DEFAULT_WEIGHTS["knowledge_growth"]
        )
        * NEUTRAL_DIMENSION_SCORE
    )
    assert payload["dimensions"] == {
        "quantity": 0.0,
        "diversity": 0.0,
        "relevance": 0.0,
        "freshness": 0.0,
        "efficiency": 0.0,
        "latency": NEUTRAL_DIMENSION_SCORE,
        "adoption": NEUTRAL_DIMENSION_SCORE,
        "knowledge_growth": NEUTRAL_DIMENSION_SCORE,
    }


def test_score_single_result(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [make_result(url="https://example.com/1")]

    payload = score_results(results, str(evidence_path))

    assert payload["dimensions"]["diversity"] == 0.0


def test_score_multiple_sources(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [
        make_result(url="https://example.com/1", source="google"),
        make_result(url="https://example.com/2", source="reddit"),
        make_result(url="https://example.com/3", source="news"),
    ]

    payload = score_results(results, str(evidence_path))

    assert payload["dimensions"]["diversity"] > 0.0
    assert payload["dimensions"]["diversity"] == pytest.approx(1.0)


def test_relevance_keyword_match(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [
        make_result(
            url="https://example.com/1",
            query="openai roadmap",
            title="OpenAI shares product roadmap",
        )
    ]

    payload = score_results(results, str(evidence_path))

    assert payload["dimensions"]["relevance"] > 0.0


def test_relevance_llm_relevant_true(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [
        make_result(
            url="https://example.com/1",
            query="query words absent",
            title="Completely unrelated title",
            metadata={"llm_relevant": True},
        )
    ]

    payload = score_results(results, str(evidence_path))

    assert payload["dimensions"]["relevance"] == pytest.approx(1.0)


def test_relevance_llm_relevant_false(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [
        make_result(
            url="https://example.com/1",
            query="openai roadmap",
            title="OpenAI roadmap details",
            metadata={"llm_relevant": False},
        )
    ]

    payload = score_results(results, str(evidence_path))

    assert payload["dimensions"]["relevance"] == 0.0


def test_freshness_recent_dates(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    now = dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc)
    results = [
        make_result(
            url="https://example.com/1",
            metadata={"published_at": "2025-06-01T00:00:00Z"},
        )
    ]

    payload = score_results(results, str(evidence_path), now=now)

    assert payload["dimensions"]["freshness"] > 0.0
    assert payload["dimensions"]["freshness"] == pytest.approx(1.0)


def test_freshness_old_dates(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    now = dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc)
    results = [
        make_result(
            url="https://example.com/1",
            metadata={"published_at": "2024-12-01T00:00:00Z"},
        )
    ]

    payload = score_results(results, str(evidence_path), now=now)

    assert payload["dimensions"]["freshness"] == 0.0


def test_efficiency(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    results = [
        make_result(url=f"https://example.com/{index}", query="alpha")
        for index in range(4)
    ] + [
        make_result(url=f"https://example.org/{index}", query="beta")
        for index in range(4)
    ]

    payload = score_results(results, str(evidence_path))

    assert payload["meta"]["unique_urls"] == 8
    assert payload["meta"]["queries_used"] == 2
    assert payload["dimensions"]["efficiency"] == pytest.approx(1.0)


def test_score_latency_no_file(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)

    assert score_latency(str(evidence_path), 120.0) == NEUTRAL_DIMENSION_SCORE


def test_score_latency_with_timing(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    write_state_json(
        tmp_path,
        "timing.json",
        {
            "start_ts": "2025-03-15T10:00:00Z",
            "end_ts": "2025-03-15T10:00:30Z",
        },
    )

    assert score_latency(str(evidence_path), 120.0) == pytest.approx(0.75)


def test_score_latency_missing_fields(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    write_state_json(
        tmp_path,
        "timing.json",
        {"end_ts": "2025-03-15T10:00:30Z"},
    )

    assert score_latency(str(evidence_path), 120.0) == NEUTRAL_DIMENSION_SCORE


def test_score_adoption_no_file(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)

    assert score_adoption(str(evidence_path)) == NEUTRAL_DIMENSION_SCORE


def test_score_adoption_with_score(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    write_state_json(tmp_path, "adoption.json", {"score": 0.8})

    assert score_adoption(str(evidence_path)) == pytest.approx(0.8)


def test_score_knowledge_growth_no_file(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)

    assert score_knowledge_growth(str(evidence_path)) == NEUTRAL_DIMENSION_SCORE


def test_score_knowledge_growth_all_zero(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    write_state_json(
        tmp_path,
        "knowledge-growth.json",
        {
            "initial_entries": 0,
            "final_entries": 0,
            "initial_gaps": 0,
            "remaining_gaps": 0,
            "high_confidence": 0,
        },
    )

    assert score_knowledge_growth(str(evidence_path)) == NEUTRAL_DIMENSION_SCORE


def test_score_knowledge_growth_with_data(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    write_state_json(
        tmp_path,
        "knowledge-growth.json",
        {
            "initial_entries": 10,
            "final_entries": 20,
            "initial_gaps": 5,
            "remaining_gaps": 1,
            "high_confidence": 8,
        },
    )

    assert score_knowledge_growth(str(evidence_path)) == pytest.approx(0.71)


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


def test_load_scoring_config_no_file(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)

    config = load_scoring_config(str(evidence_path))

    assert config["dimension_weights"] == DEFAULT_WEIGHTS
    assert config["latency_budget_seconds"] == pytest.approx(120.0)
    assert load_default_weights(str(evidence_path)) == DEFAULT_WEIGHTS


def test_load_scoring_config_custom(tmp_path):
    evidence_path = write_evidence_jsonl(tmp_path)
    write_state_json(
        tmp_path,
        "config.json",
        {
            "scoring": {
                "dimension_weights": {"relevance": 0.5},
                "latency_budget_seconds": 45,
            }
        },
    )

    config = load_scoring_config(str(evidence_path))

    assert config["dimension_weights"]["relevance"] == pytest.approx(0.5)
    assert config["dimension_weights"]["quantity"] == pytest.approx(
        DEFAULT_WEIGHTS["quantity"]
    )
    assert config["latency_budget_seconds"] == pytest.approx(45.0)
