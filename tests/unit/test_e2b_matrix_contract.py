"""Pin the v2 contract on the E2B matrices.

Without this guard, a future PR can re-add `call_tool("research", ...)` or
`stdout_contains: "References"` and silently re-resurrect the v1 expectations
that the audit explicitly flagged as a release blocker.

If a real v1-style assertion is ever needed again, document it in the matrix
file and update this test to allowlist the file/line.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MATRICES = [
    ROOT / "tests" / "e2b" / "matrix.yaml",
    ROOT / "tests" / "e2b" / "matrix-release-gate.yaml",
]


@pytest.mark.parametrize("matrix_path", MATRICES, ids=lambda p: p.name)
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


@pytest.mark.parametrize("matrix_path", MATRICES, ids=lambda p: p.name)
def test_matrix_does_not_call_deprecated_research_tool(matrix_path: Path) -> None:
    text = matrix_path.read_text(encoding="utf-8")
    assert 'call_tool("research"' not in text, (
        f"{matrix_path.name} still invokes the deprecated `research` MCP tool; "
        "use list_skills/run_clarify/run_channel instead."
    )


@pytest.mark.parametrize("matrix_path", MATRICES, ids=lambda p: p.name)
def test_matrix_yaml_parses(matrix_path: Path) -> None:
    """Catch YAML syntax breakage from sweeping edits."""
    data = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict) and "phases" in data
    assert isinstance(data["phases"], dict) and data["phases"]
