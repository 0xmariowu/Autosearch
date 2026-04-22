"""Tests for F010 workflow skill core modules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from autosearch.core.context_retention_policy import trim_to_budget
from autosearch.core.graph_search_plan import SearchGraph, SubTask, get_parallel_batches
from autosearch.core.perspective_questioning import SubQuestion, generate_perspectives
from autosearch.core.recent_signal_fusion import filter_recent
from autosearch.core.trace_harvest import extract_winning_patterns


# --- trace_harvest ---


def test_extract_winning_pattern_high_score():
    trace = {
        "channel": "arxiv",
        "query": "LLM eval",
        "count_returned": 8,
        "count_total": 10,
        "outcome": "success",
    }
    patterns = extract_winning_patterns(trace)
    assert len(patterns) == 1
    assert patterns[0].channel == "arxiv"
    assert patterns[0].score == pytest.approx(0.8)


def test_extract_winning_pattern_low_score_excluded():
    trace = {
        "channel": "arxiv",
        "query": "LLM eval",
        "count_returned": 2,
        "count_total": 10,
        "outcome": "success",
    }
    assert extract_winning_patterns(trace) == []


def test_extract_winning_pattern_error_excluded():
    trace = {
        "channel": "arxiv",
        "query": "LLM eval",
        "count_returned": 10,
        "count_total": 10,
        "outcome": "error",
    }
    assert extract_winning_patterns(trace) == []


def test_extract_winning_pattern_zero_total():
    trace = {
        "channel": "arxiv",
        "query": "test",
        "count_returned": 0,
        "count_total": 0,
        "outcome": "success",
    }
    assert extract_winning_patterns(trace) == []


# --- perspective_questioning ---


def test_generate_perspectives_default_n():
    subs = generate_perspectives("AI coding tools")
    assert len(subs) == 4
    viewpoints = [s.viewpoint for s in subs]
    assert viewpoints == ["user", "expert", "critic", "competitor"]


def test_generate_perspectives_n_2():
    subs = generate_perspectives("AI coding tools", n=2)
    assert len(subs) == 2
    assert subs[0].viewpoint == "user"
    assert subs[1].viewpoint == "expert"


def test_generate_perspectives_n_clamped():
    subs = generate_perspectives("topic", n=99)
    assert len(subs) == 4  # clamped to max viewpoints


def test_generate_perspectives_empty_topic():
    assert generate_perspectives("") == []


def test_generate_perspectives_has_viewpoint_field():
    subs = generate_perspectives("test", n=1)
    assert isinstance(subs[0], SubQuestion)
    assert subs[0].viewpoint == "user"
    assert "test" in subs[0].question


# --- graph_search_plan ---


def test_get_parallel_batches_simple_chain():
    nodes = [
        SubTask(id="A", description="", depends_on=[]),
        SubTask(id="B", description="", depends_on=["A"]),
        SubTask(id="C", description="", depends_on=["B"]),
    ]
    batches = get_parallel_batches(SearchGraph(nodes=nodes))
    assert batches == [["A"], ["B"], ["C"]]


def test_get_parallel_batches_diamond():
    # A → B, A → C, B+C → D
    nodes = [
        SubTask(id="A", description="", depends_on=[]),
        SubTask(id="B", description="", depends_on=["A"]),
        SubTask(id="C", description="", depends_on=["A"]),
        SubTask(id="D", description="", depends_on=["B", "C"]),
    ]
    batches = get_parallel_batches(SearchGraph(nodes=nodes))
    assert batches[0] == ["A"]
    assert sorted(batches[1]) == ["B", "C"]
    assert batches[2] == ["D"]


def test_get_parallel_batches_no_deps():
    nodes = [SubTask(id="A", description=""), SubTask(id="B", description="")]
    batches = get_parallel_batches(SearchGraph(nodes=nodes))
    assert len(batches) == 1
    assert sorted(batches[0]) == ["A", "B"]


def test_get_parallel_batches_cycle_raises():
    nodes = [
        SubTask(id="A", description="", depends_on=["B"]),
        SubTask(id="B", description="", depends_on=["A"]),
    ]
    with pytest.raises(ValueError, match="cycle"):
        get_parallel_batches(SearchGraph(nodes=nodes))


def test_get_parallel_batches_unknown_dep_raises():
    nodes = [SubTask(id="A", description="", depends_on=["UNKNOWN"])]
    with pytest.raises(ValueError, match="unknown"):
        get_parallel_batches(SearchGraph(nodes=nodes))


# --- recent_signal_fusion ---


def _item(days_ago: int, score: float = 1.0) -> dict:
    dt = datetime.now(UTC) - timedelta(days=days_ago)
    return {"title": f"item-{days_ago}d", "date": dt.isoformat(), "score": score}


def test_filter_recent_keeps_new():
    items = [_item(1), _item(5), _item(40)]
    result = filter_recent(items, days=30)
    assert len(result) == 2
    assert all("40d" not in r["title"] for r in result)


def test_filter_recent_sorted_newest_first():
    items = [_item(10), _item(2), _item(7)]
    result = filter_recent(items, days=30)
    ages = [int(r["title"].split("-")[1].rstrip("d")) for r in result]
    assert ages == sorted(ages)


def test_filter_recent_excludes_no_date():
    items = [{"title": "no-date", "score": 1.0}, _item(1)]
    result = filter_recent(items, days=7)
    assert len(result) == 1
    assert result[0]["title"] == "item-1d"


def test_filter_recent_empty():
    assert filter_recent([], days=30) == []


# --- context_retention_policy ---


def test_trim_to_budget_keeps_high_score_first():
    items = [
        {"title": "low", "score": 0.1, "body": "x" * 100},
        {"title": "high", "score": 0.9, "body": "x" * 100},
    ]
    # each item is ~35 tokens (len(str(item))//4); budget=40 fits one, not two
    result = trim_to_budget(items, token_budget=40)
    assert len(result) == 1
    assert result[0]["title"] == "high"


def test_trim_to_budget_zero_budget():
    items = [{"title": "a", "score": 1.0}]
    assert trim_to_budget(items, token_budget=0) == []


def test_trim_to_budget_fits_all():
    items = [{"title": "a", "score": 1.0}, {"title": "b", "score": 0.5}]
    result = trim_to_budget(items, token_budget=10000)
    assert len(result) == 2


def test_trim_to_budget_empty():
    assert trim_to_budget([], token_budget=1000) == []
