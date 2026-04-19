# Self-written, plan autosearch-0419-channels-scope-proxy.md § F101
from autosearch.core.models import SearchMode
from autosearch.core.pipeline import _initial_subquery_count


def test_initial_subquery_count_fast_returns_3() -> None:
    assert _initial_subquery_count(SearchMode.FAST) == 3


def test_initial_subquery_count_deep_returns_5() -> None:
    assert _initial_subquery_count(SearchMode.DEEP) == 5


def test_initial_subquery_count_comprehensive_returns_7() -> None:
    assert _initial_subquery_count(SearchMode.COMPREHENSIVE) == 7
