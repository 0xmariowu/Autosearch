"""AUTOSEARCH_BYPASS_CLARIFY env var: when set, pipeline proceeds past
`need_clarification=true` instead of halting with `needs_clarification` status.

Rationale: the Clarifier LLM over-triggers on broad-but-interpretable queries
(e.g. "MoE 模型工程实践最佳指南"). Batch benches cannot answer interactive
prompts, so they set this env var to keep research running on the Clarifier's
best-guess rubrics.
"""

from __future__ import annotations

import pytest

from autosearch.core.pipeline import _bypass_clarify_enabled


@pytest.mark.parametrize(
    "truthy", ["1", "true", "TRUE", "True", "yes", "YES", "on", "ON", " 1 ", " true "]
)
def test_truthy_values_enable_bypass(monkeypatch, truthy):
    monkeypatch.setenv("AUTOSEARCH_BYPASS_CLARIFY", truthy)
    assert _bypass_clarify_enabled() is True


@pytest.mark.parametrize(
    "falsy", ["", "0", "false", "FALSE", "no", "NO", "off", "OFF", "random", "2"]
)
def test_falsy_or_unknown_values_leave_default_behaviour(monkeypatch, falsy):
    monkeypatch.setenv("AUTOSEARCH_BYPASS_CLARIFY", falsy)
    assert _bypass_clarify_enabled() is False


def test_unset_defaults_to_false(monkeypatch):
    monkeypatch.delenv("AUTOSEARCH_BYPASS_CLARIFY", raising=False)
    assert _bypass_clarify_enabled() is False
