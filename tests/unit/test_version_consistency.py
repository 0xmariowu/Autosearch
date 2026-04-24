"""Pin the npm/pyproject version mapping so a release can't ship with drifted versions."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate" / "check_version_consistency.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_version_consistency", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_version_consistency"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("pyproject_version", "expected_npm"),
    [
        ("2026.04.23.1", "2026.4.23"),
        ("2026.04.23.9", "2026.4.23"),
        ("2026.12.01.1", "2026.12.1"),
        ("2027.01.01.42", "2027.1.1"),
    ],
)
def test_derive_npm_version_strips_leading_zeros_and_drops_daily_counter(
    pyproject_version: str, expected_npm: str
) -> None:
    mod = _load_module()
    assert mod.derive_npm_version(pyproject_version) == expected_npm


@pytest.mark.parametrize(
    "bad",
    [
        "2026.04.23",  # missing daily counter
        "2026.04",  # too short
        "v2026.04.23.1",  # leading prefix
    ],
)
def test_derive_npm_version_rejects_malformed_pyproject(bad: str) -> None:
    mod = _load_module()
    with pytest.raises(ValueError):
        mod.derive_npm_version(bad)


def test_repository_versions_currently_consistent() -> None:
    """The script itself, run against the live repo, must exit 0. This is the
    same check CI/release will run."""
    mod = _load_module()
    assert mod.main() == 0
