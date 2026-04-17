# Self-written, plan v2.3 § 13.5
import pytest

import autosearch.observability.cost as cost_module
from autosearch.observability.cost import CostTracker, estimate_tokens


def test_add_usage_returns_expected_cost_for_known_price_table() -> None:
    tracker = CostTracker()

    cost = tracker.add_usage("gpt-4o", input_tokens=1000, output_tokens=500)

    assert cost == pytest.approx(0.0125)


def test_total_sums_costs_across_multiple_models() -> None:
    tracker = CostTracker()

    tracker.add_usage("gpt-4o", input_tokens=1000, output_tokens=1000)
    tracker.add_usage("claude-3.5-sonnet", input_tokens=500, output_tokens=500)

    assert tracker.total() == pytest.approx(0.029)


def test_breakdown_returns_per_model_totals() -> None:
    tracker = CostTracker()

    tracker.add_usage("gpt-4o", input_tokens=100, output_tokens=200)
    tracker.add_usage("gpt-4o", input_tokens=50, output_tokens=25)
    tracker.add_usage("claude-code-local", input_tokens=200, output_tokens=200)

    breakdown = tracker.breakdown()

    assert set(breakdown) == {"gpt-4o", "claude-code-local"}
    assert breakdown["gpt-4o"]["input_tokens"] == 150
    assert breakdown["gpt-4o"]["output_tokens"] == 225
    assert breakdown["gpt-4o"]["cost"] == pytest.approx(0.004125)
    assert breakdown["claude-code-local"]["input_tokens"] == 200
    assert breakdown["claude-code-local"]["output_tokens"] == 200
    assert breakdown["claude-code-local"]["cost"] == pytest.approx(0.0)


def test_estimate_tokens_falls_back_when_tiktoken_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingTiktoken:
        @staticmethod
        def get_encoding(name: str) -> None:
            raise KeyError(name)

    monkeypatch.setattr(cost_module, "tiktoken", FailingTiktoken())

    estimated = estimate_tokens("one two three", model="cl100k_base")

    assert isinstance(estimated, int)
    assert estimated > 0
