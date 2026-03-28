"""Fixture-based integration test for genome runtime.

Verifies that the runtime + seed genome produces structurally correct
output by mocking the search primitive to return deterministic data.
No live API calls needed.
"""

from __future__ import annotations

import json
from pathlib import Path

# Ensure project root is importable
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from genome import load_genome, validate_genome
from genome.runtime import execute, RuntimeResult
from genome.schema import GenomeSchema
from genome.primitives import _REGISTRY

SEEDS_DIR = Path(__file__).resolve().parent.parent / "genome" / "seeds"

# Deterministic fixture hits
FIXTURE_HITS = [
    {
        "url": f"https://example.com/result-{i}",
        "title": f"AI Agent Framework {i} — open source tool for building agents",
        "snippet": f"A framework for building AI agents with tool support, version {i}",
        "source": ["github_repos", "ddgs", "searxng", "reddit"][i % 4],
        "provider": ["github_repos", "ddgs", "searxng", "reddit"][i % 4],
        "query": "find AI agent repos",
        "query_family": "unknown",
        "backend": "mock",
        "rank": i,
        "score_hint": 10 - i,
    }
    for i in range(20)
]


def _mock_search(query, platform, limit=10):
    """Return deterministic fixture hits regardless of query/platform."""
    return FIXTURE_HITS[:limit]


def _mock_generate_queries(task, genes, config=None):
    """Return fixed query list."""
    return [task, f"{task} framework", f"{task} open source"]


def _mock_score(hits, query, scoring_config=None):
    """Score hits deterministically."""
    for i, hit in enumerate(hits):
        hit["score_hint"] = max(20 - i, 1)
    return hits


def _mock_dedup(hits, threshold=0.85, max_per_domain=None):
    """Dedup by URL."""
    seen = set()
    result = []
    for hit in hits:
        url = hit.get("url", "")
        if url not in seen:
            seen.add(url)
            result.append(hit)
    return result


def _mock_store(records=None, filters=None, index_path=None):
    """No-op store."""
    if records is not None:
        return len(records)
    return []


def _mock_cross_ref(hits, jaccard_threshold=0.85):
    """Pass-through cross_ref."""
    return hits


def _mock_synthesize(evidence, synthesis_config=None):
    """Return empty synthesis."""
    return {"claims": [], "stance_counts": {}}


def test_engine_3phase_genome_validates():
    g = load_genome(SEEDS_DIR / "engine-3phase.json")
    errors = validate_genome(g)
    assert errors == [], f"engine-3phase validation errors: {errors}"


def test_orchestrator_react_genome_validates():
    g = load_genome(SEEDS_DIR / "orchestrator-react.json")
    errors = validate_genome(g)
    assert errors == [], f"orchestrator-react validation errors: {errors}"


def test_daily_discovery_genome_validates():
    g = load_genome(SEEDS_DIR / "daily-discovery.json")
    errors = validate_genome(g)
    assert errors == [], f"daily-discovery validation errors: {errors}"


def _swap_primitives(overrides):
    """Context manager to temporarily replace primitive functions."""
    originals = {}
    for name, fn in overrides.items():
        if name in _REGISTRY:
            spec = _REGISTRY[name]
            originals[name] = spec.fn
            _REGISTRY[name] = spec.__class__(
                name=spec.name,
                input_schema=spec.input_schema,
                output_type=spec.output_type,
                fn=fn,
            )
    return originals


def _restore_primitives(originals):
    for name, fn in originals.items():
        if name in _REGISTRY:
            spec = _REGISTRY[name]
            _REGISTRY[name] = spec.__class__(
                name=spec.name,
                input_schema=spec.input_schema,
                output_type=spec.output_type,
                fn=fn,
            )


def test_runtime_produces_result_with_evidence():
    """Execute runtime with mocked primitives — verify structure."""
    g = load_genome(SEEDS_DIR / "engine-3phase.json")

    originals = _swap_primitives(
        {
            "search": _mock_search,
            "generate_queries": _mock_generate_queries,
            "score": _mock_score,
            "dedup": _mock_dedup,
            "store": _mock_store,
            "cross_ref": _mock_cross_ref,
            "synthesize": _mock_synthesize,
        }
    )
    try:
        result = execute(g, "find AI agent repos")

        assert isinstance(result, RuntimeResult)
        assert result.genome_id == g.genome_id
        assert result.task == "find AI agent repos"
        assert result.intent in (
            "how_to",
            "comparison",
            "opinion",
            "debug",
            "breaking",
            "research",
            "prediction",
        )
        assert result.elapsed_seconds > 0
        assert len(result.phase_results) > 0

        # Check phase names match genome
        phase_names = [pr.name for pr in result.phase_results]
        genome_phase_names = [p.name for p in g.phases]
        assert len(phase_names) > 0
        for name in phase_names:
            assert name in genome_phase_names

        # Verify evidence was collected
        assert result.total_hits > 0, f"Expected hits, got {result.total_hits}"

        # Verify to_dict() serialization
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "evidence_count" in d
        assert "phases" in d
        json.dumps(d)  # must be JSON-serializable

    finally:
        _restore_primitives(originals)


def test_runtime_result_serializable():
    """RuntimeResult.to_dict() produces JSON-serializable output."""
    r = RuntimeResult(
        genome_id="test-001",
        task="test task",
        intent="research",
        evidence=[{"url": "https://example.com", "title": "Test"}],
        total_hits=1,
        unique_urls=1,
    )
    d = r.to_dict()
    serialized = json.dumps(d)
    parsed = json.loads(serialized)
    assert parsed["genome_id"] == "test-001"
    assert parsed["evidence_count"] == 1


def test_default_genome_produces_result():
    """Default genome (no phases) completes without error."""
    g = GenomeSchema.default()
    # Default genome has empty phases — should return empty result
    result = execute(g, "test query")
    assert isinstance(result, RuntimeResult)
    assert len(result.phase_results) == 0
    assert result.elapsed_seconds >= 0


if __name__ == "__main__":
    test_engine_3phase_genome_validates()
    print("PASS: engine-3phase validates")

    test_orchestrator_react_genome_validates()
    print("PASS: orchestrator-react validates")

    test_daily_discovery_genome_validates()
    print("PASS: daily-discovery validates")

    test_runtime_result_serializable()
    print("PASS: RuntimeResult serializable")

    test_default_genome_produces_result()
    print("PASS: default genome produces result")

    test_runtime_produces_result_with_evidence()
    print("PASS: runtime with mocked search produces evidence")

    print("\nALL TESTS PASSED")
