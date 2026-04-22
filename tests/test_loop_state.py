"""Tests for autosearch.core.loop_state."""

from __future__ import annotations

import pytest

from autosearch.core import loop_state as ls


@pytest.fixture(autouse=True)
def _clear_states():
    ls._LOOP_STATES.clear()
    yield
    ls._LOOP_STATES.clear()


def test_init_creates_empty_state():
    state_id = ls.init_loop()
    assert state_id in ls._LOOP_STATES
    state = ls._LOOP_STATES[state_id]
    assert state.visited_urls == []
    assert state.gaps == []
    assert state.round_count == 0


def test_update_adds_urls_from_url_field():
    state_id = ls.init_loop()
    evidence = [{"url": "https://example.com/a"}, {"url": "https://example.com/b"}]
    summary = ls.update_loop(state_id, evidence, "test")
    assert "https://example.com/a" in summary["visited_urls"]
    assert "https://example.com/b" in summary["visited_urls"]
    assert summary["round_count"] == 1
    assert summary["evidence_count"] == 2


def test_update_adds_urls_from_link_field():
    state_id = ls.init_loop()
    summary = ls.update_loop(state_id, [{"link": "https://example.com/link"}], "q")
    assert "https://example.com/link" in summary["visited_urls"]


def test_sequential_updates_accumulate_urls():
    state_id = ls.init_loop()
    ls.update_loop(state_id, [{"url": "https://example.com/1"}], "q1")
    ls.update_loop(state_id, [{"url": "https://example.com/2"}], "q2")
    state = ls._LOOP_STATES[state_id]
    assert "https://example.com/1" in state.visited_urls
    assert "https://example.com/2" in state.visited_urls
    assert state.round_count == 2


def test_get_gaps_returns_added_gaps():
    state_id = ls.init_loop()
    ls.add_gap(state_id, "gap A")
    ls.add_gap(state_id, "gap B")
    assert "gap A" in ls.get_gaps(state_id)
    assert "gap B" in ls.get_gaps(state_id)
