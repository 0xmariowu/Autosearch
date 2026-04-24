"""Plan §P0-2: a method whose impl file is missing must NEVER count as
available, even if all its declared env requirements are satisfied.

Before this contract, doctor read `requires:` from SKILL.md and ignored whether
the impl file actually existed on disk — so half-scaffolded channels reported
`ok` and users configured keys that ran nothing.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from autosearch.core.doctor import scan_channels


def _write_skill(
    root: Path,
    name: str,
    *,
    method_id: str = "api_search",
    impl_filename: str = "api_search.py",
    create_impl: bool,
    requires: list[str] | None = None,
) -> None:
    skill = root / name
    (skill / "methods").mkdir(parents=True, exist_ok=True)
    requires_yaml = "[]" if not requires else "[" + ", ".join(requires) + "]"
    (skill / "SKILL.md").write_text(
        dedent(
            f"""
            ---
            name: {name}
            description: "fixture"
            version: 1
            languages: [en]
            methods:
              - id: {method_id}
                impl: methods/{impl_filename}
                requires: {requires_yaml}
            fallback_chain: [{method_id}]
            ---
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    if create_impl:
        (skill / "methods" / impl_filename).write_text(
            "async def search(q): return []\n", encoding="utf-8"
        )


def test_missing_impl_marks_channel_off_even_when_requires_are_satisfied(tmp_path):
    """The smoking gun: zero requires, no env at all, but impl file missing —
    must not be 'ok'."""
    root = tmp_path / "channels"
    _write_skill(root, "ghost_chan", create_impl=False, requires=[])

    results = {r.channel: r for r in scan_channels(root)}
    assert "ghost_chan" in results
    assert results["ghost_chan"].status == "off"
    assert any("impl_missing" in u for u in results["ghost_chan"].unmet_requires)


def test_existing_impl_with_no_requires_is_ok(tmp_path):
    root = tmp_path / "channels"
    _write_skill(root, "real_chan", create_impl=True, requires=[])
    results = {r.channel: r for r in scan_channels(root)}
    assert results["real_chan"].status == "ok"
    assert not any("impl_missing" in u for u in results["real_chan"].unmet_requires)


def test_real_repo_has_no_silent_missing_impls():
    """Static integrity: every channel skill that ships with this package must
    have its declared method impl files on disk. If this fires, either commit
    the impl, mark the method as planned/disabled, or remove it from SKILL.md."""
    from autosearch.skills import load_all

    root = Path(__file__).resolve().parents[2] / "autosearch" / "skills" / "channels"
    missing: list[tuple[str, str, str]] = []
    for spec in load_all(root):
        for method in spec.methods:
            if not (spec.skill_dir / method.impl).is_file():
                missing.append((spec.name, method.id, method.impl))

    assert not missing, "channels declare methods whose impl files do not exist:\n" + "\n".join(
        f"  {name}.{mid} -> {impl}" for name, mid, impl in missing
    )
