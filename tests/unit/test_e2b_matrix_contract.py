"""Pin the v2 contract on every E2B matrix.

Without this guard, a future PR can re-add `call_tool("research", ...)` or
`stdout_contains: "References"` and silently re-resurrect the v1 expectations
that the audit explicitly flagged as a release blocker.

Scope evolution (plan §Gate F):
- previously only matrix.yaml + matrix-release-gate.yaml were scanned;
- now every tests/e2b/*.yaml is scanned;
- the `autosearch query` CLI is allowed because plan §P1-2 explicitly permits
  old query calls when they assert deprecation behavior (matrix.yaml does this
  by pinning `stdout_contains: "deprecated"`); enforcing that pairing as
  static yaml-parse logic would be over-engineering for the value it adds.

If a real v1-style assertion is ever needed again, document it in the matrix
file and update this test to allowlist the file/line.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MATRIX_DIR = ROOT / "tests" / "e2b"
ALL_MATRICES = sorted(MATRIX_DIR.glob("*.yaml"))


@pytest.mark.parametrize("matrix_path", ALL_MATRICES, ids=lambda p: p.name)
def test_matrix_does_not_assert_v1_report_output(matrix_path: Path) -> None:
    """The deprecated `query` path used to produce a "References" / "Sources"
    section. v2 install gates must NOT assert against those strings."""
    text = matrix_path.read_text(encoding="utf-8")
    forbidden_patterns = [
        r'stdout_contains:\s*"References"',
        r'stdout_contains:\s*"Sources"',
        r"stdout_regex:.*References",
    ]
    for pat in forbidden_patterns:
        matches = re.findall(pat, text)
        assert not matches, (
            f"{matrix_path.name} still asserts v1 report output ({pat!r}); "
            "rewrite the task to either expect a deprecation message or call "
            "the v2 MCP run_channel tool."
        )


@pytest.mark.parametrize("matrix_path", ALL_MATRICES, ids=lambda p: p.name)
def test_matrix_does_not_call_deprecated_research_tool(matrix_path: Path) -> None:
    """The MCP `research` tool is being phased out (plan §P1-4). E2B prompts
    must not steer the host agent toward it — they should drive list_skills +
    run_clarify + run_channel directly."""
    text = matrix_path.read_text(encoding="utf-8")
    assert 'call_tool("research"' not in text, (
        f"{matrix_path.name} still invokes the deprecated `research` MCP tool; "
        "use list_skills/run_clarify/run_channel instead."
    )
    assert "Use the research tool" not in text, (
        f"{matrix_path.name} still tells the host agent to use the deprecated "
        "`research` tool in its prompt; rewrite the prompt to drive the v2 "
        "tool-supplier flow (list_skills / run_clarify / run_channel)."
    )


@pytest.mark.parametrize("matrix_path", ALL_MATRICES, ids=lambda p: p.name)
def test_matrix_yaml_parses(matrix_path: Path) -> None:
    """Catch YAML syntax breakage from sweeping edits."""
    data = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "phases" in data
    assert isinstance(data["phases"], dict) and data["phases"]
