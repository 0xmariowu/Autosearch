"""Block 3 claims compression test with real LLM calls.

Verifies that Haiku can compress raw results into claims.jsonl
with correct format and significant size reduction.

Requires: OPENROUTER_API_KEY environment variable.

Usage:
    OPENROUTER_API_KEY=sk-or-... pytest tests/integration/test_block3_claims.py -x -q
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def get_api_key() -> str | None:
    return os.environ.get("OPENROUTER_API_KEY")


requires_api = pytest.mark.skipif(
    get_api_key() is None,
    reason="OPENROUTER_API_KEY not set",
)


def _load_results(path: str, limit: int = 30) -> list[dict]:
    results_file = ROOT / path
    if not results_file.exists():
        return []
    results = []
    for line in results_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("metadata", {}).get("llm_relevant"):
            results.append(r)
    return results[:limit]


@requires_api
class TestBlock3ClaimsCompression:
    """Verify Haiku produces valid claims from raw results."""

    @pytest.mark.skipif(
        not (ROOT / "evidence/20260404-ai-product-dev-trends-results.jsonl").exists(),
        reason="Session data not available",
    )
    def test_claims_format_and_compression(self) -> None:
        """Haiku compresses results into one-sentence claims with correct schema."""
        from openai import OpenAI

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=get_api_key(),
        )

        results = _load_results(
            "evidence/20260404-ai-product-dev-trends-results.jsonl", limit=20
        )
        assert len(results) > 5, "Not enough relevant results for test"

        raw_size = sum(len(json.dumps(r)) for r in results)

        prompt = f"""For each search result below, write a one-sentence structured claim.

Output ONLY JSONL (one JSON object per line, no other text). Each line:
{{"url": "the result URL", "claim": "one sentence key finding", "source": "the source field", "dimension": "which knowledge dimension this covers"}}

Results to compress:
{json.dumps(results, indent=2)[:6000]}

Output ONLY the JSONL lines, nothing else."""

        start = time.monotonic()
        response = client.chat.completions.create(
            model="anthropic/claude-haiku-4-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.monotonic() - start
        content = response.choices[0].message.content or ""

        # Parse claims
        claims = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                claims.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        # Assertions
        assert elapsed < 60, f"Haiku took {elapsed:.0f}s (> 1 min)"
        assert len(claims) >= 5, (
            f"Only {len(claims)} claims from {len(results)} results (need >= 5)"
        )

        # Schema check
        for claim in claims[:5]:
            assert "url" in claim, f"Missing url: {claim}"
            assert "claim" in claim, f"Missing claim: {claim}"
            assert "source" in claim, f"Missing source: {claim}"
            assert len(claim["claim"]) < 500, (
                f"Claim too long: {len(claim['claim'])} chars"
            )

        # Compression check
        claims_size = sum(len(json.dumps(c)) for c in claims)
        ratio = raw_size / claims_size if claims_size > 0 else 0
        assert ratio > 2, f"Compression ratio {ratio:.1f}x < 2x"
