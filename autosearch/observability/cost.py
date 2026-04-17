# Source: gpt-researcher/gpt_researcher/utils/costs.py:L1-L51 (adapted)
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import tiktoken
except ImportError:  # pragma: no cover - exercised via fallback path
    tiktoken = None

_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "claude-3.5-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "claude-3-5-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "claude-code-local": {"input_per_1k": 0.0, "output_per_1k": 0.0},
    "gemini-2.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.01},
    "gpt-4o": {"input_per_1k": 0.005, "output_per_1k": 0.015},
}


def estimate_tokens(text: str, model: str = "cl100k_base") -> int:
    if not text:
        return 0

    if tiktoken is not None:
        try:
            encoding = tiktoken.get_encoding(model)
        except Exception:
            pass
        else:
            return len(encoding.encode(text))

    return max(len(text.split()), 1)


class CostTracker:
    def __init__(
        self,
        pricing: Mapping[str, Mapping[str, float]] | None = None,
        config_env_var: str = "AUTOSEARCH_COST_CONFIG",
    ) -> None:
        self._pricing = {model: price.copy() for model, price in _DEFAULT_PRICING.items()}
        self._pricing.update(self._load_config_from_env(config_env_var))
        if pricing is not None:
            self._pricing.update(_normalize_pricing(pricing))
        self._running_total = 0.0
        self._model_totals: dict[str, dict[str, int | float]] = {}

    def add_usage(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = self._lookup_pricing(model)
        input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
        output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
        call_cost = input_cost + output_cost

        totals = self._model_totals.setdefault(
            model,
            {"input_tokens": 0, "output_tokens": 0, "cost": 0.0},
        )
        totals["input_tokens"] = int(totals["input_tokens"]) + input_tokens
        totals["output_tokens"] = int(totals["output_tokens"]) + output_tokens
        totals["cost"] = float(totals["cost"]) + call_cost

        self._running_total += call_cost
        return call_cost

    def total(self) -> float:
        return self._running_total

    def breakdown(self) -> dict[str, dict[str, int | float]]:
        return {model: values.copy() for model, values in self._model_totals.items()}

    def _load_config_from_env(self, env_var: str) -> dict[str, dict[str, float]]:
        config_path = os.getenv(env_var)
        if not config_path:
            return {}
        payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError(f"{env_var} must point to a JSON object.")
        return _normalize_pricing(payload)

    def _lookup_pricing(self, model: str) -> dict[str, float]:
        if model in self._pricing:
            return self._pricing[model]

        prefix_matches = [
            (key, price)
            for key, price in self._pricing.items()
            if model.startswith(key) or key.startswith(model)
        ]
        if prefix_matches:
            _, price = max(prefix_matches, key=lambda item: len(item[0]))
            return price

        return {"input_per_1k": 0.0, "output_per_1k": 0.0}


def _normalize_pricing(
    pricing: Mapping[str, Mapping[str, float] | dict[str, Any]],
) -> dict[str, dict[str, float]]:
    normalized: dict[str, dict[str, float]] = {}
    for model, raw_value in pricing.items():
        if not isinstance(raw_value, Mapping):
            raise ValueError(f"Pricing entry for {model!r} must be a JSON object.")
        normalized[model] = {
            "input_per_1k": float(
                raw_value.get(
                    "input_per_1k",
                    raw_value.get("input", raw_value.get("input_cost_per_1k", 0.0)),
                )
            ),
            "output_per_1k": float(
                raw_value.get(
                    "output_per_1k",
                    raw_value.get("output", raw_value.get("output_cost_per_1k", 0.0)),
                )
            ),
        }
    return normalized


__all__ = ["CostTracker", "estimate_tokens"]
