from lib.query_type import (
    detect_query_type,
    get_source_penalty,
    get_tiebreaker,
    is_source_in_tier,
)


def test_detect_comparison():
    assert detect_query_type("React vs Vue") == "comparison"


def test_detect_how_to():
    assert detect_query_type("how to deploy kubernetes") == "how_to"


def test_detect_product():
    assert detect_query_type("best alternative to Slack") == "product"


def test_detect_opinion():
    assert detect_query_type("is Claude worth it") == "opinion"


def test_detect_prediction():
    assert detect_query_type("election forecast 2028") == "prediction"


def test_detect_concept():
    assert detect_query_type("what is transformer architecture") == "concept"


def test_detect_default_breaking_news():
    assert detect_query_type("AI agents") == "breaking_news"


def test_priority_comparison_over_opinion():
    assert detect_query_type("is React better than Vue") == "comparison"


def test_get_source_penalty_web_ddgs():
    assert get_source_penalty("product", "web-ddgs") == 15.0


def test_get_source_penalty_non_web():
    assert get_source_penalty("product", "reddit") == 0.0


def test_get_tiebreaker_known():
    assert get_tiebreaker("comparison", "hn") == 1


def test_get_tiebreaker_unknown():
    assert get_tiebreaker("comparison", "unknown-source") == 99


def test_is_source_in_tier():
    assert is_source_in_tier("opinion", "reddit") is True
    assert is_source_in_tier("opinion", "some-random-source") is False
