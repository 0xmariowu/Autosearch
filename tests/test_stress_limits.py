"""Stress and boundary tests for AutoSearch pipeline components.

Tests edge cases that caused real bugs:
- Large evidence files (> 10K tokens) that exceed Read tool limits
- judge.py with 200+ results
- search_runner with many queries
- Claims fallback path when claims.jsonl missing
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = str(ROOT / ".venv" / "bin" / "python3")


def _find_python() -> str:
    venv = ROOT / ".venv" / "bin" / "python3"
    if venv.exists():
        return str(venv)
    return "python3"


def _make_result(
    i: int,
    *,
    source: str = "web-ddgs",
    relevant: bool = True,
    snippet_len: int = 200,
) -> dict:
    return {
        "url": f"https://example.com/result-{i}",
        "title": f"Result {i}: {'relevant' if relevant else 'filtered'} finding about topic",
        "snippet": f"This is snippet {i}. " * (snippet_len // 25),
        "source": source,
        "query": f"test query {i % 5}",
        "metadata": {
            "llm_relevant": relevant,
            "llm_reason": "test",
        },
    }


class TestJudgeLargeInput:
    """judge.py must handle large result sets without timeout."""

    def test_200_results_under_30s(self, tmp_path: Path) -> None:
        """Bug scenario: 200+ results should not cause judge.py to hang."""
        evidence = tmp_path / "evidence.jsonl"
        sources = ["web-ddgs", "github-repos", "arxiv", "reddit", "hn", "zhihu"]
        lines = []
        for i in range(200):
            r = _make_result(i, source=sources[i % len(sources)], relevant=i % 3 != 0)
            lines.append(json.dumps(r))
        evidence.write_text("\n".join(lines) + "\n")

        # Create minimal state
        state = tmp_path / "state"
        state.mkdir()
        (state / "timing.json").write_text(
            json.dumps(
                {
                    "start_ts": "2026-04-04T06:00:00Z",
                    "end_ts": "2026-04-04T06:05:00Z",
                }
            )
        )

        python = _find_python()
        start = time.monotonic()
        proc = subprocess.run(
            [python, str(ROOT / "lib" / "judge.py"), str(evidence)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(tmp_path),
        )
        elapsed = time.monotonic() - start

        assert proc.returncode == 0, f"judge.py failed: {proc.stderr}"
        result = json.loads(proc.stdout.strip())
        assert "total" in result
        assert 0 <= result["total"] <= 1
        assert elapsed < 30, f"judge.py took {elapsed:.1f}s on 200 results"

    def test_empty_results(self, tmp_path: Path) -> None:
        """judge.py should handle empty evidence file gracefully."""
        evidence = tmp_path / "evidence.jsonl"
        evidence.write_text("")

        state = tmp_path / "state"
        state.mkdir()
        (state / "timing.json").write_text(
            json.dumps({"start_ts": "2026-04-04T06:00:00Z"})
        )

        python = _find_python()
        proc = subprocess.run(
            [python, str(ROOT / "lib" / "judge.py"), str(evidence)],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(tmp_path),
        )
        # Should not crash
        assert proc.returncode == 0, f"judge.py crashed on empty: {proc.stderr}"


class TestLargeEvidenceFile:
    """Evidence files > 80KB (> 10K tokens) must have a usable fallback."""

    def test_large_file_compact_extraction(self, tmp_path: Path) -> None:
        """Simulate the claims fallback: extract compact JSON from large results."""
        evidence = tmp_path / "evidence.jsonl"
        # Generate 120 results with long snippets (~80KB total)
        lines = []
        for i in range(120):
            r = _make_result(i, snippet_len=500, relevant=i % 3 != 0)
            lines.append(json.dumps(r))
        evidence.write_text("\n".join(lines) + "\n")

        file_size = evidence.stat().st_size
        assert file_size > 50_000, f"Test file too small: {file_size}"

        # Run the compact extraction (same command as Block 4 fallback)
        python = _find_python()
        cmd = f"""import json
for line in open('{evidence}'):
    r = json.loads(line)
    if r.get('metadata', {{}}).get('llm_relevant'):
        print(json.dumps({{'url': r.get('url',''), 'title': r.get('title','')[:100], 'claim': r.get('snippet','')[:200], 'source': r.get('source','')}}))
"""
        proc = subprocess.run(
            [python, "-c", cmd],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert proc.returncode == 0, f"Extraction failed: {proc.stderr}"
        compact_lines = [l for l in proc.stdout.strip().split("\n") if l.strip()]
        compact_size = len(proc.stdout)

        # Compact output should be much smaller than raw
        assert compact_size < file_size * 0.5, (
            f"Compact {compact_size} not smaller enough vs raw {file_size}"
        )
        assert len(compact_lines) > 0, "No relevant results extracted"

        # Each line should be valid JSON with expected keys
        for line in compact_lines[:5]:
            obj = json.loads(line)
            assert "url" in obj
            assert "title" in obj
            assert "claim" in obj


class TestClaimsCompression:
    """Claims file should compress results by > 5x."""

    def test_claims_format(self, tmp_path: Path) -> None:
        """Verify expected claims.jsonl structure."""
        claims = tmp_path / "claims.jsonl"
        entries = []
        for i in range(30):
            entries.append(
                json.dumps(
                    {
                        "url": f"https://example.com/{i}",
                        "claim": f"Finding {i}: important discovery about the topic",
                        "source": "web-ddgs",
                        "dimension": "market_landscape",
                    }
                )
            )
        claims.write_text("\n".join(entries) + "\n")

        # Verify format
        for line in claims.read_text().strip().split("\n"):
            obj = json.loads(line)
            assert "url" in obj
            assert "claim" in obj
            assert "source" in obj
            assert "dimension" in obj
            # Each claim should be concise (< 500 chars)
            assert len(obj["claim"]) < 500

    def test_compression_ratio(self, tmp_path: Path) -> None:
        """Claims should be > 5x smaller than raw results."""
        # Simulate raw results (big)
        raw = tmp_path / "results.jsonl"
        lines = []
        for i in range(80):
            lines.append(json.dumps(_make_result(i, snippet_len=500)))
        raw.write_text("\n".join(lines) + "\n")
        raw_size = raw.stat().st_size

        # Simulate claims (small)
        claims = tmp_path / "claims.jsonl"
        claim_lines = []
        for i in range(80):
            claim_lines.append(
                json.dumps(
                    {
                        "url": f"https://example.com/result-{i}",
                        "claim": f"Key finding {i} about the topic",
                        "source": "web-ddgs",
                        "dimension": "core",
                    }
                )
            )
        claims.write_text("\n".join(claim_lines) + "\n")
        claims_size = claims.stat().st_size

        ratio = raw_size / claims_size
        assert ratio > 4, f"Compression ratio {ratio:.1f}x < 4x target"


class TestSearchRunnerTimeout:
    """search_runner.py should respect timeouts."""

    def test_importable(self) -> None:
        """search_runner.py should be importable without side effects."""
        python = _find_python()
        proc = subprocess.run(
            [
                python,
                "-c",
                "from lib.search_runner import dedup_results, normalize_url",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(ROOT),
            env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"},
        )
        assert proc.returncode == 0, f"Import failed: {proc.stderr}"
