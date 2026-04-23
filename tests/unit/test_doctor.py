"""Tests for autosearch.core.doctor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from autosearch.core.doctor import scan_channels


def _make_spec(
    name: str,
    requires: list[str],
    *,
    tier: int | None = None,
    fix_hint: str | None = None,
):
    """Build a minimal SkillSpec-like object for mocking."""
    from autosearch.skills.loader import MethodSpec, SkillSpec

    method = MethodSpec(id="api_search", impl="methods/api_search.py", requires=requires)
    return SkillSpec(
        name=name,
        description="test",
        methods=[method],
        tier=tier,
        fix_hint=fix_hint,
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


def test_scan_channels_prefers_declared_doctor_metadata(tmp_path):
    specs = [
        _make_spec(
            "xueqiu",
            ["env:XUEQIU_COOKIES"],
            tier=2,
            fix_hint="autosearch login xueqiu",
        )
    ]
    with (
        patch("autosearch.core.doctor.load_all", return_value=specs),
        patch("autosearch.core.doctor._current_env_keys", return_value=set()),
    ):
        results = scan_channels(tmp_path)

    assert results[0].tier == 2
    assert results[0].fix_hint == "autosearch login xueqiu"


def test_scan_channels_reads_declared_doctor_metadata_from_frontmatter(tmp_path):
    skill_dir = tmp_path / "xueqiu"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: xueqiu",
                "description: Finance search",
                "methods:",
                "  - id: api_search",
                "    impl: methods/api_search.py",
                "    requires: [env:XUEQIU_COOKIES]",
                "fallback_chain: [api_search]",
                "tier: 2",
                'fix_hint: "autosearch login xueqiu"',
                "---",
                "",
                "Body.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with patch("autosearch.core.doctor._current_env_keys", return_value=set()):
        results = scan_channels(tmp_path)

    assert results[0].channel == "xueqiu"
    assert results[0].tier == 2
    assert results[0].fix_hint == "autosearch login xueqiu"
