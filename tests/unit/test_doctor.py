"""Tests for autosearch.core.doctor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from autosearch.core.doctor import format_report, scan_channels


def _make_spec(name: str, requires: list[str]):
    """Build a minimal SkillSpec-like object for mocking."""
    from autosearch.skills.loader import MethodSpec, SkillSpec

    method = MethodSpec(id="api_search", impl="methods/api_search.py", requires=requires)
    return SkillSpec(
        name=name,
        description="test",
        methods=[method],
        skill_dir=Path(f"/fake/skills/channels/{name}"),
    )


def test_scan_channels_ok_when_all_env_set(tmp_path):
    specs = [_make_spec("mychann", ["env:MY_API_KEY"])]
    with (
        patch("autosearch.core.doctor.load_all", return_value=specs),
        patch("autosearch.core.doctor._current_env_keys", return_value={"MY_API_KEY"}),
    ):
        results = scan_channels(tmp_path)

    assert len(results) == 1
    assert results[0].channel == "mychann"
    assert results[0].status == "ok"
    assert results[0].unmet_requires == []


def test_scan_channels_off_when_no_env(tmp_path):
    specs = [_make_spec("mychann", ["env:MISSING_KEY"])]
    with (
        patch("autosearch.core.doctor.load_all", return_value=specs),
        patch("autosearch.core.doctor._current_env_keys", return_value=set()),
    ):
        results = scan_channels(tmp_path)

    assert results[0].status == "off"
    assert "env:MISSING_KEY" in results[0].unmet_requires


def test_scan_channels_warn_when_partial(tmp_path):
    from autosearch.skills.loader import MethodSpec, SkillSpec

    m1 = MethodSpec(id="free", impl="methods/free.py", requires=[])
    m2 = MethodSpec(id="paid", impl="methods/paid.py", requires=["env:PAID_KEY"])
    spec = SkillSpec(
        name="hybrid",
        description="test",
        methods=[m1, m2],
        skill_dir=Path("/fake/skills/channels/hybrid"),
    )
    with (
        patch("autosearch.core.doctor.load_all", return_value=[spec]),
        patch("autosearch.core.doctor._current_env_keys", return_value=set()),
    ):
        results = scan_channels(tmp_path)

    assert results[0].status == "warn"
    assert "env:PAID_KEY" in results[0].unmet_requires


def test_scan_channels_empty_root(tmp_path):
    results = scan_channels(tmp_path / "nonexistent")
    assert results == []


def test_searxng_env_requires_tier_1(tmp_path):
    """SEARXNG_URL is not an API key but still requires config — must land in tier 1, not tier 0."""
    specs = [_make_spec("searxng", ["env:SEARXNG_URL"])]
    with (
        patch("autosearch.core.doctor.load_all", return_value=specs),
        patch("autosearch.core.doctor._current_env_keys", return_value=set()),
    ):
        results = scan_channels(tmp_path)

    assert results[0].tier == 1


def test_format_report_does_not_suggest_nonexistent_fix_flag(tmp_path):
    """doctor output must not reference `autosearch doctor --fix` (the flag does not exist)."""
    specs = [_make_spec("mychann", ["env:MISSING_KEY"])]
    with (
        patch("autosearch.core.doctor.load_all", return_value=specs),
        patch("autosearch.core.doctor._current_env_keys", return_value=set()),
    ):
        results = scan_channels(tmp_path)

    report = format_report(results)
    assert "doctor --fix" not in report, "report still points to the non-existent --fix flag"
