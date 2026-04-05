import datetime

import pytest

from lib.scoring import (
    freshness_score,
    normalize_engagement_scores,
    raw_engagement,
    score_results,
    semantic_score,
)


def _make_result(
    source="reddit", title="Test", snippet="test snippet", score=0, **meta
):
    return {
        "url": f"https://example.com/{id(meta)}",
        "title": title,
        "snippet": snippet,
        "source": source,
        "query": "test",
        "metadata": {"score": score, **meta},
    }


def test_score_results_adds_composite_score():
    results = [_make_result(title="AI agents", snippet="latest AI agents news")]

    score_results(results, "AI agents")

    assert "composite_score" in results[0]["metadata"]


def test_composite_score_range():
    today = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results = [
        _make_result(title="AI agents", score=100, published_at=today),
        _make_result(
            title="cooking recipes", score=0, published_at="2020-01-01T00:00:00+00:00"
        ),
    ]

    score_results(results, "AI agents")

    for result in results:
        composite_score = result["metadata"]["composite_score"]
        assert isinstance(composite_score, int)
        assert 0 <= composite_score <= 100


def test_results_sorted_by_score():
    today = datetime.datetime.now(datetime.timezone.utc).isoformat()
    old_date = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=200)
    ).isoformat()
    results = [
        _make_result(title="cooking recipes", score=1, published_at=old_date),
        _make_result(title="AI agents", score=100, published_at=today),
        _make_result(title="AI agents", score=10, published_at=old_date),
    ]

    score_results(results, "AI agents")

    scores = [result["metadata"]["composite_score"] for result in results]
    assert scores == sorted(scores, reverse=True)


def test_semantic_score_exact_match():
    result = _make_result(title="AI agents framework", snippet="")

    score = semantic_score("AI agents", result)

    assert score > 0.5


def test_semantic_score_no_overlap():
    result = _make_result(title="cooking recipes", snippet="")

    assert semantic_score("AI agents", result) == 0.0


def test_freshness_score_recent():
    result = _make_result(
        published_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )

    score = freshness_score(result)

    assert score == pytest.approx(1.0, abs=0.01)


def test_freshness_score_old():
    result = _make_result(
        published_at=(
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=200)
        ).isoformat()
    )

    assert freshness_score(result) == 0.0


def test_freshness_score_missing_date():
    result = _make_result()

    assert freshness_score(result) == 0.5


def test_normalize_engagement_single_item():
    results = [_make_result(source="reddit", score=42)]

    normalize_engagement_scores(results)

    assert results[0]["engagement_score"] == 0.5


def test_normalize_engagement_range():
    results = [
        _make_result(source="reddit", score=1, num_comments=0),
        _make_result(source="reddit", score=100, num_comments=50),
    ]

    normalize_engagement_scores(results)

    assert results[0]["engagement_score"] == pytest.approx(0.0)
    assert results[1]["engagement_score"] == pytest.approx(1.0)


def test_raw_engagement_reddit():
    value = raw_engagement(
        "reddit",
        {
            "score": 100,
            "num_comments": 50,
            "upvote_ratio": 0.9,
            "top_comment_score": 10,
        },
    )

    assert isinstance(value, float)
    assert value > 0.0
