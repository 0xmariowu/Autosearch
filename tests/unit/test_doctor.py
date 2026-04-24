"""Tests for autosearch.core.doctor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from autosearch.core.doctor import format_report, scan_channels


def _make_spec(
    name: str,
    requires: list[str],
    *,
    tier: int | None = None,
    fix_hint: str | None = None,
    skill_root: Path | None = None,
):
    """Build a minimal SkillSpec-like object for mocking.

    Creates a real impl file under `skill_root/<name>/methods/api_search.py`
    when `skill_root` is provided so the new impl-missing check (which now
    treats absent files as unmet) doesn't downgrade these synthetic specs to
    'off'. Existing tests that don't care about the impl check pre-patch
    `is_file` via the helper below.
    """
    from autosearch.skills.loader import MethodSpec, SkillSpec

    method = MethodSpec(id="api_search", impl="methods/api_search.py", requires=requires)
    if skill_root is not None:
        skill_dir = skill_root / name
        (skill_dir / "methods").mkdir(parents=True, exist_ok=True)
        (skill_dir / "methods" / "api_search.py").write_text("", encoding="utf-8")
    else:
        skill_dir = Path(f"/fake/skills/channels/{name}")
    return SkillSpec(
        name=name,
        description="test",
        methods=[method],
        tier=tier,
        fix_hint=fix_hint,
        skill_dir=skill_dir,
    )


def test_scan_channels_ok_when_all_env_set(tmp_path):
    specs = [_make_spec("mychann", ["env:MY_API_KEY"], skill_root=tmp_path)]
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
    skill_dir = tmp_path / "hybrid"
    (skill_dir / "methods").mkdir(parents=True)
    (skill_dir / "methods" / "free.py").write_text("", encoding="utf-8")
    (skill_dir / "methods" / "paid.py").write_text("", encoding="utf-8")
    spec = SkillSpec(
        name="hybrid",
        description="test",
        methods=[m1, m2],
        skill_dir=skill_dir,
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
