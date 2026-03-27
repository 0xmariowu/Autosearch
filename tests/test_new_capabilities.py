"""Tests for new capabilities (F004 patterns)."""

import pytest


class TestConsensusScore:
    def test_multi_provider_boost(self):
        from capabilities.consensus_score import run
        hits = [
            {"url": "a.com", "score_hint": 10, "provider": "ddgs"},
            {"url": "a.com", "score_hint": 10, "provider": "searxng"},
            {"url": "b.com", "score_hint": 20, "provider": "ddgs"},
        ]
        result = run(hits)
        assert result[0]["consensus_count"] == 2
        assert result[2]["consensus_count"] == 1

    def test_empty_input(self):
        from capabilities.consensus_score import run
        assert run([]) == []


class TestContentMerge:
    def test_merges_duplicates(self):
        from capabilities.content_merge import run
        hits = [
            {"url": "https://a.com", "title": "Short", "snippet": "First", "provider": "x"},
            {"url": "https://a.com/", "title": "Longer Title", "snippet": "Second", "provider": "y"},
        ]
        result = run(hits)
        assert len(result) == 1
        assert result[0]["title"] == "Longer Title"
        assert result[0]["merge_count"] == 2

    def test_no_duplicates_passthrough(self):
        from capabilities.content_merge import run
        hits = [
            {"url": "https://a.com", "title": "A", "snippet": "a", "provider": "x"},
            {"url": "https://b.com", "title": "B", "snippet": "b", "provider": "y"},
        ]
        result = run(hits)
        assert len(result) == 2


class TestBackendHealth:
    def test_suspension_after_errors(self):
        from capabilities.backend_health import run, _STATE_PATH
        from pathlib import Path
        import tempfile
        original = _STATE_PATH
        # Use temp file
        import capabilities.backend_health as mod
        mod._STATE_PATH = Path(tempfile.mktemp(suffix=".json"))
        try:
            for _ in range(3):
                run(None, action="record_error", backend="test_be", error_type="timeout")
            report = run(None, action="check")
            assert report["test_be"]["suspended"]
            # Recovery
            run(None, action="record_success", backend="test_be")
            report = run(None, action="check")
            assert not report["test_be"]["suspended"]
        finally:
            mod._STATE_PATH = original


class TestCacheResults:
    def test_store_and_retrieve(self):
        from capabilities.cache_results import run, _DB_PATH
        from pathlib import Path
        import tempfile
        import capabilities.cache_results as mod
        original = mod._DB_PATH
        mod._DB_PATH = Path(tempfile.mktemp(suffix=".sqlite"))
        try:
            run(["data"], action="put", query="test", provider="p")
            result = run(None, action="get", query="test", provider="p")
            assert result["hit"]
            assert result["data"] == ["data"]
            # Miss
            result = run(None, action="get", query="other", provider="p")
            assert not result["hit"]
        finally:
            mod._DB_PATH = original


class TestFreshnessCheck:
    def test_fresh_and_stale(self):
        from capabilities.freshness_check import run
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        hits = [
            {"title": "A", "created": today},
            {"title": "B", "created": "2020-01-01"},
        ]
        result = run(hits, category="software")
        assert result[0]["freshness_status"] == "fresh"
        assert result[1]["freshness_status"] == "stale"


class TestPersonaExpand:
    def test_returns_7_queries(self):
        from capabilities.persona_expand import run
        result = run("AI agent framework")
        assert len(result) == 7
        personas = {r["persona"] for r in result}
        assert "skeptic" in personas


class TestStuckDetect:
    def test_detects_stuck(self):
        from capabilities.stuck_detect import run
        history = [
            {"urls": ["a", "b"], "new_count": 2},
            {"urls": ["a", "b"], "new_count": 0},
            {"urls": ["a", "b"], "new_count": 0},
        ]
        result = run(None, history=history)
        assert result["stuck"]

    def test_not_stuck(self):
        from capabilities.stuck_detect import run
        history = [
            {"urls": ["a"], "new_count": 5},
            {"urls": ["b", "c"], "new_count": 8},
        ]
        result = run(None, history=history)
        assert not result["stuck"]


class TestBeastMode:
    def test_deduplicates_and_summarizes(self):
        from capabilities.beast_mode import run
        evidence = [
            {"title": "A", "url": "a.com", "score_hint": 30},
            {"title": "B", "url": "b.com", "score_hint": 10},
            {"title": "A dup", "url": "a.com", "score_hint": 25},
        ]
        result = run(evidence, task_spec="test")
        assert result["unique_count"] == 2
        assert result["status"] == "beast_mode"


class TestBreadthControl:
    def test_halving(self):
        from capabilities.breadth_control import run
        r0 = run(None, initial_breadth=8, current_depth=0)
        r1 = run(None, initial_breadth=8, current_depth=1)
        r2 = run(None, initial_breadth=8, current_depth=2)
        assert r0["breadth"] == 8
        assert r1["breadth"] == 4
        assert r2["breadth"] == 2


class TestLearningsExtract:
    def test_extracts_learnings(self):
        from capabilities.learnings_extract import run
        hits = [
            {"title": "Framework X", "url": "https://x.com", "snippet": "A great tool"},
            {"title": "Framework Y", "url": "https://y.com", "snippet": "Another tool"},
        ]
        result = run(hits, query="AI framework")
        assert isinstance(result, list)
        assert len(result) > 0
